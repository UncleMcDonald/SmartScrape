#!/bin/bash
# 启动生产环境服务器

# 加载环境变量
if [ -f .env ]; then
  export $(cat .env | grep -v '#' | sed 's/\r$//' | awk '/=/ {print $1}')
fi

# 设置默认值
PORT=${PORT:-5000}
WORKERS=${WORKERS:-2}
THREADS=${THREADS:-8}

echo "Starting server on port $PORT with $WORKERS workers and $THREADS threads"
gunicorn --bind 0.0.0.0:$PORT --workers=$WORKERS --threads=$THREADS 'app:app' 