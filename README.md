# WikiService

基于 LightRAG 的轻量级离线知识库系统，支持语义搜索、知识图谱可视化和多源文档导入。

## 特性

- **100% 离线运行**：依赖 Ollama 本地模型，无需任何外部 API
- **语义搜索**：向量相似度 + BM25 关键词降级，中英文优化
- **知识图谱**：自动提取实体与关系，D3.js 力导向图可视化
- **多源导入**：本地文件、GitHub 仓库、网页 URL、MiniMax 文档
- **零运维**：单 JSON 文件存储，无数据库依赖

## 快速开始

### 1. 安装 Ollama（仅首次，需联网）

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# 下载 Embedding 模型
ollama pull nomic-embed-text
```

### 2. 配置环境变量

```bash
cd /Users/pankang/mycode/WikiService/lightrag

# 复制模板
cp .env.example .env
# 或直接设置
export DEEPSEEK_API_KEY=your_key_here
```

### 3. 启动服务

```bash
cd /Users/pankang/mycode/WikiService/lightrag

# 方式一：使用启动脚本（推荐）
DEEPSEEK_API_KEY=xxx ./start.sh 23100

# 方式二：直接运行
DEEPSEEK_API_KEY=xxx .venv/bin/python app.py
```

服务启动后访问 **http://localhost:23100**

### 4. 离线一键部署（已有 Ollama）

```bash
cd /Users/pankang/mycode/WikiService/lightrag
./offline-deploy.sh
```

---

## 目录结构

```
WikiService/
├── lightrag/              # 核心代码（开发 + 部署目录）
│   ├── app.py             # Flask 应用
│   ├── templates/          # Web UI
│   ├── start.sh           # 本地启动
│   ├── deploy.sh          # 远程部署
│   └── offline-deploy.sh  # 离线一键部署
├── docs/                  # 文档
└── doc/                   # 截图与演示材料
```

---

## 部署到远程服务器

```bash
cd lightrag

# 同步代码到部署机
./deploy.sh

# 在远程服务器上启动
cd /opt/yuyutian/WikiService
PORT=23100 DEEPSEEK_API_KEY=xxx .venv/bin/python app.py
```

日志位置：`/opt/yuyutian/logs/WikiService/wikiservice_{PORT}.log`

---

## 核心 API

```bash
# 知识查询
curl -X POST http://localhost:23100/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "微服务架构设计"}'

# 导入 GitHub 仓库
curl -X POST http://localhost:23100/api/ingest/github \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/owner/repo"}'

# 导入本地目录
curl -X POST http://localhost:23100/api/ingest/directory \
  -H "Content-Type: application/json" \
  -d '{"directory": "/path/to/docs"}'

# 查看统计
curl http://localhost:23100/api/stats
```

---

## 文档

| 文档 | 说明 |
|------|------|
| [`docs/离线版本部署方案.md`](docs/离线版本部署方案.md) | 完整离线部署指南，含搜索原理详解 |
| [`docs/项目总结-WikiService从0到1的AI协作实践.md`](docs/项目总结-WikiService从0到1的AI协作实践.md) | 项目复盘与 AI 协作经验总结 |
| [`CLAUDE.md`](CLAUDE.md) | AI 助手项目上下文 |
