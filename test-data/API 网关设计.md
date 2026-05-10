# API 网关设计

> API Gateway 作为微服务架构的统一入口，处理路由、认证、限流等跨领域关注点

---

## 一、API 网关的核心职责

### 1.1 请求路由

- 路径匹配和转发
- 负载均衡
- 协议转换（HTTP/HTTPS, HTTP/gRPC）

### 1.2 认证授权

- JWT 验证
- OAuth2 集成
- API Key 管理
- RBAC 权限检查

### 1.3 流量控制

- 限流（Rate Limiting）
- 熔断（Circuit Breaking）
- 降级（Fallback）
- 重试（Retry）

### 1.4 可观测性

- 访问日志
- 指标收集
- 链路追踪

### 1.5 其他功能

- 请求/响应转换
- API 版本管理
- CORS 处理
- WebSocket 支持

## 二、常见网关方案对比

| 网关 | 语言 | 特点 | 适用场景 |
|------|------|------|---------|
| **Kong** | Lua/Nginx | 插件丰富，性能优秀 | 通用 API 网关 |
| **APISIX** | Lua/Nginx | 国产开源，动态更新 | 云原生场景 |
| **Envoy** | C++ | 高性能，Service Mesh 首选 | 服务间通信 |
| **Nginx** | C | 成熟稳定，配置灵活 | 简单反向代理 |
| **Spring Cloud Gateway** | Java | Spring 生态集成好 | Java 技术栈 |
| **Traefik** | Go | 自动服务发现，Kubernetes 友好 | 容器化部署 |

## 三、Kong 网关实战

### 3.1 Docker 快速启动

```yaml
# docker-compose.yml
version: '3.8'
services:
  postgres:
    image: postgres:13
    environment:
      POSTGRES_DB: kong
      POSTGRES_USER: kong
      POSTGRES_PASSWORD: kong
    networks:
      - kong-network

  kong-migrations:
    image: kong:2.8
    command: kong migrations bootstrap
    environment:
      KONG_DATABASE: postgres
      KONG_PG_HOST: postgres
      KONG_PG_USER: kong
      KONG_PG_PASSWORD: kong
    depends_on:
      - postgres
    networks:
      - kong-network

  kong:
    image: kong:2.8
    ports:
      - "8000:8000"   # Proxy
      - "8443:8443"   # Proxy SSL
      - "8001:8001"   # Admin API
      - "8444:8444"   # Admin API SSL
    environment:
      KONG_DATABASE: postgres
      KONG_PG_HOST: postgres
      KONG_PG_USER: kong
      KONG_PG_PASSWORD: kong
      KONG_PROXY_ACCESS_LOG: /dev/stdout
      KONG_ADMIN_ACCESS_LOG: /dev/stdout
      KONG_PROXY_ERROR_LOG: /dev/stderr
      KONG_ADMIN_ERROR_LOG: /dev/stderr
      KONG_ADMIN_LISTEN: 0.0.0.0:8001
    depends_on:
      - kong-migrations
    networks:
      - kong-network
```

### 3.2 创建服务

```bash
# 添加后端服务
curl -X POST http://localhost:8001/services \
  --data "name=user-service" \
  --data "url=http://user-service:8080"

# 添加路由
curl -X POST http://localhost:8001/services/user-service/routes \
  --data "paths[]=/api/user" \
  --data "name=user-route"

# 测试路由
curl http://localhost:8000/api/user/123
```

### 3.3 添加插件

```bash
# 添加限流插件（每秒 10 个请求）
curl -X POST http://localhost:8001/services/user-service/plugins \
  --data "name=rate-limiting" \
  --data "config.second=10" \
  --data "config.policy=local"

# 添加 JWT 认证插件
curl -X POST http://localhost:8001/services/user-service/plugins \
  --data "name=jwt"

# 添加 CORS 插件
curl -X POST http://localhost:8001/services/user-service/plugins \
  --data "name=cors" \
  --data "config.origins=*" \
  --data "config.methods=GET,POST,PUT,DELETE"
```

### 3.4 JWT 认证流程

```bash
# 1. 创建消费者（用户）
curl -X POST http://localhost:8001/consumers \
  --data "username=alice"

# 2. 为消费者生成 JWT 凭证
curl -X POST http://localhost:8001/consumers/alice/jwt \
  --data "key=alice-key" \
  --data "secret=alice-secret"

# 3. 使用 JWT 访问 API
# 生成 JWT Token (可以使用 jwt.io)
# Payload: {"sub": "alice-key", "iat": 1234567890}
# Header: {"alg": "HS256", "typ": "JWT"}
# Sign with: alice-secret

curl -X GET http://localhost:8000/api/user/123 \
  -H "Authorization: Bearer <jwt-token>"
```

## 四、APISIX 网关实战

### 4.1 Docker 启动

```bash
docker run -d --name apache-apisix \
  -p 9080:9080 \
  -p 9091:9091 \
  -p 9444:9444 \
  apache/apisix
```

### 4.2 配置路由

```yaml
# conf.yaml
routes:
  - uri: /api/user/*
    name: user-service
    upstream:
      type: roundrobin
      nodes:
        "user-service:8080": 1
    plugins:
      - name: jwt-auth
      - name: limit-count
        config:
          count: 100
          time_window: 60
          policy: local
```

```bash
# 使用 Admin API 创建路由
curl http://127.0.0.1:9180/apisix/admin/routes/1 \
  -H 'X-API-KEY: edd1c9f034335f136f87ad84b625c8f1' \
  -X PUT \
  -d '{
    "uri": "/api/user/*",
    "name": "user-service",
    "upstream": {
      "type": "roundrobin",
      "nodes": {
        "user-service:8080": 1
      }
    },
    "plugins": [
      {"name": "jwt-auth"},
      {"name": "limit-count", "config": {"count": 100, "time_window": 60}}
    ]
  }'
```

## 五、自定义网关（基于 Spring Cloud Gateway）

### 5.1 依赖配置

```xml
<dependencies>
    <dependency>
        <groupId>org.springframework.cloud</groupId>
        <artifactId>spring-cloud-starter-gateway</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-data-redis</artifactId>
    </dependency>
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-security</artifactId>
    </dependency>
</dependencies>
```

### 5.2 路由配置

```yaml
# application.yml
spring:
  cloud:
    gateway:
      routes:
        - id: user-service
          uri: lb://user-service
          predicates:
            - Path=/api/user/**
          filters:
            - StripPrefix=1
            - name: RequestRateLimiter
              args:
                redis-rate-limiter.replenishRate: 10
                redis-rate-limiter.burstCapacity: 20
            - name: JwtAuthenticationFilter

        - id: order-service
          uri: lb://order-service
          predicates:
            - Path=/api/order/**
          filters:
            - StripPrefix=1
```

### 5.3 JWT 认证过滤器

```java
@Component
public class JwtAuthenticationFilter implements GlobalFilter, Ordered {

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        String authHeader = exchange.getRequest().getHeaders()
            .getFirst(HttpHeaders.AUTHORIZATION);

        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            exchange.getResponse().setStatusCode(HttpStatus.UNAUTHORIZED);
            return exchange.getResponse().setComplete();
        }

        String token = authHeader.substring(7);
        
        // 验证 JWT
        if (!JwtUtil.validate(token)) {
            exchange.getResponse().setStatusCode(HttpStatus.UNAUTHORIZED);
            return exchange.getResponse().setComplete();
        }

        // 传递用户信息到下游服务
        ServerHttpRequest request = exchange.getRequest().mutate()
            .header("X-User-Id", JwtUtil.getUserId(token))
            .build();

        return chain.filter(exchange.mutate().request(request).build());
    }

    @Override
    public int getOrder() {
        return -100; // 高优先级
    }
}
```

## 六、性能优化

### 6.1 缓存策略

- 静态资源 CDN
- Redis 缓存热点数据
- JWT 黑名单缓存

### 6.2 连接池

```yaml
# 配置连接池
spring:
  cloud:
    gateway:
      httpclient:
        pool:
          type: fixed
          max-connections: 1000
          acquire-timeout: 45000
```

### 6.3 超时配置

```yaml
spring:
  cloud:
    gateway:
      httpclient:
        response-timeout: 30s
        connect-timeout: 10s
```

## 七、监控与告警

### 7.1 Prometheus 指标

```yaml
# 开启指标
management:
  endpoints:
    web:
      exposure:
        include: prometheus
```

### 7.2 Grafana 仪表盘

关键指标面板：
- QPS（按服务）
- 响应时间 P50/P95/P99
- 错误率
- 限流触发次数

## 相关文档

- [[微服务架构设计原则]]
- [[分布式事务处理]]
- [[服务网格 Istio 入门]]

---

**最后更新**: 2026-05-10
**标签**: #api #gateway #微服务 #认证
