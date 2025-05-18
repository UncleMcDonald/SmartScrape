from flask import Flask
from flask_cors import CORS

def create_app():
    app = Flask(__name__)
    
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

    return app 