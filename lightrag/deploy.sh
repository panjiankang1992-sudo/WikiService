#!/bin/bash
# WikiService 部署脚本
# 将当前开发目录同步到部署目录
# 用法: ./deploy.sh

set -e

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_DIR="/opt/yuyutian/WikiService"
LOG_DIR="/opt/yuyutian/logs/WikiService"
DEPLOY_PORT="${PORT:-23100}"

echo "=== WikiService Deploy ==="
echo "Source:  $SRC_DIR"
echo "Deploy:  $DEPLOY_DIR"
echo "Port:    $DEPLOY_PORT"
echo ""

# 1. 同步代码（排除 .venv/data/logs 等运行时生成的文件）
rsync -av --exclude='.venv' --exclude='data' --exclude='__pycache__' --exclude='.DS_Store' \
    "$SRC_DIR/" "$DEPLOY_DIR/"

# 2. 确保持久化数据不被覆盖（data 目录独立于代码）
if [ ! -d "$DEPLOY_DIR/data" ]; then
    mkdir -p "$DEPLOY_DIR/data"
fi

# 3. 确保日志目录存在
mkdir -p "$LOG_DIR"

echo ""
echo "=== 同步完成 ==="
echo "日志文件: $LOG_DIR/wikiservice_${DEPLOY_PORT}.log"
echo ""
echo "启动服务:"
echo "  cd $DEPLOY_DIR && PORT=$DEPLOY_PORT DEEPSEEK_API_KEY=xxx .venv/bin/python app.py"
