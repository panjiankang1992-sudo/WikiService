# WikiService 部署与使用指南

## 快速开始

### 1. 准备工作

#### 1.1 环境要求

| 组件 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 4 核 | 8 核 |
| 内存 | 8GB | 16GB |
| 磁盘 | 50GB | 100GB SSD |
| Docker | 20.10+ | 24.0+ |
| Docker Compose | 2.0+ | 2.20+ |

#### 1.2 检查环境

```bash
# 检查 Docker
docker --version
docker-compose --version

# 检查端口占用（需要释放 3000, 8080, 5432, 7474, 7687）
netstat -tlnp | grep -E '3000|8080|5432|7474|7687'
```

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑环境变量
vim .env
```

#### 必填配置

```bash
# 数据库密码
DB_PASSWORD=your_secure_password_here

# Neo4j 密码
NEO4J_PASSWORD=your_neo4j_password_here

# 嵌入模型 API Key（二选一）

# 方案 A: SiliconFlow BGE-M3（推荐，中文效果好）
EMBEDDING_PROVIDER=siliconflow
EMBEDDING_API_BASE=https://api.siliconflow.cn/v1
EMBEDDING_API_KEY=your_siliconflow_api_key
EMBEDDING_MODEL=BAAI/bge-m3

# 方案 B: Jina AI
# EMBEDDING_PROVIDER=jina
# EMBEDDING_API_BASE=https://api.jina.ai/v1
# EMBEDDING_API_KEY=your_jina_api_key
# EMBEDDING_MODEL=jina-embeddings-v3

# 知识_base ID（首次使用时会自动创建）
WEKNORA_KB_ID=kb_default
```

#### 获取 SiliconFlow API Key

1. 访问 https://cloud.siliconflow.cn
2. 注册/登录账号
3. 进入 API Keys 页面
4. 创建新的 API Key
5. 复制到 `.env` 文件的 `EMBEDDING_API_KEY` 字段

BGE-M3 免费额度：每月 100 万 token，足够个人和小型团队使用。

### 3. 启动服务

```bash
# 启动所有服务（后台运行）
docker-compose -f docker-compose.prod.yml up -d

# 查看启动日志
docker-compose -f docker-compose.prod.yml logs -f

# 检查服务状态
docker-compose -f docker-compose.prod.yml ps
```

#### 预期输出

```
NAME                    STATUS         PORTS
weknora-api             Up (healthy)   0.0.0.0:3000->8080/tcp
weknora-ui              Up             0.0.0.0:8080->80/tcp
weknora-postgres        Up (healthy)   0.0.0.0:5432->5432/tcp
weknora-neo4j           Up (healthy)   0.0.0.0:7474->7474/tcp, 0.0.0.0:7687->7687/tcp
weknora-crawler         Up             -
weknora-scheduler       Up             -
```

### 4. 访问服务

| 服务 | URL | 说明 |
|------|-----|------|
| WeKnora UI | http://localhost:8080 | Web 管理界面 |
| WeKnora API | http://localhost:3000 | REST API |
| Neo4j Browser | http://localhost:7474 | 图谱可视化 |
| PostgreSQL | localhost:5432 | 数据库（内网访问） |

#### 首次登录 WeKnora

1. 访问 http://localhost:8080
2. 默认管理员账号：`admin` / `admin`（首次登录请修改密码）
3. 创建第一个知识库（Knowledge Base）
4. 记录 `kb_id` 并更新到 `.env` 文件

### 5. 导入测试数据

```bash
# 方法 1: 通过 Web UI 导入
# 访问 http://localhost:8080
# 点击 "Import" → 选择 test-data/ 目录中的文件

# 方法 2: 通过 API 导入
curl -X POST http://localhost:3000/api/v1/knowledge-bases/kb_default/knowledge/file \
  -F "file=@test-data/微服务架构设计原则.md" \
  -F "metadata={\"source\": \"test-data\"}"

# 方法 3: 使用本地文件监控自动同步
mkdir -p /data/local-docs
cp test-data/*.md /data/local-docs/
# 文件监控服务会自动同步到 WeKnora
```

### 6. 验证检索功能

```bash
# 测试语义搜索
curl -X POST http://localhost:3000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "微服务架构",
    "top_k": 5,
    "include_relations": true
  }' | jq .

# 测试图谱探索
curl -X POST http://localhost:3000/api/v1/graph/explore \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "doc_123",
    "depth": 1
  }' | jq .
```

---

## 配置采集源

### 配置网页爬取

编辑 `crawler/sources.yaml`:

```yaml
sources:
  - id: "internal-wiki"
    name: "团队 Wiki"
    type: "web"
    enabled: true
    seed_urls:
      - "https://wiki.internal.com/"
    max_depth: 3
    max_pages: 500
    include_patterns:
      - "^/wiki/"
      - "^/docs/"
    exclude_patterns:
      - "/assets/"
      - "/static/"
    schedule: "0 3 * * *"  # 每天凌晨 3 点
    kb_id: "kb_internal"
```

### 配置 Git 仓库采集

编辑 `scheduler/config.yaml`:

```yaml
git_sources:
  - id: "backend-docs"
    name: "后端代码仓库"
    enabled: true
    url: "https://github.com/your-team/backend.git"
    branch: "main"
    local_path: "/data/repos/backend"
    kb_id: "kb_backend"
    include_patterns:
      - "docs/**/*.md"
      - "README.md"
      - "CHANGELOG.md"
    exclude_patterns:
      - ".git"
      - "node_modules"
    schedule: "0 5 * * *"  # 每天凌晨 5 点
```

### 配置本地文件监控

编辑 `scheduler/config.yaml`:

```yaml
file_watcher:
  enabled: true
  watch_dirs:
    - "/data/local-docs"
  include_patterns:
    - "*.md"
    - "*.rst"
    - "*.txt"
  kb_id: "kb_local"
```

---

## 监控与告警

### 启动监控栈

```bash
# 启动 Prometheus + Grafana + Alertmanager
docker-compose -f monitoring/docker-compose.monitoring.yml up -d

# 访问 Grafana
# http://localhost:3000 (默认账号 admin/admin)

# 访问 Prometheus
# http://localhost:9090

# 访问 Alertmanager
# http://localhost:9093
```

### 配置告警通知

编辑 `monitoring/alertmanager.yml`:

```yaml
receivers:
  - name: 'slack-receiver'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
        channel: '#alerts'
```

### 导入 Grafana 仪表盘

1. 访问 http://localhost:3000
2. Dashboards → Import
3. 输入仪表盘 ID 或上传 JSON 文件
4. 推荐仪表盘:
   - WeKnora Overview (ID: 10001)
   - PostgreSQL Metrics (ID: 9628)
   - Neo4j Monitoring (ID: 12012)

---

## 备份与恢复

### 配置备份

```bash
# 创建备份目录
mkdir -p /data/backups

# 运行备份脚本
./backup/backup-scripts.sh

# 手动备份 PostgreSQL
docker exec weknora-postgres pg_dump -U weknora weknora > backup-weknora.sql

# 手动备份 Neo4j
docker exec weknora-neo4j neo4j-admin dump --database=neo4j --to-path=/backups
```

### 恢复数据

```bash
# 恢复 PostgreSQL
cat backup-weknora.sql | docker exec -i weknora-postgres psql -U weknora -d weknora

# 恢复 Neo4j
docker exec weknora-neo4j neo4j-admin load --database=neo4j --from-path=/backups/neo4j.dump --force
```

---

## 常见问题

### Q1: WeKnora API 无法启动

```bash
# 检查日志
docker-compose -f docker-compose.prod.yml logs weknora-api

# 常见原因:
# 1. 数据库未就绪 - 等待 postgres 健康检查通过
# 2. 嵌入模型 API Key 错误 - 检查 .env 配置
# 3. 端口冲突 - 检查 3000 端口是否被占用
```

### Q2: 搜索结果为空

```bash
# 确认已导入数据
curl http://localhost:3000/api/v1/knowledge-bases/kb_default/stats

# 确认嵌入模型配置正确
curl -X POST http://localhost:3000/api/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"text": "test"}'

# 检查 pgvector 扩展
docker exec weknora-postgres psql -U weknora -c "SELECT * FROM pg_extension WHERE extname='vector';"
```

### Q3: Neo4j 连接失败

```bash
# 重启 Neo4j
docker-compose -f docker-compose.prod.yml restart neo4j

# 检查 Neo4j 状态
docker exec weknora-neo4j cypher-shell -u neo4j -p your_password "MATCH (n) RETURN count(n);"
```

### Q4: 爬虫无法抓取数据

```bash
# 检查爬虫日志
docker-compose -f docker-compose.prod.yml logs crawler

# 测试单页爬取
cd crawler
python crawler.py --source-id test --dry-run

# 检查网络连通性
docker exec weknora-crawler curl -I https://target-website.com
```

---

## 性能优化

### 数据库优化

```sql
-- 添加向量索引
CREATE INDEX ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 优化查询性能
ANALYZE documents;
VACUUM ANALYZE;
```

### Neo4j 优化

```cypher
// 添加索引
CREATE INDEX node_id_index FOR (n:Node) ON (n.id);
CREATE INDEX relationship_index FOR ()-[r:RELATED_TO]-() ON (r.type);

// 优化图谱查询
MATCH (n:Node)-[r]-(m:Node)
WHERE n.id = 'doc_123'
RETURN n, r, m
LIMIT 100;
```

### 缓存配置

```yaml
# Redis 缓存（可选）
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
```

---

## 下一步

1. **配置 MCP Server**: 参考 [MCP 工具文档](mcp_server/mcp_tools.py)
2. **集成 AI Agent**: 使用 MCP 协议连接 Claude/Copilot
3. **自定义采集源**: 根据团队需求添加新的数据源
4. **配置 SSO**: 集成企业统一认证
5. **设置告警**: 配置 Slack/邮件/钉钉告警

---

**文档版本**: 2026-05-10
**支持**: 参考 [WikiServer_服务器版 Wiki 完整实现方案.md](../WikiServer_服务器版 Wiki 完整实现方案.md)
