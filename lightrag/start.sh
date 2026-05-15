#!/bin/bash
# WikiService 开发启动脚本
# 用法: ./start.sh [端口]

cd "$(dirname "$0")"
PORT="${1:-8080}"
STORAGE_PATH="$(pwd)/data"
export STORAGE_PATH
export DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-test}"
export PORT

echo "Starting WikiService (dev mode)"
echo "Port:     $PORT"
echo "Storage:  $STORAGE_PATH"
echo ""

.venv/bin/python app.py
