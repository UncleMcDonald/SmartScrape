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

# 默认环境设置
# 将此设置为False可以在本地开发中禁用内存优化
# 可以通过环境变量覆盖此设置：export USE_PRODUCTION_OPTIMIZATIONS=false
USE_PRODUCTION_OPTIMIZATIONS = os.getenv('USE_PRODUCTION_OPTIMIZATIONS', 'false').lower() in ['true', '1', 'yes', 'y']

# 每批处理的最大URL数量
MAX_BATCH_SIZE = int(os.getenv('MAX_BATCH_SIZE', '50'))

# Selenium超时设置(秒)
SELENIUM_TIMEOUT = int(os.getenv('SELENIUM_TIMEOUT', '30'))

# 用于测试的默认URL
DEFAULT_TEST_URL = "https://www.amazon.com/dp/B08L5TNJHG"
