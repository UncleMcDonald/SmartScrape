from flask import Flask
from flask_cors import CORS
import gc
import logging

def create_app():
    # 创建应用前主动回收内存
    gc.collect()
    
    # 减少日志级别以减少I/O和内存使用
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    
    # 使用精简配置创建Flask应用
    app = Flask(__name__, 
                static_folder='../static',  # 显式定义静态文件夹位置
                template_folder='../templates',  # 显式定义模板文件夹位置
                instance_relative_config=True)
    
    # 关闭不必要的调试功能减少内存使用
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
    app.config['TEMPLATES_AUTO_RELOAD'] = False
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 604800  # 1周缓存
    
    # 配置CORS，允许前端访问
    CORS(app, resources={
        r"/*": {
            "origins": [
                "http://localhost:5173",    # 本地开发服务器
                "http://127.0.0.1:5173",    # 本地开发别名
                "https://smart-scrape-five.vercel.app",  # Vercel部署的前端应用
                "https://smart-scrape.vercel.app",       # 可能的别名域名
                "https://*.vercel.app"                   # 所有vercel子域名（开发/预览环境）
            ],
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"]
        }
    })
    
    from .routes import main
    app.register_blueprint(main)
    
    # 注册清理内存的请求后处理器
    @app.after_request
    def cleanup(response):
        # 在每个请求后主动请求垃圾回收
        gc.collect()
        return response

    return app 