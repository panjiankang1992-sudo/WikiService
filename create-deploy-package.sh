#!/bin/bash
# Create deployment package for 192.168.1.9

set -e

echo "Creating deployment package..."

# Create tarball excluding unnecessary files
tar --exclude='.git' \
    --exclude='.claude' \
    --exclude='*.md' \
    --exclude='test-data' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    -czf weknora-deploy.tar.gz \
    docker-compose.prod.yml \
    docker/ \
    crawler/ \
    scheduler/ \
    ingester/ \
    mcp_server/ \
    deploy.sh \
    requirements.txt \
    .env.example \
    docs/DEPLOYMENT_192.168.1.9.md

echo "Deployment package created: weknora-deploy.tar.gz"
echo ""
echo "Upload to server:"
echo "  scp weknora-deploy.tar.gz pankang@192.168.1.9:/opt/mycode/"
echo ""
echo "Then on server:"
echo "  cd /opt/mycode"
echo "  mkdir -p WikiService && cd WikiService"
echo "  tar -xzf ../weknora-deploy.tar.gz"
echo "  ./deploy.sh"
