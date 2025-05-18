"""
测试完整的数据处理流程
"""
import sys
import os
import json
from urllib.parse import urlparse

# 将当前目录添加到模块搜索路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.scraper import scrape_url, extract_main_content
from app.llm_processor import extract_data_with_llm

def process_product_url(url: str, prompt: str = None):
    """
    处理产品URL的完整流程
    
    工作流程：
    1. 使用Selenium获取页面内容
    2. 使用BeautifulSoup提取主要内容和图片
    3. 使用LLM提取结构化数据
    
    :param url: 产品页面URL
    :param prompt: 可选的LLM提示，用于指定要提取的信息
    :return: 提取的结构化数据
    """
    print(f"\n{'='*60}")
    print(f"处理URL: {url}")
    print(f"{'='*60}")
    
    # 1. 使用Selenium获取页面内容
    print("\n1. 正在获取页面内容...")
    html_content = scrape_url(url)
    if not html_content:
        return {"error": "Failed to fetch page content"}
    
    # 2. 提取主要内容和图片
    print("\n2. 正在提取主要内容...")
    base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    clean_text, main_image = extract_main_content(html_content, base_url)
    
    print(f"- 提取的文本长度: {len(clean_text)} 字符")
    print(f"- 主图URL: {main_image}")
    
    # 3. 使用LLM提取结构化数据
    print("\n3. 使用LLM提取结构化数据...")
    if not prompt:
        prompt = """
        从产品页面提取以下信息：
        - 产品名称 (Product Name)
        - 价格 (Price)
        - 描述 (Description)
        - 主图URL (Main Image URL)
        
        以JSON数组格式返回数据。
        """
    
    structured_data = extract_data_with_llm(clean_text, prompt)
    
    # 4. 如果LLM没有提取到图片URL，使用我们之前提取的
    if isinstance(structured_data, list) and len(structured_data) > 0:
        if structured_data[0].get("Main Image URL") in ["Not found", "Unavailable", None, ""]:
            structured_data[0]["Main Image URL"] = main_image
    
    print("\n4. 提取结果:")
    print(json.dumps(structured_data, indent=2, ensure_ascii=False))
    
    return structured_data

def test_multiple_sites():
    """测试多个不同网站的产品页面"""
    test_urls = [
        # BigW
        "https://www.bigw.com.au/product/pigeon-flexible-bottle-240ml-2-pack/p/744923",
        
        # Woolworths
        "https://www.woolworths.com.au/shop/productdetails/33557/devondale-100-pure-full-cream-long-life-milk-uht",
        
        # 添加更多测试URL...
    ]
    
    results = []
    for url in test_urls:
        result = process_product_url(url)
        results.append({
            "url": url,
            "data": result
        })
    
    # 保存结果到文件
    with open("test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n所有测试结果已保存到 test_results.json")

if __name__ == "__main__":
    # 1. 测试单个URL
    url = "https://www.bigw.com.au/product/pigeon-flexible-bottle-240ml-2-pack/p/744923"
    result = process_product_url(url)
    
    # 2. 测试多个网站
    # test_multiple_sites() 