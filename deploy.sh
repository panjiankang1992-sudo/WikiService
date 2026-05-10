#!/bin/bash
# WikiService Remote Deployment Script
# Usage: Run this on the remote Linux server (192.168.1.9)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration
FRONTEND_PORT=29215
API_PORT=29216
NEO4J_HTTP_PORT=29217
NEO4J_BOLT_PORT=29218
DB_PORT=29219

echo "==================================="
echo "  WikiService Linux Deployment"
echo "==================================="
echo ""

# Check prerequisites
check_prereqs() {
    echo_info "Checking prerequisites..."

    if ! command -v docker &> /dev/null; then
        echo_error "Docker is not installed"
        echo "Install Docker:"
        echo "  curl -fsSL https://get.docker.com | sh"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        echo_warn "docker-compose not found, trying docker compose..."
        if ! docker compose version &> /dev/null; then
            echo_error "Neither docker-compose nor docker compose found"
            exit 1
        fi
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi

    echo_info "Docker: $(docker --version)"
    echo_info "Docker Compose: $($COMPOSE_CMD --version)"
}

# Create .env file
create_env() {
    echo_info "Creating .env file..."

    cat > .env << 'ENVEOF'
# Database
DB_PASSWORD=weknora_secure_db_pwd_2026

# Neo4j
NEO4J_PASSWORD=weknora_secure_neo4j_pwd_2026

# Embedding Model - DeepSeek
EMBEDDING_PROVIDER=deepseek
EMBEDDING_API_BASE=https://api.deepseek.com
EMBEDDING_API_KEY=sk-9538d57105d14bb194708e629c36ad74
EMBEDDING_MODEL=deepseek-chat

# WeKnora
WEKNORA_KB_ID=kb_default
ENVEOF

    echo_info ".env file created at $SCRIPT_DIR/.env"
}

# Update docker-compose for custom ports
update_compose() {
    echo_info "Updating docker-compose for custom ports..."

    # Create a modified docker-compose file with custom ports
    cat > docker-compose.linux.yml << 'COMPOSEEOF'
# WikiService Docker Compose - Linux Production Deployment
# Ports: 29215+ (to avoid conflicts)

services:
  weknora-api:
    image: weknora/weknora:latest
    container_name: weknora-api
    restart: unless-stopped
    ports:
      - "29216:8080"
    environment:
      - DB_DRIVER=postgres
      - DB_HOST=postgres
      - DB_PORT=5432
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
      - weknora_storage:/data/storage
    depends_on:
      postgres:
        condition: service_healthy
      neo4j:
        condition: service_healthy
    networks:
      - weknora-network

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
      - weknora-network

  postgres:
    image: pgvector/pgvector:pg16
    container_name: weknora-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: weknora
      POSTGRES_USER: weknora
      POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./docker/init-db.sql:/docker-entrypoint-initdb.d/init.sql:ro
    ports:
      - "29219:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U weknora -d weknora"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - weknora-network

  neo4j:
    image: neo4j:5.26-community
    container_name: weknora-neo4j
    restart: unless-stopped
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
      NEO4J_PLUGINS: ["apoc"]
    ports:
      - "29217:7474"
      - "29218:7687"
    volumes:
      - neo4jdata:/data
    healthcheck:
      test: ["CMD-SHELL", "wget -q -O - http://localhost:7474 || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - weknora-network

  crawler:
    build:
      context: ./crawler
      dockerfile: Dockerfile
    container_name: weknora-crawler
    restart: unless-stopped
    environment:
      - WEKNORA_API_URL=http://weknora-api:8080
      - WEKNORA_KB_ID=${WEKNORA_KB_ID}
    volumes:
      - ./crawler/sources.yaml:/app/sources.yaml:ro
      - crawler_data:/data
    depends_on:
      - weknora-api
    networks:
      - weknora-network

  scheduler:
    build:
      context: ./scheduler
      dockerfile: Dockerfile
    container_name: weknora-scheduler
    restart: unless-stopped
    environment:
      - WEKNORA_API_URL=http://weknora-api:8080
    volumes:
      - ./scheduler/config.yaml:/app/config.yaml:ro
      - ./ingester:/app/ingester:ro
      - scheduler_data:/data
    depends_on:
      - weknora-api
      - crawler
    networks:
      - weknora-network

volumes:
  pgdata:
  neo4jdata:
  weknora_storage:
  crawler_data:
  scheduler_data:

networks:
  weknora-network:
    driver: bridge
COMPOSEEOF

    echo_info "Created docker-compose.linux.yml with custom ports"
}

# Start services
start_services() {
    echo_info "Starting services..."

    $COMPOSE_CMD -f docker-compose.linux.yml up -d

    echo_info "Waiting for services to start (this may take 2-3 minutes)..."
    sleep 30

    # Check service status
    echo ""
    echo_info "Service Status:"
    $COMPOSE_CMD -f docker-compose.linux.yml ps

    echo ""
    echo "==================================="
    echo "  Deployment Complete!"
    echo "==================================="
    echo ""
    echo "Access URLs:"
    echo "  WeKnora UI:   http://192.168.1.9:29215"
    echo "  WeKnora API:  http://192.168.1.9:29216"
    echo "  Neo4j Browser:http://192.168.1.9:29217"
    echo ""
    echo "Default credentials:"
    echo "  WeKnora UI:   admin / admin"
    echo "  Neo4j:        neo4j / (your NEO4J_PASSWORD)"
    echo ""
    echo "Next steps:"
    echo "  1. Visit http://192.168.1.9:29215"
    echo "  2. Login and change default password"
    echo "  3. Configure your data sources"
    echo ""
    echo "Useful commands:"
    echo "  View logs:     $COMPOSE_CMD -f docker-compose.linux.yml logs -f"
    echo "  Stop services: $COMPOSE_CMD -f docker-compose.linux.yml down"
    echo "  Restart:       $COMPOSE_CMD -f docker-compose.linux.yml restart"
}

# Main
main() {
    check_prereqs
    create_env
    update_compose
    start_services
}

main "$@"
