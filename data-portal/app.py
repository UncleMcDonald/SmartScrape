import os
from dotenv import load_dotenv
from app import create_app

# 加载环境变量
load_dotenv()

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug) 