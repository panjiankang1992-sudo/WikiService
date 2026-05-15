# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

**WikiService** — A server-based knowledge base system built on **WeKnora** (Tencent open-source) with multi-source data ingestion.

**Core Stack:**
- **Knowledge Core**: WeKnora (Wiki + Knowledge Graph + MCP Server + WebUI)
- **Embedding**: Ollama 本地模型（`nomic-embed-text`，默认）/ 内网模型
- **Search**: 语义向量搜索（Embedding + 余弦相似度） + 关键词 BM25 Fallback
- **AI 评分**: DeepSeek Chat API（内网部署时切换为本地 LLM）
- **Web Crawler**: Crawl4AI（支持认证的定时深度抓取）
- **Git Ingester**: 自定义 Python 脚本提取仓库文档
- **Scheduler**: APScheduler（cron 定时调度）

---

## 网络策略（强制）

> **禁止主动连接外网。** 所有服务均在内网运行，不依赖外部 API。

**Embedding 模型（必须本地）：**
- 默认：Ollama (`nomic-embed-text`)，地址 `http://localhost:11434`
- 内网部署：设置 `EMBEDDING_BASE_URL` 指向内网 Ollama 服务
- 配置项：
  ```bash
  EMBEDDING_PROVIDER=ollama          # ollama | deepseek
  EMBEDDING_BASE_URL=http://192.168.x.x:11434
  EMBEDDING_MODEL=nomic-embed-text
  ```

**DeepSeek API（可选，仅开发调试）：**
- 端点：`POST https://api.deepseek.com/v1/embeddings`
- 模型：`deepseek-embedding`（1536 维）
- 仅开发时使用，**生产必须切换为内网模型**

**搜索流程：**
1. 尝试 Ollama/内网 Embedding（毫秒级，本地）
2. 失败时降级为关键词 BM25 搜索（无需网络）
3. 匹配文档 → LLM 评分归类（推荐/可能相关/其他）

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

## Deployment Conventions

### 目录约定

| 用途 | 路径 |
|------|------|
| **开发目录** | `/Users/pankang/mycode/WikiService/lightrag` |
| **部署目录** | `/opt/yuyutian/WikiService` |
| **日志目录** | `/opt/yuyutian/logs/WikiService` |
| **端口范围** | 23100-23109（通过 `PORT` 环境变量指定，默认 23100） |
| **数据目录** | `/opt/yuyutian/WikiService/data`（部署时独立，不随代码同步） |

### 开发工作流

**开发调试（当前目录）：**
```bash
cd /Users/pankang/mycode/WikiService/lightrag
DEEPSEEK_API_KEY=your_key .venv/bin/python app.py
# 默认端口 8080，无日志文件，仅输出到 stderr
```

**部署发布（同步到部署机）：**
```bash
cd /Users/pankang/mycode/WikiService/lightrag

# 方式一：使用部署脚本（自动同步代码）
./deploy.sh
PORT=23100 DEEPSEEK_API_KEY=your_key .venv/bin/python app.py

# 方式二：手动 rsync
rsync -av --exclude='.venv' --exclude='data' . /opt/yuyutian/WikiService/
```

**日志查看：**
```bash
tail -f /opt/yuyutian/logs/WikiService/wikiservice_23100.log
```

---

## Development Workflow

### Standalone LightRAG Service

**开发调试（当前目录）：**
```bash
cd /Users/pankang/mycode/WikiService/lightrag
./start.sh                    # 默认 8080，使用本地 ./data 目录
./start.sh 9000               # 指定端口 9000
DEEPSEEK_API_KEY=your_key ./start.sh  # 指定 API Key
```

**部署发布（同步代码后启动）：**
```bash
cd /Users/pankang/mycode/WikiService/lightrag && ./deploy.sh
cd /opt/yuyutian/WikiService
PORT=23100 DEEPSEEK_API_KEY=your_key .venv/bin/python app.py
```

### Docker Compose (Full Stack)

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

**Implementation Complete (2026-05-15)**

### LightRAG Standalone Service ✅
- **开发目录**: `/Users/pankang/mycode/WikiService/lightrag`（当前工作目录）
- **部署目录**: `/opt/yuyutian/WikiService`（`./deploy.sh` 同步）
- **端口**: 23100（范围 23100-23109）
- **日志**: `/opt/yuyutian/logs/WikiService/wikiservice_{PORT}.log`
- **功能**: 知识图谱 (D3.js)、多源 ingestion、全文搜索、语义搜索 + LLM 文档评分（推荐/可能相关/其他）、Markdown 渲染、`[[Wiki链接]]` 导航

### WeKnora Full Stack (Docker Compose) ✅
- Phase 1: Core deployment (Neo4j + PostgreSQL + pgvector)
- Phase 2: Multi-source ingestion (Crawl4AI, Git Ingester, File Watcher)
- Phase 3: Production features (Prometheus + Grafana monitoring, backup scripts)

### Next Steps for Users
1. **开发调试**: `cd /Users/pankang/mycode/WikiService/lightrag && DEEPSEEK_API_KEY=xxx .venv/bin/python app.py`
2. **部署发布**: `cd /Users/pankang/mycode/WikiService/lightrag && ./deploy.sh && cd /opt/yuyutian/WikiService && PORT=23100 DEEPSEEK_API_KEY=xxx .venv/bin/python app.py`
