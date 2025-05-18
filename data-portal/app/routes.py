from flask import Blueprint, request, jsonify, send_file
from .scraper import scrape_url, extract_main_content, process_product_url, process_batch_urls
from .llm_processor import extract_data_with_llm
from .config import USE_PRODUCTION_OPTIMIZATIONS
# Remove save_to_csv as it's not used in the new batch endpoint logic directly
# from .exporter import save_to_csv 
# Instead, if export is needed, it would be part of process_product_url_for_api or a separate step
import uuid
import os
import time

main = Blueprint('main', __name__)

@main.route('/process', methods=['POST'])
def process():
    data = request.json
    url = data.get('url')
    prompt = data.get('prompt')  # 用户的自然语言提示
    is_production = data.get('is_production')  # 如果提供了明确的环境设置，则使用它

    if not url:
        return jsonify({'success': False, 'error': {'code': 'INVALID_INPUT', 'message': 'URL is required'}}), 400

    # 确保prompt是字符串或None
    if prompt is not None and not isinstance(prompt, str):
        prompt = str(prompt)  # 尝试转换为字符串

    try:
        # 打印当前环境模式
        env_mode = "default" if is_production is None else ("production" if is_production else "local")
        print(f"[API] Processing URL in {env_mode} mode, USE_PRODUCTION_OPTIMIZATIONS={USE_PRODUCTION_OPTIMIZATIONS}")
        
        # 使用用户提供的自然语言prompt直接调用处理函数
        result_data = process_product_url(url, prompt, extract_data_with_llm, is_production)
        
        if isinstance(result_data, dict) and "error" in result_data:
            return jsonify({"success": False, "error": {"code": "PROCESSING_ERROR", "message": result_data.get("error"), "url": url }}), 500
        return jsonify({"success": True, "data": result_data})
    except Exception as e:
        return jsonify({"success": False, "error": {"code": "INTERNAL_ERROR", "message": str(e), "url": url}}), 500

@main.route('/api/batch-process', methods=['POST'])
def batch_process():
    request_start_time = time.time()
    data = request.json

    urls = data.get('urls')
    prompt = data.get('prompt')  # 用户的自然语言提示
    options = data.get('options', {})
    is_production = options.get('is_production')  # 如果在options中明确提供了环境设置

    if not urls or not isinstance(urls, list):
        return jsonify({"success": False, "error": {"code": "INVALID_INPUT", "message": "Missing or invalid 'urls' list"}}), 400

    # 确保prompt是字符串或None
    if prompt is not None and not isinstance(prompt, str):
        prompt = str(prompt)  # 尝试转换为字符串
            
    parallel_count = options.get('parallel', 3)
    if not isinstance(parallel_count, int) or parallel_count <= 0:
        parallel_count = 3  # 默认为3，如果无效
    
    # 打印当前环境模式
    env_mode = "default" if is_production is None else ("production" if is_production else "local")
    print(f"[API] Batch processing {len(urls)} URLs in {env_mode} mode, USE_PRODUCTION_OPTIMIZATIONS={USE_PRODUCTION_OPTIMIZATIONS}")

    # 调用scraper模块中的批处理函数，直接传递用户提供的自然语言prompt
    result = process_batch_urls(
        urls=urls,
        prompt_str=prompt,
        parallel_count=parallel_count,
        llm_processor=extract_data_with_llm,
        is_production=is_production
    )
    
    # 如果process_batch_urls返回错误信息
    if isinstance(result, dict) and result.get("success") is False:
        return jsonify(result), 500
    
    # 构建成功响应
    response_payload = {
        "success": True,
        "data": {
            **result,  # 解包result字典
            "metadata": {
                **result.get("metadata", {}),  # 保留原始元数据
                "batch_id": f"batch_{uuid.uuid4()}",  # 添加批处理ID
                "optimization_mode": result.get("metadata", {}).get("environment", "unknown")  # 添加优化模式信息
            }
        }
    }
    
    return jsonify(response_payload)

@main.route('/download/<filename>')
def download(filename):
    # 确保路径安全，防止目录遍历
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))
    file_path = os.path.abspath(os.path.join(static_dir, filename))
    
    if not file_path.startswith(static_dir):
        return jsonify({"error": "Invalid path"}), 400
        
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
        
    return send_file(file_path, as_attachment=True) 