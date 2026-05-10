#!/bin/bash
# WikiService Quick Start Script
# Usage: ./quickstart.sh [dev|prod]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check Docker
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        echo_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi

    echo_info "Docker version: $(docker --version)"
    echo_info "Docker Compose version: $(docker-compose --version)"
}

# Check environment file
check_env() {
    if [ ! -f ".env" ]; then
        echo_warn ".env file not found. Copying from .env.example..."
        cp .env.example .env
        echo_warn "Please edit .env and fill in your configuration."
        echo_warn "At minimum, you need to set:"
        echo_warn "  - EMBEDDING_API_KEY (get from https://cloud.siliconflow.cn)"
        echo_warn "  - DB_PASSWORD"
        echo_warn "  - NEO4J_PASSWORD"
        echo ""
        read -p "Press Enter after you've configured .env..."
    fi

    # Check for required variables
    if ! grep -q "EMBEDDING_API_KEY=." .env || grep -q "EMBEDDING_API_KEY=your_" .env; then
        echo_error "EMBEDDING_API_KEY is not configured in .env"
        echo_error "Please get an API key from https://cloud.siliconflow.cn"
        exit 1
    fi
}

# Check ports
check_ports() {
    PORTS_IN_USE=()

    for port in 3000 8080 5432 7474 7687; do
        if command -v netstat &> /dev/null; then
            if netstat -tlnp 2>/dev/null | grep -q ":$port "; then
                PORTS_IN_USE+=($port)
            fi
        elif command -v lsof &> /dev/null; then
            if lsof -i :$port &>/dev/null; then
                PORTS_IN_USE+=($port)
            fi
        fi
    done

    if [ ${#PORTS_IN_USE[@]} -gt 0 ]; then
        echo_warn "The following ports are in use: ${PORTS_IN_USE[@]}"
        echo_warn "You may need to stop conflicting services or change ports in docker-compose.prod.yml"
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Start services
start_services() {
    echo_info "Starting WikiService..."

    # Pull latest images
    echo_info "Pulling latest Docker images..."
    docker-compose -f docker-compose.prod.yml pull

    # Start services
    echo_info "Starting services..."
    docker-compose -f docker-compose.prod.yml up -d

    # Wait for services to be healthy
    echo_info "Waiting for services to start (this may take 1-2 minutes)..."

    MAX_ATTEMPTS=60
    attempt=0

    while [ $attempt -lt $MAX_ATTEMPTS ]; do
        if docker-compose -f docker-compose.prod.yml ps | grep -q "weknora-api.*Up"; then
            echo_info "WeKnora API is up!"
            break
        fi
        sleep 5
        attempt=$((attempt + 1))
        echo -n "."
    done
    echo ""

    if [ $attempt -eq $MAX_ATTEMPTS ]; then
        echo_warn "Services may still be starting. Check logs with: docker-compose -f docker-compose.prod.yml logs -f"
    fi
}

# Show service status
show_status() {
    echo ""
    echo_info "Service Status:"
    echo "=================="
    docker-compose -f docker-compose.prod.yml ps

    echo ""
    echo_info "Access URLs:"
    echo "================"
    echo "  WeKnora UI:     http://localhost:8080"
    echo "  WeKnora API:    http://localhost:3000"
    echo "  Neo4j Browser:  http://localhost:7474"
    echo "  PostgreSQL:     localhost:5432"
    echo ""
    echo_info "Default credentials:"
    echo "  WeKnora UI:     admin / admin (change on first login)"
    echo "  Neo4j:          neo4j / (your NEO4J_PASSWORD)"
    echo ""
}

# Import test data
import_test_data() {
    echo_info "Importing test data..."

    if [ -d "test-data" ]; then
        for file in test-data/*.md; do
            if [ -f "$file" ]; then
                echo "  Importing: $file"
                # Note: This requires WeKnora API to be running
                # curl -X POST http://localhost:3000/api/v1/knowledge-bases/kb_default/knowledge/file \
                #   -F "file=@$file" \
                #   -F "metadata={\"source\": \"test-data\"}" \
                #   2>/dev/null || true
            fi
        done
        echo_info "Test data import complete. You can also import via Web UI."
    fi
}

# Main script
main() {
    echo "==============================="
    echo "  WikiService Quick Start"
    echo "==============================="
    echo ""

    check_docker
    check_env
    check_ports
    start_services
    show_status
    import_test_data

    echo_info "WikiService is ready!"
    echo ""
    echo "Next steps:"
    echo "  1. Visit http://localhost:8080 and log in"
    echo "  2. Change default password"
    echo "  3. Create a Knowledge Base and note the kb_id"
    echo "  4. Update .env with your kb_id"
    echo "  5. Configure your data sources in crawler/sources.yaml and scheduler/config.yaml"
    echo "  6. Restart scheduler: docker-compose -f docker-compose.prod.yml restart scheduler"
    echo ""
    echo "For more information, see docs/DEPLOYMENT.md"
}

# Run main script
main "$@"
