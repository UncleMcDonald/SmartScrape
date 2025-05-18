import os

import openai
import json
import re
from .config import OPENAI_API_KEY

# 清除可能存在的代理设置环境变量
if "OPENAI_PROXY" in os.environ:
    del os.environ["OPENAI_PROXY"]
if "HTTPS_PROXY" in os.environ:
    del os.environ["HTTPS_PROXY"]
if "HTTP_PROXY" in os.environ:
    del os.environ["HTTP_PROXY"]

# 初始化OpenAI客户端，只使用api_key参数
client = openai.OpenAI(api_key=OPENAI_API_KEY)

def extract_data_with_llm(html, prompt):
    full_prompt = f"""You are given a product page's raw HTML. 
Based on this instruction: "{prompt}", extract relevant data and return it in JSON array format.

IMPORTANT RULES:
1. You MUST ONLY respond with a valid JSON array format.
2. If you can't extract the data, return an array with an error object: [{{"error": "Unable to extract data", "reason": "Your reason here"}}]
3. Make sure to properly escape all special characters in the JSON.

HTML:
{html[:3000]}  # truncated to avoid GPT overload
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": full_prompt}]
    )
    
    content = response.choices[0].message.content
    # 尝试提取JSON部分
    json_match = re.search(r'(\[.*\])', content, re.DOTALL)
    if json_match:
        content = json_match.group(1)
    
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        print(f"Response content: {content}")
        # 返回结构化错误响应
        return [{"error": "Unable to parse JSON response", "reason": "Invalid format from LLM"}] 