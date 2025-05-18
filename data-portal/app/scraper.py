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
    """获取Chrome配置，可选指定User-Agent"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 无头模式
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # 随机或指定User-Agent
    if user_agent is None:
        user_agent = generate_random_user_agent()
    chrome_options.add_argument(f"--user-agent={user_agent}")
    
    # 禁用自动化标志
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
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

def extract_main_content(html: str, base_url: str = "") -> tuple[str, str | None]:
    """
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

    # 2️⃣  抓主图 URL —— 先 og:image，再 img，再 JSON-LD
    img_url = None

    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        img_url = urljoin(base_url, og["content"])

    if not img_url:
        # 选最大尺寸或 alt 含商品名的一张
        best, best_score = None, -1
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if not src:
                continue
            w = int(img.get("width") or 0)
            h = int(img.get("height") or 0)
            score = w * h                     # 简单面积评分
            if score > best_score:
                best, best_score = src, score
        if best:
            img_url = urljoin(base_url, best)

    if not img_url:
        ld = soup.find("script", type="application/ld+json")
        if ld and ld.string and '"image"' in ld.string:
            import json, re
            try:
                data = json.loads(re.sub(r"<!--.*?-->", "", ld.string, flags=re.S))
                if isinstance(data, dict) and data.get("image"):
                    img = data["image"]
                    img_url = img[0] if isinstance(img, list) else img
            except:
                pass

    # 3️⃣  清理无用标签
    for tag in soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()
    for tag in soup.select("[hidden], [aria-hidden='true'], [style*='display:none']"):
        tag.decompose()

    text = soup.get_text("\n", strip=True)
    return text, img_url

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
    clean_text, main_image = extract_main_content(html_content, base_url)
    
    # 3. 使用LLM处理器提取结构化数据
    structured_data = llm_processor(clean_text, prompt_str)
    
    # 4. 根据提示词决定是否保留图片URL
    if isinstance(structured_data, list) and len(structured_data) > 0:
        # 如果不需要图片URL，从结果中移除
        if not include_image and "Main Image URL" in structured_data[0]:
            del structured_data[0]["Main Image URL"]
        # 如果需要图片URL但LLM未提取到，使用我们提取的
        elif include_image and structured_data[0].get("Main Image URL") in ["Not found", "Unavailable", None, ""]:
            if main_image:
                structured_data[0]["Main Image URL"] = main_image
    
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
            args=(url_queue, results, prompt_str, llm_processor)
        )
        threads.append(thread)
        thread.start()
    
    # 等待所有任务完成
    url_queue.join()
    
    # 计算统计信息
    end_time = time.time()
    processing_time = round(end_time - start_time, 2)
    successful = sum(1 for r in results if r["status"] == "success")
    
    return {
        "total": len(urls),
        "successful": successful,
        "failed": len(urls) - successful,
        "results": results,
        "metadata": {
            "processing_time_seconds": processing_time,
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    }

# 测试代码，仅在直接运行文件时执行
if __name__ == "__main__":
    url = "https://www.coles.com.au/product/coles-broccoli-approx.-340g-each-407755"
    html = scrape_url(url)
    print(extract_main_content(html))
