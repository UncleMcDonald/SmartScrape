import time
import random
import queue
import threading
import json
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, FeatureNotFound
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4.element import Tag


BROWSERS = {
    "chrome":  r"Chrome/{version}.0.0.0 Safari/537.36",
    "edge":    r"Chrome/{version}.0.0.0 Safari/537.36 Edg/{version}.0.0.0",
    "firefox": r"Gecko/20100101 Firefox/{version}.0",
    "safari":  r"Version/{safari_ver}.0 Safari/605.1.15",
}

DESKTOP_OS = [
    "Windows NT 10.0; Win64; x64",
    "Windows NT 6.1; Win64; x64",
    "Macintosh; Intel Mac OS X 10_15_7",
    "X11; Linux x86_64",
]

MOBILE_OS = [
    "iPhone; CPU iPhone OS 17_4 like Mac OS X",
    "Linux; Android 14; Pixel 8 Pro",
    "Linux; Android 13; SM-S918B",                 # Samsung S23 Ultra
]

def _rand_version(min_v: int, max_v: int) -> str:
    """Return a random major browser version as a string."""
    return str(random.randint(min_v, max_v))

def generate_random_user_agent() -> str:
    mobile = random.random() < 0.3            # ~30 % mobile traffic
    os_str = random.choice(MOBILE_OS if mobile else DESKTOP_OS)

    browser = random.choice(list(BROWSERS.keys()))
    version = _rand_version(118, 125)         # tweak as releases progress

    # Safari has its own major versioning scheme
    ua_fragment = (
        BROWSERS["safari"].format(safari_ver=_rand_version(17, 18))
        if browser == "safari" else
        BROWSERS[browser].format(version=version)
    )

    ua = f"Mozilla/5.0 ({os_str}) AppleWebKit/537.36 (KHTML, like Gecko) {ua_fragment}"
    return ua

def get_chrome_options(user_agent=None):
    """获取Chrome配置，可选指定User-Agent，优化内存使用"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 无头模式
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # 内存优化设置
    chrome_options.add_argument("--disable-gpu")  # 禁用GPU加速
    chrome_options.add_argument("--disable-extensions")  # 禁用扩展
    chrome_options.add_argument("--disable-software-rasterizer")  # 禁用软件光栅化
    chrome_options.add_argument("--disable-webgl")  # 禁用WebGL
    chrome_options.add_argument("--disable-3d-apis")  # 禁用3D API
    chrome_options.add_argument("--disable-canvas-aa")  # 禁用画布抗锯齿
    chrome_options.add_argument("--disable-accelerated-2d-canvas")  # 禁用加速2D画布
    chrome_options.add_argument("--disable-dev-shm-usage")  # 禁用/dev/shm
    chrome_options.add_argument("--remote-debugging-port=9222")  # 远程调试端口
    chrome_options.add_argument("--disable-bundled-ppapi-flash")  # 禁用捆绑的Flash
    chrome_options.add_argument("--disable-infobars")  # 禁用信息栏
    chrome_options.add_argument("--mute-audio")  # 静音
    chrome_options.add_argument("--window-size=800,600")  # 设置较小的窗口尺寸
    
    # 随机或指定User-Agent
    if user_agent is None:
        user_agent = generate_random_user_agent()
    chrome_options.add_argument(f"--user-agent={user_agent}")
    
    # 禁用自动化标志
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # 禁用图片加载以提高性能
    chrome_options.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2,
        "profile.managed_default_content_settings.javascript": 1,
        "profile.managed_default_content_settings.plugins": 2,
        "profile.managed_default_content_settings.popups": 2,
        "profile.managed_default_content_settings.geolocation": 2,
        "profile.managed_default_content_settings.media_stream": 2
    })
    
    return chrome_options

import re
from typing import Tuple
from bs4 import BeautifulSoup
from requests import Response

# ── 1. 预编译少量正则，避免误报 ────────────────────────────────
R_BLOCK = re.compile(
    r"\b(access\s+denied|verify\s+you\s+are\s+human|too\s+many\s+requests|"
    r"bot\s+detected|unusual\s+traffic|incapsula|cloudflare|akamai|protecting\s+itself)\b",
    flags=re.I
)
R_CAPTCHA = re.compile(r"recaptcha|g-recaptcha|data-sitekey", flags=re.I)

# ── 2. 响应级检查：状态码 / header 比 HTML 可靠 ────────────────
BLOCK_STATUS = {403, 429, 503}
WAF_HEADERS  = {
    "server":  ["cloudflare", "akamai", "f5 big-ip", "imperva"],
    "x-cdn":   ["incapsula", "cloudflare"],
    "via":     ["akamai"],
    "cf-ray":  [""]                 # presence alone is enough
}

def is_access_limited(resp: Response, *, threshold: int = 3) -> Tuple[bool, int]:
    """
    Return (blocked?, score).  Tune `threshold` (default 3) for your risk appetite.
    """
    score = 0

    # 1️⃣  HTTP-level evidence
    if resp.status_code in BLOCK_STATUS:
        score += 4                       # strong signal
    for header, waf_names in WAF_HEADERS.items():
        val = resp.headers.get(header, "").lower()
        if any(name in val for name in waf_names):
            score += 1                   # weak signal

    # 2️⃣  Lightweight HTML heuristics (only if we haven't decided yet)
    if score < threshold:
        html = resp.text or ""
        if R_BLOCK.search(html):
            score += 2
        if R_CAPTCHA.search(html):
            score += 2

        # title like <title>Access Denied</title>
        title = BeautifulSoup(html[:4000], "html.parser").title
        if title and re.search(r"\b(access\s+denied|blocked|restricted)\b", title.text, flags=re.I):
            score += 2

    return score >= threshold, score


def scrape_url(url):
    # 最多尝试5次（增加重试次数）
    max_retries = 3
    retry_delay_base = 3  # 基础等待时间(秒)
    
    used_user_agents = set()  # 记录已使用过的User-Agent
    
    for attempt in range(max_retries):
        driver = None
        try:
            # 每次尝试使用不同的User-Agent
            current_user_agent = generate_random_user_agent()
            while current_user_agent in used_user_agents and len(used_user_agents) < 9:  # 避免重复使用相同UA
                current_user_agent = generate_random_user_agent()
            
            used_user_agents.add(current_user_agent)
            
            # 配置Chrome
            chrome_options = get_chrome_options(current_user_agent)
            
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(30)
            
            # 随机化窗口大小，避免指纹识别
            width = random.randint(1024, 1920)
            height = random.randint(768, 1080)
            driver.set_window_size(width, height)
            
            # 访问页面
            print(f"Attempt {attempt + 1}: Accessing {url}")
            print(f"Using User-Agent: {current_user_agent[:30]}...")
            
            driver.get(url)
            
            # 等待页面加载
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # 随机滚动行为，更像人类
            scroll_pause_time = random.uniform(0.5, 2.0)
            # 随机滚动到页面中部
            driver.execute_script(f"window.scrollTo(0, {random.randint(300, 700)});")
            time.sleep(scroll_pause_time)
            # 滚动到页面底部
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause_time)
            
            # 获取页面源码
            page_source = driver.page_source
            
            #  检查是否被限制访问
            # if is_access_limited(page_source):
            #     print(f"Access limited detected on attempt {attempt + 1}. Changing identity...")
            #     if attempt < max_retries - 1:
            #         # 指数退避等待时间(每次增加等待)
            #         wait_time = retry_delay_base * (2 ** attempt) + random.random() * 2
            #         print(f"Waiting {wait_time:.2f}s before retry...")
            #         time.sleep(wait_time)
            #         continue
            #     else:
            #         return {"error": "Access limited after max retries", "details": "Website has rate limited or blocked access"}
            
            return page_source
            
        except (TimeoutException, WebDriverException) as e:
            if attempt < max_retries - 1:
                # 指数退避等待
                wait_time = retry_delay_base * (2 ** attempt) + random.random() * 2
                print(f"Error: {str(e)}. Waiting {wait_time:.2f}s before retry...")
                time.sleep(wait_time)
                continue
            else:
                return {"error": "Failed to fetch page", "details": str(e)}
        finally:
            # 确保driver被关闭
            if driver:
                driver.quit()

def collect_potential_product_images(soup, base_url):
    """
    收集页面中可能的产品图片，并进行评分和排序
    
    :param soup: BeautifulSoup对象
    :param base_url: 基础URL，用于转换相对路径
    :return: 潜在产品图片列表，已按相关性排序
    """
    potential_images = []
    
    # 1. 优先考虑 Open Graph 图片
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        img_url = urljoin(base_url, og["content"])
        potential_images.append({"url": img_url, "source": "og:image", "score": 100})

    # 2. 寻找产品图片
    # 不太可能是主图的图片特征
    non_product_patterns = [
        r'(icon|logo|avatar|banner|background|button|thumbnail|thumb|nav|header|footer)',
        r'(/icons/|/logos/|/ui/|/assets/icons/|/svg/)',
        r'(width|height)=(["|\'])([0-9]+)(["|\']).*?(\\3<50)'  # 尺寸过小的图片
    ]
    
    # 编译正则
    non_product_regex = [re.compile(pattern, re.I) for pattern in non_product_patterns]
    
    # 收集所有可能的产品图片
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if not src:
            continue
            
        # 过滤掉不太可能是主图的图片
        if any(regex.search(str(img)) for regex in non_product_regex):
            continue
            
        # 过滤掉base64和data URI图片
        if src.startswith('data:'):
            continue
        
        # 计算分数 - 基于图片尺寸与其他特征
        score = 0
        
        # 1. 尺寸分数
        w = int(img.get("width") or 0)
        h = int(img.get("height") or 0)
        size_score = w * h
        
        # 限制最大尺寸分数
        size_score = min(size_score, 1000000)
        score += size_score / 10000  # 归一化尺寸分数
        
        # 2. 产品相关类名或ID加分
        img_str = str(img)
        if re.search(r'(product|item|main)[\-_]?(image|img|photo)', img_str, re.I):
            score += 50
        
        # 3. Alt文本包含"product"相关词汇加分
        alt = img.get("alt", "")
        if alt and re.search(r'(product|item)', alt, re.I):
            score += 30
            
        # 4. 图片URL包含"product"相关词汇加分
        if re.search(r'(product|item|main|large)', src, re.I):
            score += 20
            
        # 收集这个潜在的产品图片
        full_url = urljoin(base_url, src)
        potential_images.append({
            "url": full_url,
            "alt": alt,
            "source": "img_tag",
            "score": score,
            "dimensions": f"{w}x{h}" if w and h else "unknown"
        })

    # 3. 从JSON-LD中提取
    ld = soup.find("script", type="application/ld+json")
    if ld and ld.string:
        try:
            # 清理掉注释
            clean_json = re.sub(r"<!--.*?-->", "", ld.string, flags=re.S)
            data = json.loads(clean_json)
            
            # 处理单个对象或数组
            if isinstance(data, dict):
                data_items = [data]
            elif isinstance(data, list):
                data_items = data
            else:
                data_items = []
                
            # 从各种可能的架构中提取图片
            for item in data_items:
                if isinstance(item, dict):
                    # 检查不同的可能键
                    for img_key in ['image', 'images', 'primaryImage', 'productImage']:
                        if img_key in item:
                            img_data = item[img_key]
                            urls = []
                            
                            # 处理多种可能的格式
                            if isinstance(img_data, list):
                                for img_item in img_data:
                                    if isinstance(img_item, str):
                                        urls.append(img_item)
                                    elif isinstance(img_item, dict) and 'url' in img_item:
                                        urls.append(img_item['url'])
                            elif isinstance(img_data, str):
                                urls.append(img_data)
                            elif isinstance(img_data, dict) and 'url' in img_data:
                                urls.append(img_data['url'])
                                
                            # 添加到潜在图片列表
                            for url in urls:
                                full_url = urljoin(base_url, url)
                                potential_images.append({
                                    "url": full_url,
                                    "source": f"json_ld_{img_key}",
                                    "score": 80  # JSON-LD通常包含主要产品图片
                                })
        except Exception as e:
            print(f"Error parsing JSON-LD: {e}")

    # 按评分排序潜在图片
    potential_images.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    # 限制返回的潜在图片数量，避免过多
    top_images = potential_images[:5] if len(potential_images) > 5 else potential_images
    
    return top_images


def get_image_selection_prompt(top_images, prompt_str):
    """
    生成用于让LLM选择主图的提示词
    
    :param top_images: 潜在主图列表
    :param prompt_str: 原始提示词
    :return: 增强的提示词
    """
    if not top_images:
        return prompt_str
        
    image_info = "\n\nPotential product images found (sorted by relevance):\n"
    for i, img in enumerate(top_images, 1):
        image_info += f"{i}. URL: {img['url']}\n"
        if 'alt' in img and img['alt']:
            image_info += f"   Alt: {img['alt']}\n"
        if 'dimensions' in img:
            image_info += f"   Dimensions: {img['dimensions']}\n"
        if 'source' in img:
            image_info += f"   Source: {img['source']}\n"
    
    return f"{prompt_str}\n{image_info}\nPlease determine which is the main product image and include it in your response as 'Main Image URL'."


def extract_main_content(html: str, base_url: str = "") -> tuple[str, str | None]:
    """
    提取页面主要内容和主图URL
    
    :param html: HTML内容
    :param base_url: 基础URL
    :return: (clean_text, main_image_url)
    """
    # 检查HTML是否是错误对象
    if isinstance(html, dict) and "error" in html:
        return f"Error: {html['error']} - {html.get('details', '')}", None
        
    # 1️⃣  解析 HTML（无 lxml 时自动降级）
    try:
        soup = BeautifulSoup(html, "lxml")
    except FeatureNotFound:
        soup = BeautifulSoup(html, "html.parser")
    
    # 2️⃣ 收集潜在的产品图片
    top_images = collect_potential_product_images(soup, base_url)
    
    # 选择评分最高的图片作为默认值
    img_url = top_images[0]["url"] if top_images else None
    
    # 3️⃣  清理无用标签
    for tag in soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()
    for tag in soup.select("[hidden], [aria-hidden='true'], [style*='display:none']"):
        tag.decompose()
    
    text = soup.get_text("\n", strip=True)
    return text, img_url


def select_main_image_with_llm(structured_data, top_images, main_image):
    """
    从LLM返回的结构化数据中提取或确认主图URL
    
    :param structured_data: LLM返回的结构化数据
    :param top_images: 潜在的主图列表
    :param main_image: 默认选择的主图URL
    :return: 最终确定的主图URL
    """
    if not isinstance(structured_data, list) or not structured_data:
        return main_image
        
    first_item = structured_data[0]
    
    # 检查常见的图片字段名
    image_field_names = [
        "Main Image URL", "main_image_url", "image_url", "imageUrl", 
        "MainImageURL", "product_image", "productImage", "image"
    ]
    
    for field in image_field_names:
        if field in first_item and first_item[field] and first_item[field] not in ["Not found", "Unavailable", "N/A", ""]:
            # 验证URL格式
            if re.match(r'^https?://', first_item[field]):
                return first_item[field]
    
    # 如果LLM没有返回有效的图片URL，使用默认的主图
    return main_image


def should_include_image(prompt_str):
    """
    根据提示词判断是否需要包含图片URL
    """
    if not prompt_str:
        return False
        
    # 图片相关关键词
    image_keywords = [
        "图片", "image", "picture", "photo", "img", "主图", 
        "图像", "url", "链接", "link", "src", "source", "图片链接",
        "主图url", "main image", "product image"
    ]
    
    prompt_lower = prompt_str.lower()
    
    # 检查提示词中是否包含图片相关关键词
    for keyword in image_keywords:
        if keyword.lower() in prompt_lower:
            return True
            
    return False


def process_product_url(url: str, prompt_str: str = None, llm_processor=None):
    """
    处理单个产品URL的函数
    
    :param url: 要处理的URL
    :param prompt_str: 提示词字符串
    :param llm_processor: LLM处理函数
    :return: 结构化数据或错误信息
    """
    # 检查是否提供了LLM处理器
    if llm_processor is None:
        return {"error": "LLM processor not provided"}
    
    # 根据提示词判断是否需要图片URL
    include_image = should_include_image(prompt_str)
    
    # 1. 使用scrape_url获取HTML内容
    html_content = scrape_url(url)
    if isinstance(html_content, dict) and "error" in html_content:
        return html_content
    
    if not html_content:
        return {"error": "Failed to fetch page content"}
    
    # 2. 从URL获取base_url并使用extract_main_content提取内容
    base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    
    # 解析HTML
    try:
        soup = BeautifulSoup(html_content, "lxml")
    except FeatureNotFound:
        soup = BeautifulSoup(html_content, "html.parser")
    
    # 收集潜在产品图片
    top_images = []
    if include_image:
        top_images = collect_potential_product_images(soup, base_url)
    
    # 提取正文和默认主图
    clean_text, main_image = extract_main_content(html_content, base_url)
    
    # 3. 创建增强的提示词，如果需要图片
    enhanced_prompt = prompt_str
    if include_image and top_images:
        enhanced_prompt = get_image_selection_prompt(top_images, prompt_str)
    
    # 4. 使用LLM处理器提取结构化数据
    structured_data = llm_processor(clean_text, enhanced_prompt)
    
    # 5. 处理图片字段
    if include_image and isinstance(structured_data, list) and len(structured_data) > 0:
        # 从LLM返回结果中确定主图
        final_image_url = select_main_image_with_llm(structured_data, top_images, main_image)
        
        # 更新结构化数据中的图片URL
        image_field = next((field for field in ["Main Image URL", "image_url", "image"] 
                         if field in structured_data[0]), "Main Image URL")
        structured_data[0][image_field] = final_image_url
    elif not include_image and isinstance(structured_data, list) and len(structured_data) > 0:
        # 如果不需要图片URL，移除图片相关字段
        for field in ["Main Image URL", "image_url", "image", "productImage", "main_image"]:
            if field in structured_data[0]:
                del structured_data[0][field]
    
    return structured_data

def worker(url_queue, results_list, prompt_str, llm_processor):
    """
    工作线程函数，从队列获取URL并处理
    
    :param url_queue: URL队列
    :param results_list: 结果列表
    :param prompt_str: 提示词
    :param llm_processor: LLM处理函数
    """
    while not url_queue.empty():
        try:
            # 从队列获取URL
            url = url_queue.get_nowait()
            
            # 使用process_product_url处理URL
            result = process_product_url(url, prompt_str, llm_processor)
            
            # 根据结果类型添加到结果列表
            if isinstance(result, dict) and "error" in result:
                results_list.append({
                    "url": url,
                    "status": "failed",
                    "error": result["error"],
                    "details": result.get("details", "")
                })
            else:
                results_list.append({
                    "url": url,
                    "status": "success",
                    "data": result
                })
            
        except queue.Empty:
            # 队列为空，退出循环
            break
        except Exception as e:
            # 处理过程中出现错误
            results_list.append({
                "url": url if 'url' in locals() else "unknown",
                "status": "failed",
                "error": str(e)
            })
        finally:
            if 'url' in locals():
                # 标记任务完成
                url_queue.task_done()

def analyze_fields_with_llm(prompt_str, llm_processor):
    """
    使用LLM分析提示词，确定需要提取的字段
    
    :param prompt_str: 用户的提示词
    :param llm_processor: LLM处理函数
    :return: 标准化的字段列表
    """
    field_analysis_prompt = f"""
    Based on this user instruction: "{prompt_str}", determine what fields/data should be extracted from product pages.
    Return ONLY a JSON array of field names that should be extracted. Example: ["name", "price", "description"]

    IMPORTANT: Keep field names simple, consistent, and in English. Use snake_case format.
    """
    
    # 调用LLM获取字段列表
    try:
        # 使用task参数调用LLM处理器
        response = llm_processor(field_analysis_prompt, prompt_str, task="analyze_fields")
        if isinstance(response, list) and len(response) > 0:
            # 如果响应是数组中的对象
            if isinstance(response[0], dict):
                # 尝试从中提取字段列表
                if "fields" in response[0]:
                    return response[0]["fields"]
                # 如果对象本身包含字段作为键
                return list(response[0].keys())
            # 如果是字符串列表
            elif isinstance(response[0], str):
                return response
        # 默认字段列表，如果无法从LLM获取
        return ["name", "price", "description", "delivery"]
    except Exception as e:
        print(f"Error analyzing fields: {e}")
        # 返回默认字段
        return ["name", "price", "description", "delivery"]

def normalize_result_fields(results, required_fields):
    """
    标准化结果中的字段，确保每个结果都有相同的字段
    
    :param results: 处理结果列表
    :param required_fields: 必须包含的字段列表
    :return: 标准化后的结果列表
    """
    # 创建标准字段映射
    field_mapping = {
        # 常见变种映射到标准字段
        "product_name": "name",
        "title": "name",
        "product": "name",
        "item_name": "name",
        
        "product_price": "price",
        "pricing": "price",
        "cost": "price",
        "value": "price",
        
        "product_description": "description",
        "details": "description",
        "desc": "description",
        "specifications": "description",
        "specs": "description",
        "detail": "description",
        
        "shipping": "delivery",
        "delivery_info": "delivery",
        "shipping_info": "delivery",
        "delivery_options": "delivery",
        "delivery_method": "delivery",
        
        "release_date": "delivery_in_days",
        "available_date": "delivery_in_days",
        "estimated_delivery": "delivery_in_days",
        "delivery_date": "delivery_in_days",
        "date": "delivery_in_days",
    }
    
    normalized_results = []
    for result in results:
        if result["status"] == "success" and "data" in result:
            # 处理data中的每个项目
            if isinstance(result["data"], list):
                normalized_data = []
                for item in result["data"]:
                    # 规范化当前项目的字段
                    normalized_item = {}
                    
                    # 将已有字段标准化
                    for key, value in item.items():
                        # 检查键是否在映射中，如果是则使用标准名称
                        standard_key = field_mapping.get(key.lower(), key)
                        normalized_item[standard_key] = value
                    
                    # 确保所有必需字段都存在
                    for field in required_fields:
                        if field not in normalized_item:
                            normalized_item[field] = None
                            
                    normalized_data.append(normalized_item)
                result["data"] = normalized_data
        normalized_results.append(result)
    
    return normalized_results

def process_batch_urls(urls, prompt_str=None, parallel_count=3, llm_processor=None):
    """
    批量处理URL
    
    :param urls: URL列表
    :param prompt_str: 提示词
    :param parallel_count: 并行处理数量
    :param llm_processor: LLM处理函数
    :return: 处理结果
    """
    if not llm_processor:
        return {"success": False, "error": {"code": "PROCESSOR_ERROR", "message": "LLM processor not provided"}}
    
    start_time = time.time()
    
    # 第1步：分析提示词，确定需要提取的字段
    required_fields = analyze_fields_with_llm(prompt_str, llm_processor)
    print(f"Required fields determined: {required_fields}")
    
    # 修改提示词，确保LLM提取所有必要字段
    enhanced_prompt = prompt_str
    if prompt_str:
        field_list = ", ".join(required_fields)
        enhanced_prompt = f"{prompt_str}. Make sure to extract these fields: {field_list}."
    
    # 创建URL队列
    url_queue = queue.Queue()
    for url in urls:
        url_queue.put(url)
    
    # 创建结果列表
    results = []
    
    # 创建并启动工作线程
    threads = []
    for _ in range(min(parallel_count, len(urls))):
        thread = threading.Thread(
            target=worker,
            args=(url_queue, results, enhanced_prompt, llm_processor)
        )
        threads.append(thread)
        thread.start()
    
    # 等待所有任务完成
    url_queue.join()
    
    # 标准化结果中的字段
    normalized_results = normalize_result_fields(results, required_fields)
    
    # 计算统计信息
    end_time = time.time()
    processing_time = round(end_time - start_time, 2)
    successful = sum(1 for r in normalized_results if r["status"] == "success")
    
    return {
        "total": len(urls),
        "successful": successful,
        "failed": len(urls) - successful,
        "results": normalized_results,
        "metadata": {
            "processing_time_seconds": processing_time,
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "required_fields": required_fields
        }
    }

# 测试代码，仅在直接运行文件时执行
if __name__ == "__main__":
    url = "https://www.coles.com.au/product/coles-broccoli-approx.-340g-each-407755"
    html = scrape_url(url)
    print(extract_main_content(html))
