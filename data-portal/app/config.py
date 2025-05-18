import os

# 优先从环境变量获取API密钥
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# 应用配置
DEBUG = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "t")
ENV = os.getenv("FLASK_ENV", "development")

# LLM配置
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))

# 并行处理配置
DEFAULT_PARALLEL_COUNT = int(os.getenv("DEFAULT_PARALLEL_COUNT", "3"))

# 超时设置（秒）
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

# 日志级别
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
