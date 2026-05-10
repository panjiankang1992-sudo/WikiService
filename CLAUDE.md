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
├── WikiServer_服务器版 Wiki 完整实现方案.md  # Full technical spec
├── .claude/
│   └── settings.local.json        # Claude Code permissions
├── crawler/                       # Crawl4AI integration (to implement)
│   ├── sources.yaml               # Crawler configuration
│   └── Dockerfile
├── ingester/                      # Git repository ingester (to implement)
│   └── git_ingester.py
├── scheduler/                     # APScheduler orchestration
│   └── scheduler.py
└── docker-compose.prod.yml        # Production deployment
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

- ✅ Initial commit completed (2026-05-10)
- ✅ `master` branch created and set as primary
- 🚧 Phase 1 pending: WeKnora deployment, embedding config, test data import
- 🚧 Crawler, Git Ingester, Scheduler: design ready, implementation pending
