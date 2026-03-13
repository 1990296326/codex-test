# ES / Redis 管理控制台（FastAPI + Vue）

一个可直接运行的 ES/Redis 管理控制台，支持：

- 集群注册与管理（ES / Redis）
- 集群资源与健康状态查看
- 命令执行（带白名单限制）
- 工单提交与审批流（operator 提交，admin 审批）
- Redis 慢日志查询 / 慢日志阈值配置
- Elasticsearch 查询（DSL）与 slowlog 阈值配置
- 执行审计日志 + 过滤查询（按 cluster / 执行人 / 关键字）
- Docker / Docker Compose 一键部署

## 技术栈

- 后端：FastAPI + SQLAlchemy + SQLite
- 前端：Vue3（CDN）+ Tailwind（CDN）
- 中间件客户端：redis-py / elasticsearch-py

## 快速启动

### 方式 1：本地 Python

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

打开 `http://localhost:8000`

### 方式 2：Docker Compose（推荐）

```bash
docker compose up --build
```

服务：
- 控制台：`http://localhost:8000`
- Redis：`localhost:6379`
- Elasticsearch：`localhost:9200`

## 权限模型

通过请求头模拟登录：

- `X-User`: 用户名
- `X-Role`: 角色（`viewer` / `operator` / `admin`）

权限规则：
- `viewer`: 只读（集群、健康、日志、工单、慢日志、ES 查询）
- `operator`: 可提交工单、执行“已审批且一致”的命令
- `admin`: 全权限（可直接执行命令、审批工单、注册集群、更新慢日志阈值）

## 命令格式

### Redis
直接输入 Redis 命令（已内置白名单）：

示例：
- `PING`
- `SET key value`
- `GET key`
- `INFO`

### Elasticsearch
格式：

```text
METHOD /path {optional-json-body}
```

示例：
- `GET /_cluster/health`
- `GET /_cat/indices?format=json`
- `POST /my-index/_doc {"name":"demo"}`

## 新增运维接口（慢日志 / 查询）

### Redis 慢日志
- `GET /api/clusters/{id}/redis/slowlog?count=20`
- `GET /api/clusters/{id}/redis/slowlog/config`
- `PUT /api/clusters/{id}/redis/slowlog/config`

`PUT` 示例：

```json
{
  "slower_than_us": 20000,
  "max_len": 512
}
```

### ES 查询
- `POST /api/clusters/{id}/es/query`

请求体示例：

```json
{
  "index": "logs-*",
  "query": {"match_all": {}},
  "size": 20
}
```

### ES slowlog 设置
- `GET /api/clusters/{id}/es/slowlog/settings?index_pattern=*`
- `PUT /api/clusters/{id}/es/slowlog/settings`

`PUT` 示例：

```json
{
  "index_pattern": "logs-*",
  "search_warn_threshold": "1s",
  "indexing_warn_threshold": "1s"
}
```

## 可优化项（本次已提升）

- 命令最小权限白名单：减少高危命令误操作风险
- 审批前后状态流转：`pending -> approved/rejected -> executed`
- 审计日志查询：支持按执行人、集群、关键字过滤
- 慢日志开关与阈值化管理：便于性能问题排查

## 进一步建议

- 接入企业 SSO（OIDC）替代请求头模拟鉴权
- 工单支持多级审批、超时与自动提醒
- 命令模板中心（按场景固化）
- 敏感字段加密（KMS / Vault）
- 指标大盘接入 Prometheus + Grafana
