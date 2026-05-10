#!/bin/bash
# WikiService 快速部署脚本
# 用法：在服务器上下载此脚本并执行

set -e

echo "=========================================="
echo "  WikiService 一键部署脚本"
echo "=========================================="
echo ""

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker 未安装!"
    echo "请先安装 Docker: curl -fsSL https://get.docker.com | sh"
    exit 1
fi

echo "[OK] Docker 已安装: $(docker --version)"

# 检查 docker-compose
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo "[ERROR] docker-compose 未安装!"
    exit 1
fi
echo "[OK] Docker Compose: $($COMPOSE_CMD --version)"
echo ""

# 创建目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 创建 .env 文件
echo "创建配置文件..."
cat > .env << 'ENVEOF'
DB_PASSWORD=weknora_secure_db_pwd_2026
NEO4J_PASSWORD=weknora_secure_neo4j_pwd_2026
EMBEDDING_PROVIDER=deepseek
EMBEDDING_API_BASE=https://api.deepseek.com
EMBEDDING_API_KEY=sk-9538d57105d14bb194708e629c36ad74
EMBEDDING_MODEL=deepseek-chat
WEKNORA_KB_ID=kb_default
ENVEOF

echo "[OK] .env 文件已创建"

# 创建 docker-compose 文件
echo "创建 Docker Compose 配置..."
cat > docker-compose.deploy.yml << 'COMPOSEEOF'
version: '3.8'

services:
  weknora-ui:
    image: weknora/weknora-ui:latest
    container_name: weknora-ui
    restart: unless-stopped
    ports:
      - "29215:80"
    environment:
      - WEKNORA_API_URL=http://weknora-api:8080
    depends_on:
      - weknora-api
    networks:
      - weknora-net

  weknora-api:
    image: weknora/weknora:latest
    container_name: weknora-api
    restart: unless-stopped
    ports:
      - "29216:8080"
    environment:
      - DB_DRIVER=postgres
      - DB_HOST=postgres
      - DB_NAME=weknora
      - DB_USER=weknora
      - DB_PASSWORD=${DB_PASSWORD}
      - VECTOR_STORE=pgvector
      - EMBEDDING_PROVIDER=${EMBEDDING_PROVIDER}
      - EMBEDDING_API_BASE=${EMBEDDING_API_BASE}
      - EMBEDDING_API_KEY=${EMBEDDING_API_KEY}
      - EMBEDDING_MODEL=${EMBEDDING_MODEL}
      - NEO4J_ENABLED=true
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
    volumes:
      - weknora-data:/data
    depends_on:
      - postgres
      - neo4j
    networks:
      - weknora-net

  postgres:
    image: pgvector/pgvector:pg16
    container_name: weknora-db
    restart: unless-stopped
    ports:
      - "29219:5432"
    environment:
      POSTGRES_DB: weknora
      POSTGRES_USER: weknora
      POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - pg-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U weknora -d weknora"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - weknora-net

  neo4j:
    image: neo4j:5.26-community
    container_name: weknora-neo4j
    restart: unless-stopped
    ports:
      - "29217:7474"
      - "29218:7687"
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
      NEO4J_PLUGINS: ["apoc"]
    volumes:
      - neo4j-data:/data
    healthcheck:
      test: ["CMD-SHELL", "wget -q -O - http://localhost:7474 || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - weknora-net

  crawler:
    build: ./crawler
    container_name: weknora-crawler
    restart: unless-stopped
    environment:
      - WEKNORA_API_URL=http://weknora-api:8080
      - WEKNORA_KB_ID=${WEKNORA_KB_ID}
    volumes:
      - ./crawler/sources.yaml:/app/sources.yaml:ro
      - crawler-data:/data
    depends_on:
      - weknora-api
    networks:
      - weknora-net

  scheduler:
    build: ./scheduler
    container_name: weknora-scheduler
    restart: unless-stopped
    environment:
      - WEKNORA_API_URL=http://weknora-api:8080
    volumes:
      - ./scheduler/config.yaml:/app/config.yaml:ro
      - ./ingester:/app/ingester:ro
    depends_on:
      - weknora-api
    networks:
      - weknora-net

volumes:
  weknora-data:
  pg-data:
  neo4j-data:
  crawler-data:

networks:
  weknora-net:
    driver: bridge
COMPOSEEOF

echo "[OK] docker-compose.deploy.yml 已创建"
echo ""

# 拉取镜像
echo "开始拉取 Docker 镜像 (可能需要几分钟)..."
docker pull weknora/weknora:latest || echo "警告：WeKnora 镜像拉取失败，可能需要使用替代镜像"
docker pull weknora/weknora-ui:latest || echo "警告：WeKnora UI 镜像拉取失败"
docker pull pgvector/pgvector:pg16
docker pull neo4j:5.26-community

echo ""
echo "启动服务..."
$COMPOSE_CMD -f docker-compose.deploy.yml up -d

echo ""
echo "等待服务启动..."
sleep 15

echo ""
echo "=========================================="
echo "  部署完成!"
echo "=========================================="
echo ""
echo "服务访问地址:"
echo "  WeKnora UI:   http://$(hostname -I | awk '{print $1}'):29215"
echo "  WeKnora API:  http://$(hostname -I | awk '{print $1}'):29216"
echo "  Neo4j Browser:http://$(hostname -I | awk '{print $1}'):29217"
echo ""
echo "默认账号:"
echo "  WeKnora UI: admin / admin (首次登录请修改)"
echo ""
echo "查看日志：$COMPOSE_CMD -f docker-compose.deploy.yml logs -f"
echo "停止服务：$COMPOSE_CMD -f docker-compose.deploy.yml down"
echo ""
