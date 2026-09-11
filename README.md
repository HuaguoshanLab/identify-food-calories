# 基于 LangGraph 的多模态饮食健康智能 Agent

本仓库承载一个前后端分离、可追问、可校验、可追溯的饮食健康 Agent。当前已交付认证、分析与确认保存、长期偏好、饮食规划、用户 records 看板及独立管理员后台。未经过冻结评测和安全测试的能力不会在这里宣称达到生产指标；Phase 6 的真实浏览器证据、自动化门禁与仍待复验边界见 [`docs/verification/phase-06-browser-acceptance.md`](docs/verification/phase-06-browser-acceptance.md)。

## 职责

- `frontend/`：独立运行和构建的 React、TypeScript 与 Vite 用户端。
- `backend/`：FastAPI 模块化单体，依赖方向为 API → Application/Service → Repository → Model。
- `admin-frontend/`：独立后台前端，不能塞进用户 H5；只访问公开 `/api/v1/admin/*`。
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

先启动本地依赖，再分别启动后端、用户端和独立后台。不要把测试库当成开发库；`postgres-test` 是自动化测试唯一允许清空的数据源。

```bash
docker compose up -d --wait postgres postgres-test mailpit

cd backend
uv python install 3.12
uv sync --extra dev --locked
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

cd ../frontend
npm ci
npm run dev

cd ../admin-frontend
npm ci
npm run dev
```

测试迁移必须明确选择隔离库，随后再运行后端门禁；完整浏览器验收由 Playwright 管理 FastAPI、Vite、Mailpit 与测试数据库生命周期。

```bash
cd backend
APP_ENV=test DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev \
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test \
uv run alembic upgrade head
APP_ENV=test DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev \
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test \
uv run pytest -q

cd ../frontend
npm run lint && npm run typecheck && npm run test && npm run test:e2e

cd ../admin-frontend
npm run typecheck && npm test && npm run build
```

`frontend` 固定在 `http://127.0.0.1:5178`，后台固定在 `http://127.0.0.1:5179`，FastAPI 默认在 `http://127.0.0.1:8000`。Records 与独立后台均已有 guarded Playwright 配置：runner 启动专属 FastAPI/Vite/Mailpit/测试库栈，走真实页面与公开 API，且不接受数据库 seed、token/Cookie 注入、mock endpoint 或内部调用作为证据。可分别运行：

```bash
cd frontend
E2E_FRONTEND_PORT=5182 E2E_BACKEND_PORT=8002 E2E_RECORDS_ADMIN_FRONTEND_PORT=5185 \
  npm run test:e2e -- --grep 'records-dashboard|真实登录后的记录页显示低覆盖周复盘'

cd ../admin-frontend
E2E_ADMIN_BACKEND_PORT=8003 E2E_ADMIN_USER_FRONTEND_PORT=5183 E2E_ADMIN_FRONTEND_PORT=5184 \
  npm run test:e2e -- --grep admin-management
```

`records-dashboard.spec.ts` 在 Shanghai 和 Los Angeles Chromium 时区上下文中观察 records-owned 统计时区确认先于看板读取；`records-weekly-review.spec.ts` 覆盖同一公开前置后的低覆盖安全投影；`admin-management.spec.ts` 覆盖管理员管理路径。它们是跨栈自动化证据，不替代 Codex 内置浏览器验收，也不宣称 UTC/DST/周一起点的精确数学；后者由确定性单元/API 测试负责，详见验收记录。

## Phase 6 架构与边界

```mermaid
flowchart LR
  H5[frontend: 用户 H5 SPA] -->|公开 /api/v1| API[FastAPI API]
  ADM[admin-frontend: 独立管理 SPA] -->|公开 /api/v1/admin/*| API
  API --> SVC[领域 Service / Application]
  SVC --> REPO[Repository]
  REPO --> PG[(PostgreSQL)]
  API --> AGENT[Agent API / LangGraph]
  AGENT --> TOOLS[受控 Tools]
  TOOLS --> SVC
  AGENT -. 只能读取确定性 facts .-> DASH[Dashboard weekly-review graph]
  DASH --> CACHE[(版本化 review cache)]
```

两份 SPA 都只能经公开 HTTP 合约访问后端；前端 route guard 不构成授权。管理员请求由 `app.admin.service.AdminService` 重新读取 PostgreSQL 当前角色，餐食和看板聚合只读取已确认快照。LangGraph 不直接访问数据库：Agent 只通过受控 tools 调用领域服务；周复盘 graph 只接收去标识、确定性的聚合 facts，Provider 不是营养数字或权限真相。

```mermaid
stateDiagram-v2
  [*] --> no_records
  no_records --> recorded: completed_validated 报告\n确认保存 + IANA 时区
  recorded --> overview: Service 固化 local_date\n并写入餐食快照
  overview --> history: 签名 keyset cursor
  overview --> insufficient: 覆盖不足
  overview --> reviewing: 覆盖合格且 cache miss
  reviewing --> reviewed: facts-only graph 通过语义阀
  reviewing --> safe_abstention: 安全/预算/停用/未知结果
  reviewed --> [*]
  insufficient --> [*]
  safe_abstention --> [*]
```

```mermaid
sequenceDiagram
  participant U as 用户 H5
  participant A as FastAPI / Agent
  participant R as Records Service
  participant D as Dashboard Service
  U->>A: 分析并确认保存（IANA time_zone）
  A->>R: 仅接受 completed_validated 报告
  R->>R: 固化 consumed_local_date
  R-->>U: 餐食详情与快照版本
  U->>R: 一次确认统计 IANA 时区
  U->>D: overview / history(cursor) / weekly-review（不携带客户端时区权威）
  D-->>U: 聚合事实、签名 cursor、闭合安全状态
```

```mermaid
sequenceDiagram
  participant M as 管理员 SPA
  participant A as Admin API
  participant S as Admin Service
  participant P as PostgreSQL
  M->>A: 草稿预览 / If-Match / 理由
  A->>S: DB-RBAC + 服务端 diff
  S->>P: 草稿、不可变 publication、eligibility history
  S->>P: append-only audit
  S-->>M: revision、影响范围和审计结果
  M->>A: runtime config 命令
  A->>S: 非密钥快照 + optimistic version
  S-->>M: 后续运行使用的新版本
```

## 调试与可追溯验收

- 后端读模型、cursor、facts-first cache：[`backend/app/dashboard/service.py`](backend/app/dashboard/service.py)、[`backend/tests/dashboard/test_dashboard_service.py`](backend/tests/dashboard/test_dashboard_service.py)。
- SSE 安全阶段：[`backend/app/agent/api.py`](backend/app/agent/api.py)、[`backend/tests/agent/test_safe_stream_stage_mapping.py`](backend/tests/agent/test_safe_stream_stage_mapping.py)。
- 管理员 DB RBAC、不可变目录和运行配置快照：[`backend/app/admin/service.py`](backend/app/admin/service.py)、[`backend/tests/admin/test_catalog_lifecycle_service.py`](backend/tests/admin/test_catalog_lifecycle_service.py)、[`backend/tests/admin/test_runtime_config_service.py`](backend/tests/admin/test_runtime_config_service.py)。
- 真实浏览器成功路径、边界和未完成项：[`docs/verification/phase-06-browser-acceptance.md`](docs/verification/phase-06-browser-acceptance.md)。

### 可验证的面试深挖题

1. 为什么保存请求必须提交 IANA 时区而不是由浏览器展示时再换算？从 [`backend/app/records/service.py`](backend/app/records/service.py) 和 [`backend/tests/integration/test_record_local_time_attribution.py`](backend/tests/integration/test_record_local_time_attribution.py) 追踪。
2. 为什么 dashboard history 使用签名 keyset cursor，而不是 offset？从 [`backend/app/dashboard/schemas.py`](backend/app/dashboard/schemas.py) 与 [`backend/tests/dashboard/test_dashboard_service.py`](backend/tests/dashboard/test_dashboard_service.py) 验证。
3. 为什么周复盘不把 Profile 或 Agent State 交给模型？对照 [`backend/app/dashboard/weekly_review_graph.py`](backend/app/dashboard/weekly_review_graph.py) 和冻结 [`backend/tests/evals/test_weekly_review_eval.py`](backend/tests/evals/test_weekly_review_eval.py)。
4. 为什么后台 UI 隐藏菜单不能替代 RBAC？从 [`backend/app/admin/api.py`](backend/app/admin/api.py)、[`backend/app/admin/service.py`](backend/app/admin/service.py) 与 [`backend/tests/unit/test_admin_rbac_api.py`](backend/tests/unit/test_admin_rbac_api.py) 检查。

管理员不通过用户 H5 创建。先注册、验证一个真实账号，然后按 [`backend/README.md`](backend/README.md#本地运行) 的 `app.admin.cli bootstrap` 或 `promote` 命令操作；两种操作都会留下可审计记录。

Phase 2 的真实 Provider 文案评测仅能使用 lockfile 中已批准的本地 CLI；它不是日常前端构建步骤，也不得用 `npx` 临时下载。Plan 02-17 获得明确付费授权后才可执行：

```bash
cd frontend
npx --no-install promptfoo eval -c ../backend/evals/promptfooconfig.yaml --no-cache
```

该命令会调用配置的 Provider，未获当次授权时禁止运行。

Phase 3 的图片冻结评测不调用真实模型，只回放合成、不可逆 fixture reference；任何哈希漂移、缺案例或关键安全失败都让报告失败：

```bash
cd backend
.venv/bin/python evals/evaluate_phase3.py \
  --dataset evals/phase03-cases.jsonl \
  --output evals/phase03-release.json
```

详见 [`docs/learning/phase-03-multimodal-meal-analysis.md`](docs/learning/phase-03-multimodal-meal-analysis.md)。

## 文件索引

| 路径 | 职责 |
|---|---|
| `AGENTS.md` | 全仓库架构、安全、测试与文档硬约束 |
| `.gitignore` | Node、Python、测试和本地环境生成物排除规则 |
| `frontend/` | React + TypeScript + Vite 用户端应用 |
| `admin-frontend/` | 独立 React + TypeScript + Vite 管理后台；仅调用公开 `/api/v1/admin/*` |
| `backend/` | 后端运行时、迁移和测试 |
| `docker-compose.yml` | 本地 pgvector 双库与 Mailpit 编排 |
| `docker-compose.langfuse.yml` | 默认关闭、仅环回暴露的本地 Langfuse 冻结评测镜像；独立网络、数据库与对象存储卷。 |
| `docs/` | 中文教学与工程使用文档 |
| `.planning/` | GSD 权威规划、需求、路线图与执行状态 |

## 文档维护

任何新目录必须在同一提交中提供 `README.md`，至少包含“职责”“允许依赖”“文件索引”；目录内容变化时同步更新父级索引。

### 今日计划存档

成功生成的三餐自动保存到 PostgreSQL，计划页刷新后恢复今日餐单；历史入口可查看旧版本并删除整日计划。个人身体资料仍由用户显式选择保存，计划不会直接计入实际摄入。升级执行 `cd backend && .venv/bin/python -m alembic upgrade head`。设计与验证方法见 [中文教学](docs/learning/daily-plan-archive.md)。
