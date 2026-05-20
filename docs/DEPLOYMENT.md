# WikiService 部署与使用指南

> 本文档描述 LightRAG 单机版（当前实际部署方案）。如需 WeKnora Docker Compose 历史方案，参考 [`WikiServer_服务器版 Wiki 完整实现方案.md`](../WikiServer_服务器版 Wiki 完整实现方案.md)。

---

## 一、系统架构

```
┌──────────────────────────────────────────────────────┐
│                      用户浏览器                        │
│               http://localhost:23100                    │
└───────────────────────┬──────────────────────────────┘
                        │ HTTP
┌───────────────────────▼──────────────────────────────┐
│              WikiService (Flask)                     │
│              端口: 23100                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │
│  │  知识查询     │ │  知识图谱     │ │  知识管理     │ │
│  │  /api/query  │ │  /api/graph  │ │  /api/chunks │ │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ │
│         └────────────────┼────────────────┘         │
│  ┌──────────────────────▼──────────────────────┐    │
│  │           检索引擎（语义 + 关键词）             │    │
│  └──────────────────────┬──────────────────────┘    │
└──────────────────────────┼───────────────────────────┘
                           │ POST /api/embeddings
                   ┌───────▼───────┐
                   │   Ollama       │
                   │ nomic-embed   │
                   │   :11434      │
                   └───────────────┘
```

---

## 二、环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | ≥ 3.10 | 运行环境 |
| Ollama | ≥ 0.1.42 | 本地 Embedding 服务 |
| nomic-embed-text | latest | 向量模型（274MB，一次下载永久离线） |

**Ollama 安装：**
```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# 下载模型（首次需要网络）
ollama pull nomic-embed-text
```

---

## 三、配置环境变量

```bash
# 必需配置（Ollama 方式，无需 API Key）
export EMBEDDING_PROVIDER=ollama
export EMBEDDING_MODEL=nomic-embed-text
export EMBEDDING_BASE_URL=http://localhost:11434

# 必需配置（占位值，当前版本不使用 LLM）
export DEEPSEEK_API_KEY=your_key_here

# 可选配置
export PORT=23100                              # 服务端口（默认 23100）
export STORAGE_PATH=/opt/yuyutian/WikiService/data  # 数据目录
export LOG_DIR=/opt/yuyutian/logs/WikiService      # 日志目录
```

---

## 四、启动服务

### 本地开发

```bash
cd /Users/pankang/mycode/WikiService/lightrag
DEEPSEEK_API_KEY=xxx .venv/bin/python app.py
```

### 使用启动脚本

```bash
cd /Users/pankang/mycode/WikiService/lightrag
./start.sh          # 默认端口 23100
./start.sh 23101    # 指定端口
```

### 一键离线部署（已有 Ollama）

```bash
cd /Users/pankang/mycode/WikiService/lightrag
./offline-deploy.sh
```

### 部署到远程服务器

```bash
# 同步代码
cd /Users/pankang/mycode/WikiService/lightrag
./deploy.sh

# 在远程启动
ssh deploy-server
cd /opt/yuyutian/WikiService
PORT=23100 DEEPSEEK_API_KEY=xxx .venv/bin/python app.py
```

日志：`/opt/yuyutian/logs/WikiService/wikiservice_{PORT}.log`

---

## 五、访问服务

| 服务 | 地址 | 说明 |
|------|------|------|
| **WikiService Web UI** | http://localhost:23100 | 知识查询 + 图谱 + 管理 |
| **健康检查** | http://localhost:23100/health | 返回 `{"status": "ok"}` |
| **统计数据** | http://localhost:23100/api/stats | chunks 数量、来源分布 |

---

## 六、数据导入

### 6.1 Web UI 导入

访问 http://localhost:23100 → 左侧「知识管理」→ 选择导入方式（文件/手动输入/URL）

### 6.2 本地目录批量导入

```bash
curl -X POST http://localhost:23100/api/ingest/directory \
  -H "Content-Type: application/json" \
  -d '{"directory": "/path/to/your/docs", "recursive": true}'
```

### 6.3 GitHub 仓库导入

```bash
curl -X POST http://localhost:23100/api/ingest/github \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/owner/repo"}'
```

### 6.4 网页 URL 导入

```bash
# 单页
curl -X POST http://localhost:23100/api/ingest/url \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/docs/guide.md"}'

# MiniMax 文档批量（最多 20 页）
curl -X POST http://localhost:23100/api/ingest/minimax \
  -H "Content-Type: application/json" \
  -d '{"max_pages": 20}'
```

---

## 七、搜索原理

### 综合关联度算法

```
综合关联度 = 语义相似度 × 0.55 + 关键词匹配强度 × 0.45
```

### 关键词匹配强度（0-1）

| 条件 | 强度 |
|------|------|
| 标题精确命中中文词组 | 0.9 |
| 英文单词命中（词边界，≥3字符） | 0.8 |
| 标题 bigram ≥ 3 个命中 | 0.65 |
| 标题 bigram = 2 个命中 | 0.5 |
| 标题 bigram = 1 个命中 | 0.3 |
| 正文命中（标题无关键词时） | 0.15 |

### 结果分类

| 分类 | 条件 |
|------|------|
| **HIGH**（推荐文档） | 关键词命中 + 语义 ≥ 50% |
| **MEDIUM A**（可能相关） | 关键词命中 + 语义 ≥ 30% |
| **MEDIUM B**（可能相关） | 极短英文（≤4字符）+ 正文命中 |
| **MEDIUM C**（可能相关） | 中文正文命中 + 语义 ≥ 50%（标题无关键词时） |

> 参考 [`离线版本部署方案.md`](离线版本部署方案.md) 获取完整搜索原理文档。

---

## 八、数据存储

```
STORAGE_PATH/
├── text_chunks.json    # 所有文档 chunks
└── embeddings.json     # 向量缓存（key: chunk_id, value: {vec, _hash}）
```

---

## 九、故障排查

| 问题 | 解决方法 |
|------|---------|
| `EMBEDDING_PROVIDER environment variable is required` | 同步最新 app.py（当前版本已内置默认值） |
| 搜索返回 0 结果 | 知识库为空，先通过「知识管理」导入文档 |
| Ollama 连接超时 | `ollama run nomic-embed-text` 预热模型 |
| 端口被占用 | `kill $(lsof -ti TCP:23100)` 或改用其他端口 |
| 语义分数过低 | 检查文档是否被正确分块，可尝试重新导入 |

---

## 十、完全离线验证清单

| 检查项 | 命令 | 预期结果 |
|--------|------|---------|
| Ollama 运行中 | `curl http://localhost:11434/api/tags` | 返回 JSON |
| 模型已安装 | `ollama list` | 显示 nomic-embed-text |
| 服务启动 | `curl http://localhost:23100/health` | `{"status":"ok"}` |
| 数据存在 | `curl http://localhost:23100/api/stats` | `chunks_count > 0` |
| 搜索正常 | 界面输入"微服务架构" | 返回相关文档列表 |
| 图谱正常 | 切换到「知识图谱」页 | 显示力导向图 |

---

**文档版本**: 2026-05-20
