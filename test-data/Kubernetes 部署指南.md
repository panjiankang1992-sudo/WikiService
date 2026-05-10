# Kubernetes 部署指南

> 在 Kubernetes 集群中部署微服务的完整指南

---

## 一、前置要求

- Kubernetes 集群 (v1.20+)
- kubectl 命令行工具
- Docker 镜像仓库
- Helm (可选)

## 二、基础概念回顾

### 2.1 核心资源

| 资源 | 作用 |
|------|------|
| Pod | 最小调度单元，包含一个或多个容器 |
| Deployment | 管理 Pod 的副本数和版本 |
| Service | 服务发现和负载均衡 |
| Ingress | 外部访问入口 |
| ConfigMap | 配置管理 |
| Secret | 敏感信息管理 |

### 2.2 命名空间

```bash
# 创建命名空间
kubectl create namespace wiki-service

# 查看所有命名空间
kubectl get namespaces
```

## 三、部署微服务

### 3.1 编写 Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: user-service
  namespace: wiki-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: user-service
  template:
    metadata:
      labels:
        app: user-service
    spec:
      containers:
      - name: user-service
        image: registry.example.com/user-service:v1.0.0
        ports:
        - containerPort: 8080
        env:
        - name: DB_HOST
          valueFrom:
            configMapKeyRef:
              name: app-config
              key: db.host
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: db.password
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
```

### 3.2 编写 Service

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: user-service
  namespace: wiki-service
spec:
  selector:
    app: user-service
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8080
  type: ClusterIP  # 集群内部访问
```

### 3.3 编写 Ingress

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: wiki-ingress
  namespace: wiki-service
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  rules:
  - host: wiki.example.com
    http:
      paths:
      - path: /api/user
        pathType: Prefix
        backend:
          service:
            name: user-service
            port:
              number: 80
      - path: /api/order
        pathType: Prefix
        backend:
          service:
            name: order-service
            port:
              number: 80
```

## 四、部署命令

### 4.1 应用配置

```bash
# 创建命名空间
kubectl apply -f namespace.yaml

# 创建 ConfigMap
kubectl apply -f configmap.yaml

# 创建 Secret
kubectl apply -f secrets.yaml

# 部署服务
kubectl apply -f deployment.yaml

# 创建 Service
kubectl apply -f service.yaml

# 创建 Ingress
kubectl apply -f ingress.yaml
```

### 4.2 验证部署

```bash
# 查看 Pod 状态
kubectl get pods -n wiki-service

# 查看 Service
kubectl get svc -n wiki-service

# 查看 Ingress
kubectl get ingress -n wiki-service

# 查看日志
kubectl logs -f deployment/user-service -n wiki-service

# 进入 Pod 调试
kubectl exec -it deployment/user-service -n wiki-service -- /bin/sh
```

## 五、配置管理

### 5.1 ConfigMap

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: wiki-service
data:
  db.host: "postgres.wiki-service.svc.cluster.local"
  db.port: "5432"
  redis.host: "redis.wiki-service.svc.cluster.local"
  log.level: "info"
```

### 5.2 Secret

```yaml
# secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
  namespace: wiki-service
type: Opaque
stringData:
  db.password: "super-secret-password"
  jwt.secret: "jwt-signing-key"
```

```bash
# 从字面创建 Secret
kubectl create secret generic app-secrets \
  --from-literal=db.password=super-secret-password \
  --from-literal=jwt.secret=jwt-signing-key \
  -n wiki-service
```

## 六、滚动更新

### 6.1 更新镜像

```bash
# 更新镜像
kubectl set image deployment/user-service \
  user-service=registry.example.com/user-service:v1.1.0 \
  -n wiki-service

# 查看更新状态
kubectl rollout status deployment/user-service -n wiki-service

# 查看历史版本
kubectl rollout history deployment/user-service -n wiki-service

# 回滚到上一版本
kubectl rollout undo deployment/user-service -n wiki-service

# 回滚到指定版本
kubectl rollout undo deployment/user-service --to-revision=2 -n wiki-service
```

### 6.2 金丝雀发布

```yaml
# 金丝雀 Deployment（10% 流量）
apiVersion: apps/v1
kind: Deployment
metadata:
  name: user-service-canary
spec:
  replicas: 1  # 总副本数的 10%
  # ... 其他配置与主 Deployment 相同
```

## 七、自动扩缩容

### 7.1 HPA (Horizontal Pod Autoscaler)

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: user-service-hpa
  namespace: wiki-service
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: user-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

```bash
# 应用 HPA
kubectl apply -f hpa.yaml

# 查看 HPA 状态
kubectl get hpa -n wiki-service
```

## 八、健康检查

### 8.1 探针类型

| 探针 | 作用 | 失败后果 |
|------|------|---------|
| livenessProbe | 检测容器是否存活 | 重启容器 |
| readinessProbe | 检测容器是否就绪 | 从 Service 后端移除 |
| startupProbe | 检测应用是否启动完成 | 不执行其他探针直到成功 |

### 8.2 探针配置

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8080
  initialDelaySeconds: 15
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3
```

## 九、资源管理

### 9.1 Resource Quota

```yaml
# quota.yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: wiki-quota
  namespace: wiki-service
spec:
  hard:
    requests.cpu: "4"
    requests.memory: 8Gi
    limits.cpu: "8"
    limits.memory: 16Gi
    pods: "20"
```

### 9.2 Limit Range

```yaml
# limitrange.yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: wiki-limits
  namespace: wiki-service
spec:
  limits:
  - type: Container
    default:
      cpu: "500m"
      memory: "512Mi"
    defaultRequest:
      cpu: "100m"
      memory: "128Mi"
```

## 十、故障排查

### 10.1 常用命令

```bash
# 查看 Pod 详情
kubectl describe pod <pod-name> -n wiki-service

# 查看事件
kubectl get events -n wiki-service --sort-by='.lastTimestamp'

# 查看 Pod 日志
kubectl logs <pod-name> -n wiki-service

# 查看上一个实例的日志（重启后）
kubectl logs <pod-name> -n wiki-service --previous

# 进入 Pod 执行命令
kubectl exec -it <pod-name> -n wiki-service -- /bin/sh

# 端口转发（本地访问）
kubectl port-forward deployment/user-service 8080:8080 -n wiki-service
```

### 10.2 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| CrashLoopBackOff | 应用启动失败 | 检查日志，修复配置 |
| ImagePullBackOff | 镜像拉取失败 | 检查镜像名和凭证 |
| Pending | 资源不足 | 检查节点资源和调度策略 |
| OOMKilled | 内存超限 | 增加内存限制或优化代码 |

## 相关文档

- [[微服务架构设计原则]]
- [[Docker 容器化指南]]
- [[服务网格 Istio 入门]]
- [[Prometheus 监控配置]]

---

**最后更新**: 2026-05-10
**标签**: #kubernetes #docker #容器化 #devops
