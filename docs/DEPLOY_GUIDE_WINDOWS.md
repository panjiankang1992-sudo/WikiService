# WikiService 部署指南

> 当前环境：Windows + Git Bash (无 Docker)

---

## 方案选择

由于当前环境没有安装 Docker，你有两个选择：

### 方案 A：安装 Docker Desktop（推荐）

**最完整的体验**，所有功能都可以正常运行。

**安装步骤：**
1. 下载 Docker Desktop for Windows
   - 官网：https://www.docker.com/products/docker-desktop/
   - 或使用国内镜像：https://registry.docker-cn.com
2. 安装并启动 Docker Desktop
3. 等待 Docker 完全启动（托盘图标变绿）
4. 验证安装：`docker --version`

**安装后运行：**
```bash
docker-compose -f docker-compose.prod.yml up -d
```

---

### 方案 B：纯 Python 运行（部分功能）

**无需 Docker**，但只能运行采集器、调度器等组件，WeKnora 核心服务需要单独部署。

**步骤 1：安装 Python 依赖**

```bash
cd D:/MyCode/WikiService
python -m venv venv
source venv/Scripts/activate  # Git Bash
# 或 Windows CMD: venv\Scripts\activate

pip install -r requirements.txt
```

**步骤 2：配置本地数据目录**

```bash
mkdir -p /d/data/weknora
mkdir -p /d/data/weknora/repos
mkdir -p /d/data/weknora/logs
mkdir -p /d/data/weknora/output
```

**步骤 3：测试 Git 采集器**

```bash
cd ingester
python git_ingester.py
```

**步骤 4：测试文件监控**

```bash
cd ingester
python file_watcher.py /d/data/weknora/docs
```

**步骤 5：测试爬虫**

```bash
cd crawler
python crawler.py
```

---

## WeKnora 核心服务部署

WeKnora 需要单独部署，有以下选项：

### 选项 1：使用 WeKnora 云服务（如果有）

联系腾讯 WeKnora 团队获取云实例。

### 选项 2：使用替代方案

可以使用以下开源替代方案作为知识管理核心：

| 方案 | 特点 |
|------|------|
| **Dify** | 国产开源 LLM 应用开发平台，支持知识库 |
| **FastChat** | 支持向量检索和知识库 |
| **LangChain + Qdrant** | 自建 RAG 系统 |

---

## 推荐：安装 Docker Desktop

为了获得完整功能体验，建议安装 Docker Desktop。

**Windows 系统要求：**
- Windows 10/11 64 位
- WSL 2 启用
- 虚拟化支持开启

**启用 WSL 2：**
```powershell
# 以管理员身份运行 PowerShell
wsl --install
wsl --set-default-version 2
```

然后安装 Docker Desktop。

---

## 环境变量已配置

`.env` 文件已配置为 DeepSeek API：

```bash
EMBEDDING_PROVIDER=deepseek
EMBEDDING_API_BASE=https://api.deepseek.com
EMBEDDING_API_KEY=sk-9538d57105d14bb194708e629c36ad74
EMBEDDING_MODEL=deepseek-chat
```

⚠️ **注意：** DeepSeek 主要是对话模型，不是嵌入模型。如果需要向量嵌入功能，建议使用：
- SiliconFlow BGE-M3（中文优化）
- Jina AI
- OpenAI text-embedding-ada-002

---

## 下一步

请告诉我你的选择：

**A.** 安装 Docker Desktop，我来帮你配置和启动完整服务

**B.** 使用纯 Python 方案，我先帮你安装依赖并测试组件

**C.** 了解其他替代方案（Dify 等）
