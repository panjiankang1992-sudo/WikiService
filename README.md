# WikiService

基于 WeKnora 的企业级知识库系统，支持多源数据采集、知识图谱关联查询和 MCP 服务暴露。

## 快速开始

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填写你的配置
```

### 2. 启动服务

```bash
# 启动所有服务（WeKnora + Neo4j + PostgreSQL + Crawler + Scheduler）
docker-compose -f docker-compose.prod.yml up -d

# 查看日志
docker-compose -f docker-compose.prod.yml logs -f

# 停止服务
docker-compose -f docker-compose.prod.yml down
```

### 3. 访问服务

| 服务 | 地址 | 说明 |
|------|------|------|
| WeKnora UI | http://localhost:8080 | Web 管理界面 |
| WeKnora API | http://localhost:3000 | REST API |
| Neo4j Browser | http://localhost:7474 | 图谱可视化 |
| PostgreSQL | localhost:5432 | 数据库 |

## 核心功能

- **Obsidian 式关联查询**: 关键词搜索 → 返回 Top-K 文档 + 关联关系图谱
- **多源定时采集**: 网页（含登录）、Git 仓库、本地文件自动采集
- **MCP 服务**: 标准 MCP 协议，供 AI Agent 调用
- **Web 管理页面**: Wiki 编辑、搜索、图谱可视化、数据仪表盘

## 架构组件

| 组件 | 技术选型 |
|------|---------|
| 知识管理核心 | WeKnora (Wiki + KG + MCP + WebUI) |
| 知识图谱引擎 | Neo4j + GraphRAG |
| 向量数据库 | PostgreSQL + pgvector |
| 嵌入模型 | SiliconFlow BGE-M3 (可配置) |
| 网页爬取 | Crawl4AI |
| Git 采集 | 自定义 Git Ingester |
| 定时调度 | APScheduler |

## 目录结构

```
WikiService/
├── docker-compose.prod.yml    # 生产部署配置
├── .env.example               # 环境变量模板
├── crawler/                   # Crawl4AI 网页爬取
│   ├── Dockerfile
│   ├── crawler.py
│   └── sources.yaml          # 爬取源配置
├── scheduler/                 # 定时调度服务
│   ├── Dockerfile
│   ├── scheduler.py
│   └── config.yaml           # 调度配置
├── ingester/                  # Git 采集器
│   └── git_ingester.py
├── docker/                    # Docker 配置
│   └── init-db.sql
└── docs/                      # 文档
    └── superpowers/
        └── specs/            # 设计文档
```

## 配置示例

### 添加网页爬取源

编辑 `crawler/sources.yaml`:

```yaml
sources:
  - id: "my-wiki"
    name: "团队 Wiki"
    type: "web"
    seed_urls:
      - "https://wiki.internal.com/"
    max_depth: 3
    schedule: "0 3 * * *"  # 每天凌晨 3 点
    kb_id: "kb_my_wiki"
```

### 添加 Git 仓库源

编辑 `scheduler/config.yaml`:

```yaml
git_sources:
  - id: "backend-docs"
    name: "后端文档"
    url: "https://github.com/team/backend.git"
    include_patterns:
      - "docs/**/*.md"
      - "README.md"
    schedule: "0 5 * * *"  # 每天凌晨 5 点
    kb_id: "kb_backend"
```

## 开发

```bash
# 本地运行爬虫
cd crawler
python crawler.py

# 本地运行 Git 采集器
cd ingester
python git_ingester.py

# 运行调度器
cd scheduler
python scheduler.py
```

## MCP 工具

WeKnora 内置 MCP Server，暴露以下工具：

| 工具 | 功能 |
|------|------|
| `search_wiki` | 关键词搜索，返回 Top-K 文档 + 关系图 |
| `explore_relations` | 从指定文档扩展探索关联文档 |
| `ingest_webpage` | 手动触发网页采集 |
| `ingest_git_repo` | 手动触发 Git 仓库采集 |
| `get_wiki_graph` | 获取知识图谱结构 |

## 文档

- [完整技术方案](WikiServer_服务器版 Wiki 完整实现方案.md)
- [CLAUDE.md](CLAUDE.md) - AI 助手项目指南

## License

MIT
