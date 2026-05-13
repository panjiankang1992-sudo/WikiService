#!/bin/bash
# WikiService LightRAG - Start Script
# Usage: ./start-lightrag.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check Docker
if ! command -v docker &> /dev/null && ! command -v docker-compose &> /dev/null; then
    echo_error "Docker is not installed or not in PATH."
    echo_error "Install Docker Desktop from: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

# Determine docker compose command
if command -v docker &> /dev/null; then
    DOCKER_CMD="docker"
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_CMD="docker-compose"
    COMPOSE_CMD="docker-compose"
else
    echo_error "Neither 'docker' nor 'docker-compose' found."
    exit 1
fi

# Check environment file
if [ ! -f ".env.lightrag" ]; then
    echo_warn ".env.lightrag not found. Creating from example..."
    cp .env.lightrag.example .env.lightrag 2>/dev/null || true
    echo_warn "Please edit .env.lightrag and set DEEPSEEK_API_KEY"
    echo_warn "Get your key from: https://platform.deepseek.com/"
    exit 1
fi

# Verify API key is set
if grep -q "your_deepseek_api_key_here" .env.lightrag; then
    echo_error "DEEPSEEK_API_KEY is not configured in .env.lightrag"
    echo_error "Get your key from: https://platform.deepseek.com/"
    exit 1
fi

echo_info "Starting WikiService LightRAG..."

# Build image
echo_info "Building Docker image..."
$COMPOSE_CMD -f docker-compose.lightrag.yml build

# Start container
echo_info "Starting container..."
$COMPOSE_CMD -f docker-compose.lightrag.yml up -d

# Wait for health check
echo_info "Waiting for service to be ready..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
        echo_info "WikiService LightRAG is up!"
        break
    fi
    echo -n "."
    sleep 2
done
echo ""

echo ""
echo_info "Service Status:"
$COMPOSE_CMD -f docker-compose.lightrag.yml ps
echo ""
echo_info "Access URLs:"
echo "  Web UI:    http://localhost:8080"
echo "  Health:    http://localhost:8080/health"
echo "  API Docs:  http://localhost:8080/"
echo ""
echo_info "Logs: $COMPOSE_CMD -f docker-compose.lightrag.yml logs -f"
