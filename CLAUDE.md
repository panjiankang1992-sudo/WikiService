# CLAUDE.md

---

## 项目概述

**WikiService** — 基于 LightRAG 的轻量级离线知识库系统，支持语义搜索、知识图谱可视化和多源文档导入。

**核心特性**：
- 100% 离线可用（依赖 Ollama 本地 Embedding）
- 语义搜索 + 关键词 BM25 降级Fallback
- 知识图谱（D3.js 力导向图）
- 多源导入：本地文件、GitHub 仓库、网页 URL、MiniMax 文档
- 单 JSON 文件存储，零数据库依赖

---

## 技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| **Web 服务** | Flask + HTML/JS/CSS | 单进程、无状态 |
| **Embedding** | Ollama (`nomic-embed-text`) | 完全本地，毫秒级 |
| **搜索** | 语义向量 + 中文 Bigram + 英文词边界 | 综合关联度排序 |
| **图谱** | D3.js 力导向图 | 自动提取实体 + 关系 |
| **存储** | JSON 文件（`text_chunks.json`, `embeddings.json`） | 零数据库 |

---

## 网络策略（强制）

> **禁止主动连接外网。** 服务完全在内网运行，不依赖任何外部 API。

**Embedding（必须本地 Ollama）：**
- 地址：`http://localhost:11434`（默认）
- 模型：`nomic-embed-text`（274MB，首次 pull 后永久离线）
- 配置项：
  ```bash
  EMBEDDING_PROVIDER=ollama
  EMBEDDING_BASE_URL=http://localhost:11434
  EMBEDDING_MODEL=nomic-embed-text
  ```

**搜索降级链：**
1. Ollama 语义搜索（毫秒级）
2. 失败时降级为 BM25 关键词搜索（中文 bigram + 英文词边界）

---

## 目录结构

```
WikiService/
├── CLAUDE.md                      # 本文件
├── README.md                      # 快速开始
├── .env.example                   # 环境变量模板
├── lightrag/                      # 核心代码（开发 + 部署目录）
│   ├── app.py                     # Flask 应用（~1400 行）
│   ├── templates/index.html        # 前端（知识查询 + 图谱 + 管理）
│   ├── deploy.sh                  # 部署脚本（rsync 到远程）
│   ├── offline-deploy.sh          # 离线一键部署脚本
│   ├── start.sh                   # 本地启动脚本
│   ├── Dockerfile                 # Docker 镜像构建
│   └── data/                      # 数据目录（gitignore）
├── crawler/                       # 网页爬虫（Crawl4AI，未激活）
├── ingester/                      # 数据导入模块（Git、本地文件）
├── scheduler/                     # 定时调度（APScheduler，未激活）
├── docs/                          # 文档
│   ├── DEPLOYMENT.md              # 完整部署指南
│   ├── 离线版本部署方案.md          # 离线部署详解（含搜索原理）
│   └── 项目总结-*.md               # 项目复盘文档
├── doc/                           # 截图和演示材料
├── backup/                        # 备份脚本
├── monitoring/                    # Prometheus + Grafana（历史）
└── test-data/                     # 测试文档
```

---

## 部署约定

| 用途 | 路径 |
|------|------|
| **开发目录** | `/Users/pankang/mycode/WikiService/lightrag` |
| **部署目录** | `/opt/yuyutian/WikiService` |
| **日志目录** | `/opt/yuyutian/logs/WikiService` |
| **端口范围** | 23100-23109（通过 `PORT` 环境变量指定，默认 23100） |
| **数据目录** | `/opt/yuyutian/WikiService/data`（部署时独立，不随代码同步） |

---

## 开发工作流

### 本地开发

```bash
cd /Users/pankang/mycode/WikiService/lightrag

# 启动服务（默认端口 23100）
DEEPSEEK_API_KEY=xxx .venv/bin/python app.py

# 指定端口
DEEPSEEK_API_KEY=xxx PORT=23101 .venv/bin/python app.py

# 或使用启动脚本
DEEPSEEK_API_KEY=xxx ./start.sh        # 默认 23100
DEEPSEEK_API_KEY=xxx ./start.sh 9000   # 端口 9000
```

### 部署发布

```bash
cd /Users/pankang/mycode/WikiService/lightrag

# 同步代码到远程服务器
./deploy.sh

# 在远程启动
ssh deploy-server
cd /opt/yuyutian/WikiService
PORT=23100 DEEPSEEK_API_KEY=xxx .venv/bin/python app.py
```

### Ollama 管理

```bash
# 启动 Ollama 服务
ollama serve

# 下载 Embedding 模型（首次需要网络）
ollama pull nomic-embed-text

# 查看已安装模型
ollama list

# 预热模型（减少首次查询延迟）
ollama run nomic-embed-text "test"
```

---

## 搜索原理

### 综合关联度算法

```
综合关联度 = 语义相似度 × 0.55 + 关键词匹配强度 × 0.45
```

**关键词匹配强度：**

| 条件 | 强度 |
|------|------|
| 标题精确命中中文词组 | 0.9 |
| 英文单词命中（词边界，≥3字符） | 0.8 |
| 标题 bigram ≥ 3 个命中 | 0.65 |
| 标题 bigram = 2 个命中 | 0.5 |
| 标题 bigram = 1 个命中 | 0.3 |
| 正文命中（标题无关键词时） | 0.15 |

**结果分类阈值：**

| 分类 | 条件 |
|------|------|
| HIGH（推荐文档） | 关键词命中 + 语义 ≥ 50% |
| MEDIUM A（可能相关） | 关键词命中 + 语义 ≥ 30% |
| MEDIUM B（可能相关） | 极短英文查询（≤4字符）+ 语义 ≥ 40% + 正文命中 |
| MEDIUM C（可能相关） | 中文查询正文命中 + 语义 ≥ 50%（标题无关键词时） |

---

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | Web UI |
| `/health` | GET | 健康检查 |
| `/api/query` | POST | 知识查询（语义 + 关键词） |
| `/api/graph` | GET | 知识图谱数据 |
| `/api/stats` | GET | 统计数据 |
| `/api/chunks` | GET | 知识列表 |
| `/api/ingest` | POST | 手动添加知识 |
| `/api/ingest/file` | POST | 文件上传 |
| `/api/ingest/url` | POST | 网页抓取 |
| `/api/ingest/directory` | POST | 目录批量导入 |
| `/api/ingest/github` | POST | GitHub 仓库导入 |
| `/api/ingest/minimax` | POST | MiniMax 文档批量导入 |
| `/api/delete/<id>` | DELETE | 删除知识 |
| `/api/clear` | POST | 清空知识库 |

---

## Branch 策略

- **`master`**: 主要开发分支，所有代码合并到这里
- **`main`**: 历史分支，仅保留备份

---

## 当前状态（2026-05-20）

**✅ 已完成并上线**

- **LightRAG 单机版**：`http://localhost:23100`，完全离线运行
- **语义搜索**：Ollama Embedding + BM25 Fallback，中英文优化
- **知识图谱**：D3.js 力导向图，自动实体提取
- **多源导入**：本地文件、GitHub、MiniMax、网页 URL
- **离线部署**：`./offline-deploy.sh` 一键安装

**文档**：
- [`docs/离线版本部署方案.md`](docs/离线版本部署方案.md) — 离线部署详解（含搜索原理）
- [`docs/项目总结-WikiService从0到1的AI协作实践.md`](docs/项目总结-WikiService从0到1的AI协作实践.md) — 项目复盘与经验总结
- [`WikiServer_服务器版 Wiki 完整实现方案.md`](WikiServer_服务器版Wiki完整实现方案.md) — 原始技术方案（历史参考）
