#!/bin/bash
# offline-deploy.sh — WikiService 单机离线部署脚本
# 用法: ./offline-deploy.sh [PORT] [STORAGE_PATH]
#
# 前提条件（仅首次需要联网）:
#   1. 安装 Ollama: https://ollama.com
#   2. 下载模型: ollama pull nomic-embed-text
#   3. 启动 Ollama: ollama serve

set -e

cd "$(dirname "$0")"

# ===== 配置（可通过环境变量覆盖）=====
PORT="${1:-${PORT:-23100}}"
STORAGE="${2:-${STORAGE_PATH:-./data}}"
LOG_DIR="${LOG_DIR:-./logs}"
OLLAMA_URL="${EMBEDDING_BASE_URL:-http://localhost:11434}"

echo "=========================================="
echo " WikiService 离线部署"
echo "=========================================="
echo "  端口:       $PORT"
echo "  数据目录:   $STORAGE"
echo "  日志目录:   $LOG_DIR"
echo "  Ollama:     $OLLAMA_URL"
echo ""

# ===== 步骤 1: 检查 Ollama =====
echo "[1/4] 检查 Ollama..."
if ! curl -s --max-time 3 "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
    echo "ERROR: Ollama 未运行"
    echo "请先启动 Ollama:"
    echo "  1. ollama serve"
    echo "  2. ollama pull nomic-embed-text  # 仅首次需要联网"
    exit 1
fi
echo "  ✓ Ollama 运行正常"

# ===== 步骤 2: 检查模型 =====
echo ""
echo "[2/4] 检查 Embedding 模型..."
if ! ollama list 2>/dev/null | grep -q nomic-embed-text; then
    echo "ERROR: nomic-embed-text 模型未安装"
    echo "请运行: ollama pull nomic-embed-text"
    exit 1
fi
echo "  ✓ nomic-embed-text 已就绪"

# ===== 步骤 3: 安装依赖 =====
echo ""
echo "[3/4] 检查 Python 依赖..."
if [ ! -d ".venv" ]; then
    echo "  创建虚拟环境..."
    python3 -m venv .venv
fi
.venv/bin/pip install flask flask-cors httpx beautifulsoup4 lxml -q
echo "  ✓ 依赖就绪"

# ===== 步骤 4: 启动服务 =====
echo ""
echo "[4/4] 启动 WikiService..."
mkdir -p "$STORAGE" "$LOG_DIR"

export PORT
export STORAGE_PATH="$STORAGE"
export LOG_DIR="$LOG_DIR"
export DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-offline-placeholder}"
export EMBEDDING_PROVIDER=ollama
export EMBEDDING_MODEL=nomic-embed-text
export EMBEDDING_BASE_URL="$OLLAMA_URL"

PID_FILE="/tmp/wikiservice_${PORT}.pid"

# 如果已有进程在运行，先停止
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "  停止旧进程 (PID $OLD_PID)..."
        kill "$OLD_PID" || true
        sleep 1
    fi
    rm -f "$PID_FILE"
fi

.venv/bin/python app.py > "$LOG_DIR/wikiservice_${PORT}.log" 2>&1 &
NEW_PID=$!
echo $NEW_PID > "$PID_FILE"

sleep 2

if kill -0 "$NEW_PID" 2>/dev/null; then
    echo ""
    echo "=========================================="
    echo " ✓ WikiService 已启动"
    echo ""
    echo "  访问地址: http://localhost:$PORT"
    echo "  健康检查: http://localhost:$PORT/health"
    echo "  日志文件: $LOG_DIR/wikiservice_${PORT}.log"
    echo "  进程 PID: $NEW_PID"
    echo "=========================================="
else
    echo "ERROR: 服务启动失败，查看日志:"
    tail -20 "$LOG_DIR/wikiservice_${PORT}.log"
    exit 1
fi
