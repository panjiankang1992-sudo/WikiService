# WikiServer 服务器版 Wiki 完整实现方案

> 基于现有 WikiServer v1/v2/递归采集方案 + 开源工具深度调研，形成最优可执行技术方案
> 
> 📅 2026-05-10 | 🏷️ wiki, weknora, crawl4ai, mcp, knowledge-graph
> 📚 目标知识库：禹余天的总结（共享知识库）

---

## 一、需求回顾与方案总览

### 1.1 核心需求

| # | 需求 | 关键描述 |
|---|------|---------|
| 1 | **Obsidian 式关联查询** | 关键词输入 → 返回 Top-K 相关文档 + 关联关系图谱，供 Agent 继续探查 |
| 2 | **多源定时采集** | 网页（含登录）、Git 仓库、本地文件，每天自动处理 |
| 3 | **MCP 服务** | 标准 MCP 协议暴露，供 AI Agent 调用 |
| 4 | **Web 管理页面** | 查看/搜索/录入/删除/更新 Wiki，关系图可视化，数据分析面板 |

### 1.2 方案结论

**核心选型：WeKnora（腾讯开源） + Crawl4AI + 自定义 Git 采集器**

| 组件 | 选型 | 覆盖需求 | 理由 |
|------|------|---------|------|
| 知识管理核心 | **WeKnora** | #1 #3 #4 | Wiki模式 + KG + MCP + WebUI 四合一 |
| 知识图谱引擎 | **WeKnora 内置 Neo4j + GraphRAG** | #1 | D3.js 交互式可视化，支持语义+关键词+图遍历混合检索 |
| MCP 服务 | **WeKnora 内置 MCP Server** | #3 | 开箱即用，暴露完整知识库操作能力 |
| Web 管理 UI | **WeKnora 内置** | #4 | 零代码部署的管理控制台 |
| 深度网页爬取 | **Crawl4AI** | #2 | MIT 开源，内置 cron 调度，支持登录态、JS 渲染、自适应爬取 |
| Git 仓库采集 | **自定义轻量脚本** | #2 | 无现成方案完美匹配，~200行 Python 即可覆盖 |
| 嵌入模型 | **SiliconFlow BGE-M3 / Jina AI** | #1 | HTTP API 调用，零本地 GPU，中文最优，免费额度充足 |
| 向量数据库 | **WeKnora 内置** (pgvector/Qdrant/Milvus) | #1 | 可插拔，默认 pgvector 零额外部署 |

### 1.3 为什么不选其他方案

| 方案 | 致命缺陷 |
|------|---------|
| **纯自建 WikiServer** | 缺少 Web UI、KG 可视化、团队协作，研发成本至少 3 人月 |
| **Graphiti 做核心** | 纯后端库，无 Web UI、无采集、无 Wiki 生成，需从零搭建一切 |
| **Mnemo** | 0 star，单开发者，完全未经验证 |
| **SiYuan** | 纯个人工具，无团队协作、无 MCP |
| **Outline** | BSL 非开源协议，无 KG、无 MCP |
| **Logseq+TriliumNext** | 桌面优先架构，非服务器设计，MCP 仅社区版 |

---

## 二、总体架构设计

### 2.1 架构全景图

```
┌─────────────────────────────────────────────────────────────────┐
│                     📥 数据采集层 (Ingestion Layer)               │
│                                                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │   Crawl4AI        │  │  Git Ingester    │  │ File Watcher  │  │
│  │  · 定时深度爬取    │  │  · 克隆仓库      │  │  · 目录监控    │  │
│  │  · Cookie/登录态   │  │  · 提取文档      │  │  · 增量同步    │  │
│  │  · JS 渲染        │  │  · 增量更新      │  │  · 格式识别    │  │
│  │  · Markdown 输出  │  │  · Markdown 输出 │  │               │  │
│  └────────┬─────────┘  └────────┬─────────┘  └───────┬───────┘  │
│           │                     │                     │          │
│           └─────────────────────┼─────────────────────┘          │
│                                 ▼                                │
│                    ┌─────────────────────┐                       │
│                    │  Cron Scheduler     │                       │
│                    │  (APScheduler)      │                       │
│                    └─────────┬───────────┘                       │
└──────────────────────────────┼──────────────────────────────────┘
                               │ HTTP API / 文件系统
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     🧠 WeKnora 核心引擎                           │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              文档处理管道 (Document Pipeline)              │   │
│  │  PDF/Word/Excel/PPT/Markdown/HTML/图片                    │   │
│  │       ↓ 解析 → 分块 → 嵌入 → 存储                          │   │
│  │  (Docling + OCR + 多模态模型)                              │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Wiki 模式 (Wiki Mode)                        │   │
│  │  原始文档 → Agent 自动蒸馏 → 结构化 Markdown Wiki          │   │
│  │  · 自动提取关键概念    · 生成交叉引用链接                  │   │
│  │  · 层级化组织          · 持续增量更新                      │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │          知识图谱 (Knowledge Graph)                        │   │
│  │  ┌──────────────────┐  ┌──────────────────────────────┐  │   │
│  │  │  Neo4j 图数据库   │  │  GraphRAG 检索策略            │  │   │
│  │  │  · 实体-关系存储  │  │  · 语义搜索 + 关键词 + 图遍历 │  │   │
│  │  │  · 社区检测       │  │  · 混合重排序                │  │   │
│  │  │  · 路径查询       │  │  · 子图扩展                  │  │   │
│  │  └──────────────────┘  └──────────────────────────────┘  │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              存储层                                       │   │
│  │  PostgreSQL (元数据) + pgvector/Qdrant (向量)             │   │
│  │  + Neo4j (图谱) + MinIO/OSS (原始文件)                    │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     🔌 服务暴露层                                 │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │  MCP Server   │  │  REST API    │  │  Web UI               │  │
│  │  · 知识检索   │  │  · CRUD      │  │  · Wiki 编辑器        │  │
│  │  · 文档管理   │  │  · 搜索      │  │  · 图谱可视化         │  │
│  │  · 图谱遍历   │  │  · 图谱查询  │  │  · 数据仪表盘         │  │
│  │  · 采集管理   │  │  · 采集管理  │  │  · 来源管理           │  │
│  └──────────────┘  └──────────────┘  └───────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流

```
外部来源                   WeKnora 内部                    对外服务
─────────                ──────────────                  ──────────
网页 ──→ Crawl4AI ──→ Markdown ──→ 文档管道 ──→ 向量库 ──→ MCP/API
Git  ──→ Ingester ──→ Markdown ──→          ──→ 图谱库 ──→ WebUI
文件 ──→ Watcher  ──→ 原始文件 ──→ Wiki模式 ──→ Wiki页面
```

---

## 三、组件详细设计

### 3.1 WeKnora 核心（承担 80% 需求）

**版本**：v0.5.1+（需启用 Neo4j + 知识图谱功能）

**部署命令**（一键启动）：
```bash
git clone https://github.com/Tencent/WeKnora.git
cd WeKnora

# 启用 Neo4j 知识图谱
docker compose --profile neo4j up -d

# 访问 http://localhost:3000
```

**关键能力映射**：

| 用户需求 | WeKnora 对应功能 | 状态 |
|---------|-----------------|------|
| 关键词关联查询 | GraphRAG 混合检索 + 子图扩展 | ✅ 内置 |
| Obsidian 式关系图 | D3.js 交互式知识图谱可视化 | ✅ 内置 |
| MCP 服务 | 内置 MCP Server (`mcp-server/`) | ✅ 内置 |
| Web 管理 UI | 完整管理控制台 | ✅ 内置 |
| 网页导入 | URL 导入（单页） | ✅ 内置 |
| 文件导入 | PDF/Word/Excel/PPT/Markdown/图片 | ✅ 内置 |
| Wiki 自动生成 | Wiki Mode（Agent 蒸馏文档） | ✅ 内置 |
| 团队共享 | 多租户、IM 集成 | ✅ 内置 |
| 深度网页爬取 | ❌ 仅单页 URL 导入 | 🔧 需 Crawl4AI 补充 |
| Git 仓库采集 | ❌ 不支持 | 🔧 需自建采集器 |

### 3.2 Crawl4AI — 深度网页爬取

**为什么选 Crawl4AI 而非 Firecrawl**：
- Crawl4AI：MIT 开源，完全免费，内置 cron 调度器，~49k stars
- Firecrawl：部分开源(AGPL)，调度需外部实现，云服务付费

**关键功能**：

```python
# 定时深度爬取配置示例
from crawl4ai import AsyncWebCrawler, CrawlerConfig, SchedulerConfig

config = CrawlerConfig(
    seed_urls=["https://docs.internal.com/wiki/"],
    
    # === 登录态支持 ===
    auth={
        "type": "cookie",
        "cookies": {"session": "xxx", "csrf": "yyy"}
    },
    # 或表单登录
    # auth={"type": "form", "login_url": "...", "username": "...", "password": "..."},
    
    # === 深度控制 ===
    max_depth=5,
    max_pages=5000,
    
    # === URL 过滤（参考 WikiServer 递归采集设计）===
    include_patterns=["^/docs/", "^/wiki/"],
    exclude_patterns=["/assets/", "/static/", r"\.pdf$", r"\?"],
    
    # === 输出 ===
    output_format="markdown",  # 直接输出 Markdown 供 WeKnora 消费
    
    # === 速率控制 ===
    rate_limit=0.5,  # 每 0.5 秒一个请求
    max_concurrent=1,
    
    # === 计划任务 ===
    scheduler=SchedulerConfig(
        enabled=True,
        cron="0 3 * * *",  # 每天凌晨 3 点
        incremental=True,   # 增量更新
    )
)

async with AsyncWebCrawler(config) as crawler:
    await crawler.start()
```

**与 WeKnora 集成**：Crawl4AI 输出 Markdown 文件 → WeKnora 的文件夹导入 API 自动摄入。

### 3.3 Git 仓库采集器（自建，~200 行）

**设计参考 WikiServer 方案中的来源管理设计**：

```python
"""
Git Ingester — 定时克隆/拉取仓库，提取文档文件，推送到 WeKnora
借鉴 WikiServer v2 的 sources 配置表和递归采集的状态管理设计
"""
import os
import subprocess
import hashlib
import yaml
from pathlib import Path
from datetime import datetime
import requests

class GitIngester:
    """Git 仓库文档采集器"""
    
    def __init__(self, config_path: str, weknora_api: str):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        self.weknora_api = weknora_api
    
    def _clone_or_pull(self, repo_config: dict) -> Path:
        """克隆或增量拉取仓库"""
        repo_dir = Path(repo_config['local_path'])
        repo_url = repo_config['url']
        
        if not repo_dir.exists():
            # 首次克隆
            cmd = ["git", "clone", "--depth", "1"]
            if repo_config.get('branch'):
                cmd += ["-b", repo_config['branch']]
            subprocess.run(cmd + [repo_url, str(repo_dir)], check=True)
        else:
            # 增量拉取
            subprocess.run(["git", "-C", str(repo_dir), "pull"], check=True)
        
        return repo_dir
    
    def _extract_docs(self, repo_dir: Path, include_patterns: list, 
                      exclude_patterns: list) -> list:
        """提取匹配的文档文件（借鉴递归采集的 URL 过滤模式）"""
        import fnmatch
        docs = []
        for root, dirs, files in os.walk(repo_dir):
            # 排除目录
            dirs[:] = [d for d in dirs if not any(
                fnmatch.fnmatch(d, pat) for pat in exclude_patterns
            )]
            
            for f in files:
                filepath = Path(root) / f
                rel_path = filepath.relative_to(repo_dir)
                
                # 包含模式过滤
                if not any(fnmatch.fnmatch(str(rel_path), pat) 
                          for pat in include_patterns):
                    continue
                
                # 去重（基于内容 SHA256 — WikiServer 设计）
                content_hash = hashlib.sha256(
                    filepath.read_bytes()
                ).hexdigest()
                
                docs.append({
                    'path': str(filepath),
                    'rel_path': str(rel_path),
                    'content_hash': content_hash,
                    'source': f"git://{repo_dir.name}/{rel_path}"
                })
        
        return docs
    
    def _push_to_weknora(self, docs: list, kb_id: str):
        """将文档推送到 WeKnora 知识库"""
        for doc in docs:
            # WeKnora 的文件上传 API
            with open(doc['path'], 'rb') as f:
                resp = requests.post(
                    f"{self.weknora_api}/api/v1/knowledge-bases/{kb_id}/knowledge/file",
                    files={"file": (doc['rel_path'], f)},
                    data={"metadata": str({"source": doc['source']})}
                )
                resp.raise_for_status()
    
    def run(self):
        """主采集流程 — 定时调度入口"""
        for repo in self.config['sources']:
            if not repo.get('enabled', True):
                continue
            try:
                repo_dir = self._clone_or_pull(repo)
                docs = self._extract_docs(
                    repo_dir,
                    repo.get('include_patterns', ['*.md', '*.rst', '*.txt']),
                    repo.get('exclude_patterns', ['.git', 'node_modules', '__pycache__'])
                )
                self._push_to_weknora(docs, repo['kb_id'])
                print(f"[{repo['name']}] ✅ {len(docs)} docs ingested")
            except Exception as e:
                print(f"[{repo['name']}] ❌ {e}")
```

**配置文件**（参考 WikiServer sources 表设计）：

```yaml
# git_sources.yaml
sources:
  - id: "team-backend"
    name: "后端代码仓库"
    type: "git"
    enabled: true
    url: "https://github.com/team/backend.git"
    branch: "main"
    local_path: "/data/repos/backend"
    kb_id: "kb_backend_xxx"
    include_patterns:
      - "docs/**/*.md"
      - "README.md"
      - "CHANGELOG.md"
      - "*.md"
    exclude_patterns:
      - ".git"
      - "node_modules"
      - "__pycache__"
      - "*.pyc"
      - "vendor"
    schedule: "0 5 * * *"  # 每天凌晨5点

  - id: "open-source-docs"
    name: "开源项目文档"
    type: "git"
    url: "https://github.com/project/docs.git"
    local_path: "/data/repos/oss-docs"
    kb_id: "kb_oss_xxx"
    include_patterns:
      - "**/*.md"
      - "**/*.rst"
    schedule: "0 6 * * *"
```

### 3.4 定时调度层

```python
"""
Scheduler — 统一调度 Crawl4AI + Git Ingester + File Watcher
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = BackgroundScheduler()

# Crawl4AI 爬取任务
for web_source in web_sources:
    scheduler.add_job(
        crawl_web_source,
        CronTrigger.from_crontab(web_source['schedule']),
        args=[web_source],
        id=f"web_{web_source['id']}"
    )

# Git 仓库采集任务
for git_source in git_sources:
    scheduler.add_job(
        git_ingester.run_repo,
        CronTrigger.from_crontab(git_source['schedule']),
        args=[git_source],
        id=f"git_{git_source['id']}"
    )

# 本地文件监控（watchdog）
scheduler.add_job(
    file_watcher.scan,
    CronTrigger.from_crontab("0 */2 * * *"),  # 每2小时
    id="file_watcher"
)

scheduler.start()
```

### 3.5 MCP 服务设计

WeKnora 内置 MCP Server，额外增强以下工具：

```json
{
  "mcp_tools": [
    {
      "name": "search_wiki",
      "description": "关键词搜索 Wiki，返回 Top-K 文档 + 关联关系图",
      "parameters": {
        "query": "string",
        "top_k": "int (default 10)",
        "include_relations": "bool (default true)",
        "kb_id": "string"
      },
      "returns": {
        "results": "[{id, title, score, summary}]",
        "relations": "[{source_id, target_id, type, weight}]",
        "graph_subset": "{nodes, edges}"
      }
    },
    {
      "name": "explore_relations",
      "description": "从指定文档出发，扩展探索关联文档（Agent 链式查询关键）",
      "parameters": {
        "doc_id": "string",
        "depth": "int (default 1)",
        "relation_types": ["semantic", "reference", "tag"]
      }
    },
    {
      "name": "ingest_webpage",
      "description": "手动触发网页采集",
      "parameters": {
        "url": "string",
        "kb_id": "string",
        "deep_crawl": "bool (default false)",
        "auth": "object (optional)"
      }
    },
    {
      "name": "ingest_git_repo",
      "description": "手动触发 Git 仓库采集",
      "parameters": {
        "repo_url": "string",
        "branch": "string",
        "kb_id": "string"
      }
    },
    {
      "name": "get_wiki_graph",
      "description": "获取知识图谱完整结构（节点+边），支持子图查询",
      "parameters": {
        "kb_id": "string",
        "center_doc_id": "string (optional)",
        "depth": "int (default 2)"
      }
    }
  ]
}
```

### 3.6 Obsidian 式关联查询实现

这是需求 #1 的核心。利用 WeKnora 的 **GraphRAG + Neo4j** 实现：

```
用户输入查询 "微服务架构"
        │
        ▼
┌───────────────────────────────────────┐
│  第一层：语义向量检索                   │
│  BGE-M3 嵌入 → pgvector Top-20        │
│  返回最相关的文档列表                   │
└───────────────┬───────────────────────┘
                ▼
┌───────────────────────────────────────┐
│  第二层：关键词 BM25 检索               │
│  领域关键词匹配 → 补充候选              │
│  合并去重后得 Top-K                     │
└───────────────┬───────────────────────┘
                ▼
┌───────────────────────────────────────┐
│  第三层：图谱扩展（关键！）              │
│  对每个 Top-K 文档，查询 Neo4j：       │
│  MATCH (d)-[r]-(related)              │
│  WHERE d.id IN [top_k_ids]            │
│  RETURN related, r                    │
│                                       │
│  结果：                                │
│  - 直接引用关系 (explicit links)       │
│  - 语义相似关系 (semantic edges)       │
│  - 标签关联 (shared tags)              │
│  - 来源关联 (same source)             │
└───────────────┬───────────────────────┘
                ▼
┌───────────────────────────────────────┐
│  第四层：社区检测 + 排序                │
│  Louvain 社区检测 → 分组              │
│  PageRank 重要性排序                   │
│  返回结构化图谱数据                    │
└───────────────┬───────────────────────┘
                ▼
        返回给 Agent：
        {
          "query": "微服务架构",
          "results": [
            {"id": "doc_1", "title": "微服务设计原则", 
             "score": 0.95, "community": "architecture"},
            {"id": "doc_2", "title": "Kubernetes 部署指南", 
             "score": 0.87, "community": "devops"},
            ...
          ],
          "relations": [
            {"source": "doc_1", "target": "doc_2", 
             "type": "semantic", "weight": 0.72},
            {"source": "doc_1", "target": "doc_3", 
             "type": "reference", "weight": 1.0},
            ...
          ],
          "graph": {
            "nodes": [{...}],
            "edges": [{...}]
          }
        }
```

---

## 四、分阶段实施计划

### Phase 1：核心部署 + 基础能力（第 1 周）

**目标**：快速上线 MVP，验证核心链路

| 任务 | 工时 | 产出 |
|------|------|------|
| WeKnora Docker 部署（含 Neo4j） | 0.5 天 | 运行中的 WeKnora 实例 |
| 配置嵌入模型（SiliconFlow BGE-M3） | 0.5 天 | 中文语义检索可用 |
| 手动导入测试数据 | 1 天 | 验证文档解析→检索→图谱全链路 |
| 验证 MCP Server | 0.5 天 | Agent 可通过 MCP 查询知识库 |
| 配置 Web UI + 用户权限 | 0.5 天 | 团队可访问管理页面 |
| 验证 Wiki Mode | 1 天 | 测试 Agent 自动蒸馏文档生成 Wiki |

### Phase 2：多源采集接入（第 2 周）

**目标**：实现自动化多源采集

| 任务 | 工时 | 产出 |
|------|------|------|
| Crawl4AI 集成 + 定时调度 | 2 天 | 网页深度爬取自动入库 |
| Git Ingester 开发 | 1.5 天 | 代码仓文档自动采集 |
| 本地文件监控 | 1 天 | 本地 Markdown 目录同步 |
| 采集状态管理 + 日志 | 0.5 天 | 采集历史可追溯 |

### Phase 3：关联增强 + 生产优化（第 3-4 周）

**目标**：强化 Obsidian 式关联查询，完善生产特性

| 任务 | 工时 | 产出 |
|------|------|------|
| MCP 增强工具开发（custom MCP tools） | 2 天 | Agent 友好的关联查询接口 |
| 图谱查询接口优化 | 1 天 | 子图扩展、路径查询、社区检测 |
| 采集去重 + 增量优化 | 1 天 | 避免重复摄入 |
| 监控告警 + 备份 | 1 天 | 生产可用 |
| 文档 + 使用指南 | 1 天 | 团队上手文档 |

### 总工时估算

| 阶段 | 工时 | 累计 |
|------|------|------|
| Phase 1 | 4 天 | 4 天 |
| Phase 2 | 5 天 | 9 天 |
| Phase 3 | 6 天 | 15 天 |
| **总计** | **15 天** | — |

---

## 五、部署架构与资源估算

### 5.1 Docker Compose 一键部署

```yaml
# docker-compose.prod.yml
services:
  # === WeKnora 核心 ===
  weknora-api:
    image: weknora/weknora:latest
    ports:
      - "3000:8080"
    environment:
      - DB_DRIVER=postgres
      - DB_HOST=postgres
      - VECTOR_STORE=pgvector
      - EMBEDDING_API_BASE=https://api.siliconflow.cn/v1
      - EMBEDDING_API_KEY=${SILICONFLOW_API_KEY}
      - EMBEDDING_MODEL=BAAI/bge-m3
    depends_on:
      - postgres
      - neo4j

  weknora-ui:
    image: weknora/weknora-ui:latest
    ports:
      - "8080:80"

  # === 数据库 ===
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: weknora
      POSTGRES_USER: weknora
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data

  neo4j:
    image: neo4j:5.26-community
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4jdata:/data

  # === 采集服务 ===
  crawler:
    build: ./crawler
    environment:
      - WEKNORA_API=http://weknora-api:8080
      - WEKNORA_KB_ID=${WEKNORA_KB_ID}
    volumes:
      - ./sources.yaml:/app/sources.yaml
      - crawl_data:/data

  # === MCP 服务（WeKnora 内置，可选独立部署） ===
  mcp-server:
    image: weknora/weknora-mcp:latest
    ports:
      - "3100:3100"
    environment:
      - WEKNORA_API_URL=http://weknora-api:8080

volumes:
  pgdata:
  neo4jdata:
  crawl_data:
```

### 5.2 资源配置

| 组件 | CPU | 内存 | 磁盘 | 说明 |
|------|-----|------|------|------|
| WeKnora API | 2 核 | 4GB | 10GB | Go 服务，轻量 |
| PostgreSQL+pgvector | 2 核 | 4GB | 50GB+ | 含向量索引 |
| Neo4j | 2 核 | 4GB | 20GB | 图谱存储 |
| Crawler | 1 核 | 2GB | 10GB | 爬虫工作目录 |
| **总计** | **4-8 核** | **16GB** | **100GB** | 单机可运行 |

---

## 六、关键风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| WeKnora 版本不稳定 | 中 | 高 | 固定版本部署，关注 GitHub Release |
| Neo4j 资源占用高 | 中 | 中 | 使用 Community 版，限制内存；万级节点足矣 |
| Crawl4AI 被反爬 | 中 | 中 | 配置合理 rate limit，支持登录态 |
| 嵌入 API 限流 | 低 | 中 | SiliconFlow 免费额度充足，Jina AI 每日 100 万 token |
| Git 仓库过大 | 低 | 低 | shallow clone (--depth 1)，过滤二进制文件 |

---

## 七、与原 WikiServer 方案的关系

本次方案充分吸收了知识库中三篇 WikiServer 文章的核心设计思想：

| WikiServer 设计思想 | 在本方案中的体现 |
|---------------------|-----------------|
| **v1：SQLite + numpy 内存向量检索** | 升级为 pgvector + 混合检索，但保留了"内存优先"的轻量思想 |
| **v1：links 关系表（explicit/semantic/tag/share_source）** | Neo4j 实现，关系类型更丰富，支持图遍历 |
| **v2：HTTP API 嵌入（零本地模型）** | 完全采纳，SiliconFlow BGE-M3 / Jina AI |
| **v2：sources 配置表 + cron 调度** | 采纳并增强，Crawl4AI + Git Ingester 调度层 |
| **递归采集：BFS 深度控制 + URL 过滤** | Crawl4AI 原生支持，配置方式一致 |
| **递归采集：登录态 Cookie/Form 认证** | Crawl4AI 支持 |
| **递归采集：增量更新 + 状态管理** | 全部保留 |

**本质上，本方案是将 WikiServer 的设计思想落地到生产级开源组件上，而非从零造轮子。**

---

## 八、附录

### A. 参考资源

| 资源 | 链接 |
|------|------|
| WeKnora GitHub | https://github.com/Tencent/WeKnora |
| WeKnora 文档 | https://weknora.weixin.qq.com |
| Crawl4AI | https://github.com/unclecode/crawl4ai |
| Graphiti | https://github.com/getzep/graphiti |
| BGE-M3 嵌入 | https://api.siliconflow.cn |
| Jina Embeddings | https://api.jina.ai |
| Neo4j | https://neo4j.com |

### B. 相关设计文档（本知识库内）

1. WikiServer — 服务器端个人 Wiki 实现方案（v1）
2. WikiServer — MySQL + HTTP API 嵌入方案 v2
3. WikiServer 递归深钻采集 — 增强设计

---

> 📝 **结论**：以 WeKnora 为核心、Crawl4AI + 自定义 Git 采集器为辅助的方案，是目前最优、最快的实现路径。**15 天可完成从部署到生产就绪的全流程**，覆盖全部 4 项核心需求，且全部基于成熟的 MIT/Apache 开源组件，无商业授权风险。
