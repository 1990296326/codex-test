# ES / Redis 管理控制台（FastAPI + Vue）

这是一个可直接部署的 ES/Redis 运维控制台，参考常见管理台能力做了增强：

- 集群管理、健康检查、连通性检测
- 仪表盘总览（集群/工单/执行日志/模板数量）
- 命令执行前预检（白名单/METHOD 检查）
- Redis 慢日志与阈值设置
- ES Query DSL 与 slowlog 设置
- 工单审批流与执行审计
- 命令模板中心
- 执行日志查询与 CSV 导出

## 快速启动

```bash
docker compose up --build
```

打开 `http://localhost:8000`。

> Docker Compose 中建议集群地址用 `redis:6379`、`elasticsearch:9200`；本地部署则用 `localhost`。

## 常用 API

- `GET /api/dashboard`：总览统计
- `GET /api/clusters/{id}/connectivity`：连通性探测
- `POST /api/commands/precheck`：执行前预检
- `GET /api/templates` / `POST /api/templates`：模板管理
- `GET /api/logs/export`：导出审计日志（CSV）

## 角色模型

- `viewer`：只读
- `operator`：可提交工单、预检、执行审批后的命令
- `admin`：全权限（集群、审批、模板、慢日志阈值、日志导出）
