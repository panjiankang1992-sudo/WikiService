# Stop WikiService

set -e

echo "Stopping all WikiService containers..."
docker-compose -f docker-compose.prod.yml down

echo ""
echo "All services stopped."
echo ""
echo "To start again: docker-compose -f docker-compose.prod.yml up -d"
