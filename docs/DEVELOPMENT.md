# WikiService Development Guide

## Project Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Data Ingestion Layer                      │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  Crawl4AI   │  │ Git Ingester │  │   File Watcher   │   │
│  │  (crawler/) │  │ (ingester/)  │  │  (ingester/)     │   │
│  └──────┬──────┘  └──────┬───────┘  └────────┬─────────┘   │
│         │                │                   │              │
│         └────────────────┼───────────────────┘              │
│                          ▼                                  │
│              ┌─────────────────────┐                        │
│              │   APScheduler       │                        │
│              │   (scheduler/)      │                        │
│              └─────────┬───────────┘                        │
└────────────────────────┼───────────────────────────────────┘
                         │ HTTP API
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    WeKnora Core                              │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐    │
│  │ Wiki Mode   │  │Knowledge Graph│  │   MCP Server    │    │
│  │             │  │ (Neo4j+RAG)   │  │ (mcp_server/)   │    │
│  └─────────────┘  └──────────────┘  └─────────────────┘    │
│  ┌─────────────┐  ┌──────────────┐                         │
│  │ Web UI      │  │ pgvector     │                         │
│  │             │  │ (PostgreSQL) │                         │
│  └─────────────┘  └──────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

## Development Environment Setup

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Git

### Local Development (without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Run individual components
python crawler/crawler.py
python scheduler/scheduler.py
python ingester/git_ingester.py
```

### Docker Development

```bash
# Start all services
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Rebuild a specific service
docker-compose -f docker-compose.prod.yml build crawler
docker-compose -f docker-compose.prod.yml up -d crawler

# Run a one-off command
docker-compose -f docker-compose.prod.yml run crawler python crawler.py --dry-run
```

## Code Style

### Python

- Follow PEP 8
- Use type hints
- Docstrings for public functions
- Max line length: 100

```python
def search_wiki(
    query: str,
    top_k: int = 10,
    include_relations: bool = True
) -> Dict[str, Any]:
    """
    Search Wiki with hybrid retrieval.

    Args:
        query: Search query string
        top_k: Number of results
        include_relations: Include relation graph

    Returns:
        Search results with relations
    """
    pass
```

### Configuration Files

- YAML for configuration
- Use descriptive key names
- Include comments for complex settings

## Testing

### Unit Tests

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_git_ingester.py -v

# Run with coverage
pytest --cov=. --cov-report=html
```

### Integration Tests

```bash
# Start test environment
docker-compose -f docker-compose.test.yml up -d

# Run integration tests
pytest tests/integration/ -v
```

## Debugging

### Enable Debug Logging

```yaml
# In config.yaml
logging:
  level: DEBUG
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Connection refused | Check if services are healthy: `docker-compose ps` |
| Import errors | Verify Python path: `echo $PYTHONPATH` |
| Port conflicts | Change ports in docker-compose.prod.yml |
| API timeouts | Increase timeout values in .env |

## Adding New Features

### 1. New Ingestion Source

```python
# ingester/new_source.py
class NewSourceIngester:
    def run(self) -> int:
        """Ingest from new source"""
        pass
```

```yaml
# scheduler/config.yaml
new_sources:
  - id: "my-source"
    type: "new_source"
    schedule: "0 3 * * *"
```

### 2. New MCP Tool

```python
# mcp_server/mcp_tools.py
@server.tool(name="new_tool")
async def new_tool(param: str) -> str:
    """New tool description"""
    pass
```

### 3. New Alert Rule

```yaml
# monitoring/alerts.yml
groups:
  - name: custom_alerts
    rules:
      - alert: CustomAlert
        expr: your_metric > threshold
        for: 5m
```

## Performance Tuning

### Database

```sql
-- Add indexes for frequently queried fields
CREATE INDEX idx_doc_title ON documents(title);
CREATE INDEX idx_created_at ON documents(created_at);

-- Analyze tables
ANALYZE documents;
```

### Crawler

```yaml
# Adjust rate limiting
rate_limit: 0.5  # Increase for faster crawling
max_concurrent: 2  # More parallel requests
```

### Embedding

```bash
# Batch embedding requests
# Modify mcp_tools.py to batch multiple texts together
```

## Deployment Checklist

- [ ] Environment variables configured
- [ ] Database backups scheduled
- [ ] Monitoring enabled
- [ ] Alert notifications configured
- [ ] SSL certificates installed (production)
- [ ] Firewall rules configured
- [ ] Resource limits set
- [ ] Log rotation configured

## Release Process

```bash
# 1. Update version in docker-compose.prod.yml
# 2. Commit changes
git commit -m "Release v1.0.0"

# 3. Create tag
git tag v1.0.0
git push origin v1.0.0

# 4. Build and push images (if using custom images)
docker build -t registry.example.com/weknora-crawler:v1.0.0 crawler/
docker push registry.example.com/weknora-crawler:v1.0.0
```

## Contributing

1. Fork the repository
2. Create a feature branch (`feature/your-feature`)
3. Make your changes
4. Run tests
5. Submit a pull request

## Getting Help

- Documentation: `docs/DEPLOYMENT.md`
- Technical Spec: `WikiServer_服务器版 Wiki 完整实现方案.md`
- Issues: GitHub Issues
- Discussions: GitHub Discussions
