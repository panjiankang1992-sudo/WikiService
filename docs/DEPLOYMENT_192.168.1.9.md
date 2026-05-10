# WikiService 部署到 192.168.1.9 服务器指南

## 部署方式（任选其一）

### 方式一：使用 Git 克隆（推荐）

**在服务器上执行：**

```bash
# SSH 登录服务器
ssh pankang@192.168.1.9

# 进入目标目录
cd /opt/mycode

# 克隆代码（如果需要，先配置 SSH key 或使用 HTTPS）
git clone <your-repo-url> WikiService
cd WikiService

# 运行部署脚本
chmod +x deploy.sh
./deploy.sh
```

---

### 方式二：SCP 上传部署包

**在本地执行：**

```bash
# 1. 创建部署包（排除不必要的文件）
cd D:/MyCode/WikiService
tar --exclude='.git' --exclude='test-data' --exclude='*.md' -czf weknora-deploy.tar.gz \
    docker-compose.prod.yml \
    docker/ \
    crawler/ \
    scheduler/ \
    ingester/ \
    mcp_server/ \
    deploy.sh \
    requirements.txt \
    .env.example

# 2. 上传到服务器
scp weknora-deploy.tar.gz pankang@192.168.1.9:/opt/mycode/

# 3. SSH 登录服务器
ssh pankang@192.168.1.9

# 4. 解压并部署
cd /opt/mycode
mkdir -p WikiService && cd WikiService
tar -xzf ../weknora-deploy.tar.gz

# 5. 创建 .env 文件
cat > .env << 'ENVEOF'
DB_PASSWORD=weknora_secure_db_pwd_2026
NEO4J_PASSWORD=weknora_secure_neo4j_pwd_2026
EMBEDDING_PROVIDER=deepseek
EMBEDDING_API_BASE=https://api.deepseek.com
EMBEDDING_API_KEY=sk-9538d57105d14bb194708e629c36ad74
EMBEDDING_MODEL=deepseek-chat
WEKNORA_KB_ID=kb_default
ENVEOF

# 6. 运行部署脚本
chmod +x deploy.sh
./deploy.sh
```

---

## 部署后验证

### 1. 检查服务状态

```bash
docker-compose -f docker-compose.linux.yml ps
```

预期输出：
```
NAME            STATUS         PORTS
weknora-api     Up (healthy)   0.0.0.0:29216->8080/tcp
weknora-ui      Up             0.0.0.0:29215->80/tcp
weknora-postgres Up (healthy)  0.0.0.0:29219->5432/tcp
weknora-neo4j   Up (healthy)   0.0.0.0:29217->7474/tcp, 0.0.0.0:29218->7687/tcp
```

### 2. 访问 Web UI

浏览器打开：`http://192.168.1.9:29215`

默认账号：`admin` / `admin`

### 3. 测试 API

```bash
curl http://192.168.1.9:29216/api/v1/health
```

### 4. 查看日志

```bash
# 全部日志
docker-compose -f docker-compose.linux.yml logs -f

# 特定服务日志
docker-compose -f docker-compose.linux.yml logs -f weknora-api
docker-compose -f docker-compose.linux.yml logs -f crawler
```

---

## 常用运维命令

```bash
# 启动所有服务
docker-compose -f docker-compose.linux.yml up -d

# 停止所有服务
docker-compose -f docker-compose.linux.yml down

# 重启服务
docker-compose -f docker-compose.linux.yml restart

# 查看资源使用
docker stats

# 清理未使用的容器/镜像
docker system prune -a

# 备份数据
docker-compose -f docker-compose.linux.yml exec postgres pg_dump -U weknora weknora > backup.sql
```

---

## 防火墙配置（如需要）

如果服务器有防火墙，需要开放端口：

```bash
# CentOS/RHEL
firewall-cmd --permanent --add-port=29215/tcp
firewall-cmd --permanent --add-port=29216/tcp
firewall-cmd --permanent --add-port=29217/tcp
firewall-cmd --permanent --add-port=29218/tcp
firewall-cmd --permanent --add-port=29219/tcp
firewall-cmd --reload

# Ubuntu/Debian
ufw allow 29215/tcp
ufw allow 29216/tcp
ufw allow 29217/tcp
ufw allow 29218/tcp
ufw allow 29219/tcp
```

---

## 故障排查

### 服务启动失败

```bash
# 查看 Docker 日志
journalctl -u docker -f

# 检查端口占用
netstat -tlnp | grep -E '2921[5-9]'

# 检查磁盘空间
df -h
docker system df
```

### 内存不足

```bash
# 查看内存使用
free -h
docker stats

# 限制容器内存（编辑 docker-compose.linux.yml）
# 添加：
#   deploy:
#     resources:
#       limits:
#         memory: 4G
```

### WeKnora 镜像拉取失败

WeKnora 是腾讯新开源的项目，如果官方镜像拉取失败：

1. 使用替代镜像或从源码构建
2. 或考虑使用 Dify 等替代方案

---

## 数据持久化

数据存储在 Docker volumes 中：
- `pgdata` - PostgreSQL 数据
- `neo4jdata` - Neo4j 图谱数据
- `weknora_storage` - 文件存储

备份建议：
```bash
# 定期备份到远程存储
docker-compose -f docker-compose.linux.yml exec postgres pg_dump -U weknora weknora | gzip > /backup/weknora-$(date +%Y%m%d).sql.gz
```
