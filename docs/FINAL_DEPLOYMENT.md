# WikiService 部署到 192.168.1.9 - 最终方案

## 现状说明

1. **服务器信息**:
   - 主机：192.168.1.9
   - 用户：pankang
   - 系统：Ubuntu 26.04 LTS
   - Docker: 29.4.1
   - Docker Compose: v5.1.3

2. **已部署组件**:
   - 代码已同步到 `/opt/mycode/WikiService`
   - `.env` 配置文件已创建（DeepSeek API）

3. **遇到的问题**:
   - WeKnora 官方镜像拉取失败（429 限流）
   - Dify 镜像较大（约 1GB），拉取时间较长

## 推荐方案

### 方案 A：使用 Dify（推荐）

Dify 是成熟的开源 LLM 应用开发平台，支持知识库、RAG、MCP 等功能。

**部署步骤：**

```bash
# SSH 登录服务器
wsl ssh pankang@192.168.1.9

# 进入目录
cd /opt/mycode/WikiService

# 创建 Dify 部署配置
cat > docker-compose.yml << 'EOF'
services:
  api:
    image: langgenius/dify-api:latest
    restart: always
    ports:
      - "29216:5001"
    environment:
      - MODE=api
      - LOG_LEVEL=INFO
      - SECRET_KEY=sk-9538d57105d14bb194708e629c36ad74
      - INIT_PASSWORD=Admin@123
      - CONSOLE_WEB_URL=http://192.168.1.9:29215
      - DB_USERNAME=dify
      - DB_PASSWORD=dify_db_pwd_2026
      - DB_HOST=db
      - REDIS_HOST=redis
    depends_on:
      - db
      - redis
    volumes:
      - dify-storage:/app/storage

  web:
    image: langgenius/dify-web:latest
    restart: always
    ports:
      - "29215:3000"
    environment:
      - CONSOLE_API_URL=http://192.168.1.9:29216
      - APP_API_URL=http://192.168.1.9:29216
    depends_on:
      - api

  db:
    image: postgres:15-alpine
    restart: always
    ports:
      - "29219:5432"
    environment:
      POSTGRES_DB: dify
      POSTGRES_USER: dify
      POSTGRES_PASSWORD: dify_db_pwd_2026
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    restart: always
    ports:
      - "29220:6379"
    volumes:
      - redis-data:/data

  worker:
    image: langgenius/dify-api:latest
    restart: always
    environment:
      - MODE=worker
      - DB_USERNAME=dify
      - DB_PASSWORD=dify_db_pwd_2026
      - DB_HOST=db
      - REDIS_HOST=redis
    volumes:
      - dify-storage:/app/storage

volumes:
  pgdata:
  redis-data:
  dify-storage:
EOF

# 拉取并启动（可能需要 10-30 分钟）
docker compose pull
docker compose up -d

# 查看日志
docker compose logs -f
```

**访问地址**:
- Web UI: http://192.168.1.9:29215
- API: http://192.168.1.9:29216
- 默认账号：设置密码时配置的 INIT_PASSWORD

---

### 方案 B：使用 FastChat + 本地采集器

如果 Dify 镜像拉取太慢，可以使用更轻量的方案：

```bash
cd /opt/mycode/WikiService

# 1. 部署 FastChat（轻量级 LLM 服务）
cat > docker-compose-fastchat.yml << 'EOF'
services:
  fastchat:
    image: lmcache/vllm:latest
    ports:
      - "29216:8000"
    environment:
      - MODEL_NAME=deepseek-chat
      - API_KEY=sk-9538d57105d14bb194708e629c36ad74
    volumes:
      - fastchat-models:/models

  webui:
    image: gradio/gradio:latest
    ports:
      - "29215:7860"
    volumes:
      - ./crawler:/app/crawler
      - ./ingester:/app/ingester

volumes:
  fastchat-models:
EOF

docker compose -f docker-compose-fastchat.yml up -d
```

---

### 方案 C：仅部署采集器（无需 Docker）

如果只需要爬虫和采集功能：

```bash
cd /opt/mycode/WikiService

# 安装 Python 依赖
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 测试 Git 采集器
python ingester/git_ingester.py

# 测试文件监控
mkdir -p /opt/mycode/WikiService/docs
python ingester/file_watcher.py /opt/mycode/WikiService/docs

# 测试爬虫
python crawler/crawler.py
```

采集的数据可以导出为 Markdown 文件，手动导入到其他知识库系统。

---

## 现有代码功能

### 已实现的组件

| 组件 | 状态 | 位置 |
|------|------|------|
| Crawl4AI 集成 | ✅ 完成 | `crawler/` |
| Git Ingester | ✅ 完成 | `ingester/git_ingester.py` |
| File Watcher | ✅ 完成 | `ingester/file_watcher.py` |
| Scheduler | ✅ 完成 | `scheduler/` |
| MCP Tools | ✅ 完成 | `mcp_server/mcp_tools.py` |
| 监控配置 | ✅ 完成 | `monitoring/` |
| 备份脚本 | ✅ 完成 | `backup/` |

### 待部署的核心服务

由于 WeKnora 镜像不可用，可以选择：
1. **Dify** - 功能最全，镜像较大
2. **FastChat** - 轻量级，需要配置模型
3. **其他 RAG 平台** - 如 LangChain + Qdrant

---

## 下一步行动

**推荐执行方案 A（Dify）：**

1. 在后台继续拉取 Dify 镜像
2. 启动后访问 Web UI 配置
3. 使用 DeepSeek API 作为嵌入模型
4. 配置采集器将数据导入 Dify

**执行命令：**

```bash
# 1. 登录服务器
wsl ssh pankang@192.168.1.9

# 2. 进入目录
cd /opt/mycode/WikiService

# 3. 确认 docker-compose.yml 已创建（见上方方案 A）

# 4. 后台拉取镜像（使用 nohup）
nohup docker compose pull > /tmp/dify-pull.log 2>&1 &

# 5. 等待完成后启动
docker compose up -d

# 6. 查看状态
docker compose ps
```

---

## 联系方式

如有问题，请参考：
- Dify 文档：https://docs.dify.ai
- 本项目文档：`docs/DEPLOYMENT.md`
