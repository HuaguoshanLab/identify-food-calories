# 基于 LangGraph 的多模态饮食健康智能 Agent

本仓库承载一个前后端分离、可追问、可校验、可追溯的饮食健康 Agent。当前阶段先建立 FastAPI、PostgreSQL、认证与权限基座；LangGraph、视觉识别和长期记忆会在后续阶段接入。未经过冻结评测和安全测试的能力不会在这里宣称达到生产指标。

## 职责

- `frontend/`：独立运行和构建的 React、TypeScript 与 Vite 用户端。
- `backend/`：FastAPI 模块化单体，依赖方向为 API → Application/Service → Repository → Model。
- `admin-frontend/`：Phase 6 才创建的独立后台前端，不能塞进用户 H5。
- PostgreSQL 保存权威业务数据；模型不得成为营养数值真相来源。
- v1 不引入微服务、Kafka、Kubernetes 或互相自由对话的多 Agent 网络。

## 允许依赖

- 用户端仅使用 React、TypeScript、Vite 与已批准的前端库，并通过公开 `/api/v1` 合约访问后端。
- 后端仅使用 FastAPI、Pydantic、SQLAlchemy 2、Alembic 与 PostgreSQL；认证、营养计算和权限规则不能交给模型决定。
- 本地集成可使用 Docker Compose 的 PostgreSQL 与 Mailpit；生产密钥、第三方账号和真实用户数据不进入仓库。

## 本地基础设施

Plan 01-01 提供独立开发/测试 pgvector 数据库与 Mailpit：

```bash
docker compose up -d --wait postgres postgres-test mailpit
docker compose ps
```

默认端口：开发库 `5432`、测试库 `55432`、Mailpit SMTP `1025`、Mailpit UI `8025`。所有端口只绑定本机回环地址。

服务端口与验证命令以 [`backend/README.md`](backend/README.md) 为准。生产密钥只通过未提交的环境变量提供；`.env.example` 仅记录变量名和安全占位值。

## 启动、迁移与验收

先启动本地依赖，再分别启动后端和用户端。不要把测试库当成开发库；`postgres-test` 是自动化测试唯一允许清空的数据源。

```bash
docker compose up -d --wait postgres postgres-test mailpit

cd backend
python3.11 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload

cd ../frontend
npm ci
npm run dev
```

测试迁移必须明确选择隔离库，随后再运行后端门禁；完整浏览器验收由 Playwright 管理 FastAPI、Vite、Mailpit 与测试数据库生命周期。

```bash
cd backend
APP_ENV=test DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev \
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test \
.venv/bin/alembic upgrade head
APP_ENV=test DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev \
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test \
.venv/bin/python -m pytest -q

cd ../frontend
npm run lint && npm run typecheck && npm run test && npm run test:e2e
```

管理员不通过用户 H5 创建。先注册、验证一个真实账号，然后按 [`backend/README.md`](backend/README.md#本地运行) 的 `app.admin.cli bootstrap` 或 `promote` 命令操作；两种操作都会留下可审计记录。

## 文件索引

| 路径 | 职责 |
|---|---|
| `AGENTS.md` | 全仓库架构、安全、测试与文档硬约束 |
| `.gitignore` | Node、Python、测试和本地环境生成物排除规则 |
| `frontend/` | React + TypeScript + Vite 用户端应用 |
| `backend/` | 后端运行时、迁移和测试 |
| `docker-compose.yml` | 本地 pgvector 双库与 Mailpit 编排 |
| `docs/` | 中文教学与工程使用文档 |
| `.planning/` | GSD 权威规划、需求、路线图与执行状态 |

## 文档维护

任何新目录必须在同一提交中提供 `README.md`，至少包含“职责”“允许依赖”“文件索引”；目录内容变化时同步更新父级索引。
