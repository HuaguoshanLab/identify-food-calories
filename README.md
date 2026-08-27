# 基于 LangGraph 的多模态饮食健康智能 Agent

本仓库承载一个前后端分离、可追问、可校验、可追溯的饮食健康 Agent。当前阶段先建立 FastAPI、PostgreSQL、认证与权限基座；LangGraph、视觉识别和长期记忆会在后续阶段接入。未经过冻结评测和安全测试的能力不会在这里宣称达到生产指标。

## 工程边界

- `frontend/`：独立运行和构建的 React、TypeScript 与 Vite 用户端。
- `backend/`：FastAPI 模块化单体，依赖方向为 API → Application/Service → Repository → Model。
- `admin-frontend/`：Phase 6 才创建的独立后台前端，不能塞进用户 H5。
- PostgreSQL 保存权威业务数据；模型不得成为营养数值真相来源。
- v1 不引入微服务、Kafka、Kubernetes 或互相自由对话的多 Agent 网络。

## 本地基础设施

Plan 01-01 提供独立开发/测试 pgvector 数据库与 Mailpit：

```bash
docker compose up -d --wait postgres postgres-test mailpit
docker compose ps
```

默认端口：开发库 `5432`、测试库 `55432`、Mailpit SMTP `1025`、Mailpit UI `8025`。所有端口只绑定本机回环地址。

服务端口与验证命令以 [`backend/README.md`](backend/README.md) 为准。生产密钥只通过未提交的环境变量提供；`.env.example` 仅记录变量名和安全占位值。

## 文件索引

| 路径 | 职责 |
|---|---|
| `AGENTS.md` | 全仓库架构、安全、测试与文档硬约束 |
| `.gitignore` | Node、Python、测试和本地环境生成物排除规则 |
| `frontend/` | React + TypeScript + Vite 用户端应用 |
| `backend/` | 后端运行时、迁移和测试 |
| `docker-compose.yml` | 本地 pgvector 双库与 Mailpit 编排 |
| `.planning/` | GSD 权威规划、需求、路线图与执行状态 |

## 文档维护

任何新目录必须在同一提交中提供 `README.md`，至少包含“职责”“允许依赖”“文件索引”；目录内容变化时同步更新父级索引。
