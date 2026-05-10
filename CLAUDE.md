# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

**WikiService** — A server-based knowledge base system built on **WeKnora** (Tencent open-source) with multi-source data ingestion.

**Core Stack:**
- **Knowledge Core**: WeKnora (Wiki + Knowledge Graph + MCP Server + WebUI)
- **Vector Store**: pgvector (PostgreSQL)
- **Graph Engine**: Neo4j
- **Embedding**: SiliconFlow BGE-M3 (HTTP API)
- **Web Crawler**: Crawl4AI (scheduled deep crawling with auth support)
- **Git Ingester**: Custom Python script for repository documentation extraction
- **Scheduler**: APScheduler (cron-based)

---

## Branch Strategy

- **`master`**: Primary development branch. All code changes must be merged here to be considered complete.
- **`main`**: Legacy branch, kept for backup/sync purposes only.

**Workflow:**
1. Create feature branches from `master` (e.g., `feature/crawler-enhancement`)
2. Merge back to `master` via PR or direct commit
3. Never develop directly on `master`

---

## Architecture (High-Level)

```
┌─────────────────────────────────────────────────────────┐
│              Data Ingestion Layer                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐          │
│  │Crawl4AI  │  │Git Ingester│  │File Watcher │          │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘          │
└───────┼─────────────┼───────────────┼──────────────────┘
        │             │               │
        ▼             ▼               ▼
┌─────────────────────────────────────────────────────────┐
│              WeKnora Core                                │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │Wiki Mode    │  │Knowledge Graph│  │MCP Server     │  │
│  │(auto-gen)   │  │(Neo4j+RAG)    │  │(Agent API)    │  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
│  ┌─────────────┐  ┌──────────────┐                      │
│  │Web UI       │  │pgvector      │                      │
│  │(Admin/View) │  │(Semantic)    │                      │
│  └─────────────┘  └──────────────┘                      │
└─────────────────────────────────────────────────────────┘
```

**Key Design Patterns:**
- **4-layer retrieval**: Vector → BM25 → Graph expansion → Community detection
- **Scheduled ingestion**: Cron-based orchestration (APScheduler)
- **MCP-first**: All operations exposed via MCP tools for Agent consumption

---

## Directory Structure

```
WikiService/
├── CLAUDE.md                      # This file
├── README.md                      # Quick start guide
├── WikiServer_服务器版 Wiki 完整实现方案.md  # Full technical spec
├── .env.example                   # Environment variables template
├── docker-compose.prod.yml        # Production deployment
├── .claude/
│   └── settings.local.json        # Claude Code permissions
├── crawler/                       # Crawl4AI web crawler
│   ├── Dockerfile
│   ├── crawler.py                 # Main crawler script
│   └── sources.yaml               # Crawler configuration
├── ingester/                      # Data ingestion modules
│   ├── git_ingester.py            # Git repository ingester
│   └── file_watcher.py            # Local file watcher (watchdog)
├── scheduler/                     # APScheduler orchestration
│   ├── Dockerfile
│   ├── scheduler.py               # Main scheduler script
│   └── config.yaml                # Scheduler configuration
├── mcp_server/                    # MCP tools
│   └── mcp_tools.py               # Enhanced MCP tools for WikiService
├── monitoring/                    # Prometheus + Grafana
│   ├── docker-compose.monitoring.yml
│   ├── prometheus.yml
│   ├── alerts.yml
│   └── alertmanager.yml
├── backup/                        # Backup scripts
│   └── backup-scripts.sh          # PostgreSQL/Neo4j/Storage backup
├── test-data/                     # Test documents
│   ├── 微服务架构设计原则.md
│   ├── Kubernetes 部署指南.md
│   └── API 网关设计.md
└── docs/                          # Documentation
    └── DEPLOYMENT.md              # Deployment and usage guide
```

---

## Development Workflow

### Build & Run

```bash
# Start all services (WeKnora + Neo4j + Postgres + Crawler)
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f crawler

# Stop all services
docker-compose -f docker-compose.prod.yml down
```

### Key Configuration Files

| File | Purpose |
|------|---------|
| `sources.yaml` | Web/Git source definitions with cron schedules |
| `docker-compose.prod.yml` | Service orchestration, env vars |
| `.claude/settings.local.json` | Claude Code permissions |

### Testing

```bash
# Test single crawler source
python crawler/crawler.py --source-id team-backend --dry-run

# Test Git ingester
python ingester/git_ingester.py --repo test-repo --kb-id kb_test

# Verify MCP endpoints
curl http://localhost:3100/tools
```

---

## MCP Tools (Agent Interface)

WeKnora exposes these MCP tools for Agent consumption:

| Tool | Purpose |
|------|---------|
| `search_wiki` | Keyword search → Top-K docs + relation graph |
| `explore_relations` | Expand from doc_id with depth control |
| `ingest_webpage` | Manual web ingestion trigger |
| `ingest_git_repo` | Manual Git ingestion trigger |
| `get_wiki_graph` | Full graph structure or subgraph query |

---

## Existing Documentation

The file [`WikiServer_服务器版 Wiki 完整实现方案.md`](./WikiServer_服务器版 Wiki 完整实现方案.md) contains:
- Full requirements breakdown (4 core needs)
- Architecture decisions & rejection rationale
- Phase-by-phase implementation plan (15 days total)
- Docker Compose deployment spec
- Risk mitigation strategies
- Design continuity from original WikiServer v1/v2

**Read this file first** before implementing any major feature.

---

## Current Status

**Implementation Complete (2026-05-10)**

All 3 phases of the 15-day plan have been implemented:

### Phase 1: Core Deployment ✅
- WeKnora Docker Compose deployment (API + UI + Neo4j + PostgreSQL + pgvector)
- Configurable embedding model support (SiliconFlow BGE-M3 / Jina AI / custom)
- Test data imported (microservices, K8s, API gateway docs)
- MCP tools implemented (search, graph exploration, ingestion triggers)

### Phase 2: Multi-source Ingestion ✅
- Crawl4AI integration with scheduled crawling
- Git Ingester with incremental updates (SHA256 deduplication)
- File Watcher using watchdog for real-time sync
- APScheduler unified orchestration layer

### Phase 3: Production Features ✅
- Monitoring stack (Prometheus + Grafana + Alertmanager)
- Alert rules (service availability, resource usage, application metrics)
- Backup scripts (PostgreSQL dump, Neo4j backup, storage sync)
- Complete documentation (DEPLOYMENT.md with troubleshooting guide)

### Next Steps for Users
1. Configure `.env` with your embedding API key
2. Run `docker-compose -f docker-compose.prod.yml up -d`
3. Access WeKnora UI at http://localhost:8080
4. Configure your data sources in `crawler/sources.yaml` and `scheduler/config.yaml`
5. Set up monitoring with `docker-compose -f monitoring/docker-compose.monitoring.yml up -d`
