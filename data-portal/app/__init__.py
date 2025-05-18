from flask import Flask
from flask_cors import CORS

def create_app():
    app = Flask(__name__)
    
    # 配置CORS，允许前端访问
    CORS(app, resources={
        r"/*": {
            "origins": [
                "http://localhost:5173",  # 开发服务器
                "http://127.0.0.1:5173"   # 可选的别名
            ],
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    
    from .routes import main
    app.register_blueprint(main)

    return app 