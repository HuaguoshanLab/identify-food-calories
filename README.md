# 基于 LangGraph 的多模态饮食健康智能 Agent

本仓库承载一个前后端分离、可追问、可校验、可追溯的饮食健康 Agent。当前已交付认证、分析与确认保存、长期偏好、饮食规划、用户 records 看板及独立管理员后台。未经过冻结评测和安全测试的能力不会在这里宣称达到生产指标；Phase 6 的真实浏览器证据、自动化门禁与仍待复验边界见 [`docs/verification/phase-06-browser-acceptance.md`](docs/verification/phase-06-browser-acceptance.md)。

## 交付状态

- Phase 1–06.3 共 129 个计划均已执行并产生 Summary；Phase 6、06.2 和 06.3 的最终验证已通过。
- Phase 2 已由用户手动接受为阶段完成，但当前 Spearman 发布报告仍为 `FAIL`，不得宣称该发布门禁已通过。
- Phase 5 的规划实现和组件证据已完成，但真实“生成后调整餐单”的 E2E 路径仍需人工复验。
- Phase 7“评测、安全与上线”尚未开始；项目当前不等于生产就绪。权威追踪见 [`.planning/REQUIREMENTS.md`](.planning/REQUIREMENTS.md)、[`.planning/ROADMAP.md`](.planning/ROADMAP.md) 和 [`.planning/STATE.md`](.planning/STATE.md)。

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

### 新电脑首次启动本地 Langfuse

本地 Langfuse 是独立的开发辅助栈，不包含在默认 `docker compose up` 中。新电脑需要先安装并启动 Docker Desktop（或提供 Docker Compose v2 的 Docker Engine），然后在仓库根目录确认：

```bash
docker version
docker compose version
```

复制未提交的环境模板：

```bash
cp .env.langfuse.example .env.langfuse
```

为 `.env.langfuse` 中前六个密码或 Secret 分别执行一次 `openssl rand -base64 32`，把每次结果填入对应变量；加密密钥单独执行 `openssl rand -hex 32`，其结果必须正好是 64 位十六进制字符：

```bash
openssl rand -base64 32
openssl rand -hex 32
```

不得继续使用模板中的 `replace-with-...` 占位值，也不要提交 `.env.langfuse`。配置完成后启动整个 Langfuse 栈并等待健康检查：

```bash
docker compose --env-file .env.langfuse -f docker-compose.langfuse.yml up -d --wait
docker compose --env-file .env.langfuse -f docker-compose.langfuse.yml ps
```

打开 `http://127.0.0.1:3001`，注册这台电脑上的本地账号，创建 `food-agent-dev` 项目，再到 **Project Settings → API Keys** 创建项目密钥。将 `LANGFUSE_PUBLIC_KEY` 和 `LANGFUSE_SECRET_KEY` 写入 `backend/.env`，并确认下列配置存在：

```dotenv
TRACING_ENABLED=true
TRACING_BACKEND=langfuse
TRACING_HMAC_KEY=<执行 openssl rand -base64 32 后得到的值>
TRACING_SERVICE_NAME=food-agent-backend
TRACING_SERVICE_VERSION=local-dev
LANGFUSE_PUBLIC_KEY=pk-lf-实际值
LANGFUSE_SECRET_KEY=sk-lf-实际值
LANGFUSE_BASE_URL=http://127.0.0.1:3001
LANGFUSE_ENVIRONMENT=development
```

然后按下文启动或重启 FastAPI。完成一次餐食分析后，在 Langfuse 的 **Tracing → Traces** 中应看到 `agent.run`、`agent.provider` 和营养查询节点。

后续开机只需重新启动容器；数据保存在 Docker volumes 中：

```bash
docker compose --env-file .env.langfuse -f docker-compose.langfuse.yml up -d --wait
```

停止容器但保留数据：

```bash
docker compose --env-file .env.langfuse -f docker-compose.langfuse.yml stop
```

排错时查看服务状态和日志：

```bash
docker compose --env-file .env.langfuse -f docker-compose.langfuse.yml ps
docker compose --env-file .env.langfuse -f docker-compose.langfuse.yml logs --tail=200 langfuse langfuse-worker
```

更完整的字段解释、安全边界和验证方法见 [`docs/learning/feature-observability.md`](docs/learning/feature-observability.md)。

## 启动、迁移与验收

先安装 Docker Compose、uv 和 Node.js（>=22.12.0）。以下每个终端都从仓库根目录开始；后端和两个前端是持续运行的进程，需要分别保留终端。不要把测试库当成开发库；`postgres-test` 是自动化测试唯一允许清空的数据源。

**终端 1：基础设施与后端。** 首次配置时复制模板；已有 `.env` 时保留原文件。

```bash
docker compose up -d --wait postgres postgres-test mailpit
cd backend
[ -f .env ] || cp .env.example .env
uv python install 3.12
uv sync --extra dev --locked
```

继续前先编辑 `backend/.env`：模板当前开启 DeepSeek、Qwen 和 DashScope，必须分别配置对应密钥及可用的模型、端点与价格快照。若只需离线调试流程，将以下配置改为 `fake`；Fake 不提供真实模型识别或推理能力。

```dotenv
REASONING_PROVIDER_MODE=fake
VISION_PROVIDER_MODE=fake
EMBEDDING_PROVIDER_MODE=fake
MEMORY_PROVIDER_MODE=fake
```

保留 `APP_ENV=local` 和模板中的本地开发数据库地址，然后在终端 1 的 `backend/` 目录继续：

```bash
uv run alembic upgrade head
uv run python scripts/bootstrap_local_planning_data.py
uv run python scripts/setup_local_checkpointer.py
uv run uvicorn app.main:app --reload
```

两条初始化命令可重复执行：分别导入受控食材/菜谱和创建 LangGraph 短期状态表，不能用 Alembic 迁移代替。它们使用代码默认的本地开发库配置（不读取 `.env`），仅允许 loopback 上的 `food_agent_dev`；运行时数据库应与其保持一致。缺少初始化时，即使健康检查通过，分析或规划仍可能失败。

需要本地管理员时，先在 `backend/.env` 设置 `LOCAL_BOOTSTRAP_ADMIN_PASSWORD`（12–128 个字符），再在 `backend/` 运行 `uv run python scripts/bootstrap_local_admin.py`，创建已验证的 `admin@admin.com`。此命令不会重置已有管理员密码；生产管理员流程见后端 README。

**终端 2：用户端。** 从仓库根目录运行：

```bash
cd frontend
npm ci
npm run dev
```

**终端 3：独立后台。** 从仓库根目录运行：

```bash
cd admin-frontend
npm ci
npm run dev
```

访问用户端 `http://127.0.0.1:5178`、后台 `http://127.0.0.1:5179`、后端健康检查 `http://127.0.0.1:8000/api/v1/health`；注册验证邮件在 `http://127.0.0.1:8025` 查看。后续启动保留 `.env`，执行迁移并启动三个服务；首次初始化和数据库重建后需执行上述初始化命令。

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
npm run typecheck && npm test && VITE_ADMIN_API_BASE_URL=/api/v1/admin npm run build
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

Phase 06.3 的混合菜品检索、受控索引构建和激活命令见 [`docs/after/phase-06.3-hybrid-food-search.md`](docs/after/phase-06.3-hybrid-food-search.md)。release 不依赖 Langfuse 或付费 Provider：必须在真实 PostgreSQL 上运行完整测试及 `evaluate.py --verify-release`。只有 hash-bound PASS 证据、数据库管理员身份和明确 immutable build 同时存在时，才可按 `activate.py --help` 请求原子激活；不要猜测或复制生产参数。

Phase 06.3 的 GitHub CI 门禁定义在 [`.github/workflows/phase-063-frozen-retrieval.yml`](.github/workflows/phase-063-frozen-retrieval.yml)。它只启动 `postgres-test`，并固定执行：受保护初始化与 seed → 在 CI 临时目录生成 release → `--verify-release` → 相关真实 PostgreSQL 集成测试。需要本地复现时，在已启动 `postgres-test` 的前提下，从 `backend/` 依次运行：

```bash
uv run python tests/run_pg.py --env-file .env.test.example -- uv run python scripts/run_initialized_app.py --prepare-only
uv run python tests/run_pg.py --env-file .env.test.example -- uv run python evals/phase_06_3/evaluate.py --output /tmp/phase063-release.json
uv run python tests/run_pg.py --env-file .env.test.example -- uv run python evals/phase_06_3/evaluate.py --verify-release --output /tmp/phase063-release.json
uv run python tests/run_pg.py --env-file .env.test.example -- uv run --extra dev pytest -q tests/integration/test_hybrid_food_search.py tests/integration/test_catalog_embedding_jobs.py tests/integration/test_embedding_budget_ledger.py
```

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

详见 [`docs/after/phase-03-multimodal-meal-analysis.md`](docs/after/phase-03-multimodal-meal-analysis.md)。

## 文件索引

| 路径 | 职责 |
|---|---|
| `AGENTS.md` | 全仓库架构、安全、测试与文档硬约束 |
| `.gitignore` | Node、Python、测试和本地环境生成物排除规则 |
| `frontend/` | React + TypeScript + Vite 用户端应用 |
| `admin-frontend/` | 独立 React + TypeScript + Vite 管理后台；仅调用公开 `/api/v1/admin/*` |
| `backend/` | 后端运行时、迁移和测试 |
| `docker-compose.yml` | 本地 pgvector 双库与 Mailpit 编排 |
| `docker-compose.langfuse.yml` | 默认关闭、仅环回暴露的本地 Langfuse 开发栈；含 Web、Worker、Redis、独立数据库与对象存储。 |
| `docs/` | 中文教学与工程使用文档 |
| `.planning/` | GSD 权威规划、需求、路线图与执行状态 |

## 文档维护

任何新目录必须在同一提交中提供 `README.md`，至少包含“职责”“允许依赖”“文件索引”；目录内容变化时同步更新父级索引。

### 今日计划存档

成功生成的三餐自动保存到 PostgreSQL，计划页刷新后恢复今日餐单；历史入口可查看旧版本并删除整日计划。个人身体资料仍由用户显式选择保存，计划不会直接计入实际摄入。升级执行 `cd backend && .venv/bin/python -m alembic upgrade head`。设计与验证方法见 [中文教学](docs/after/daily-plan-archive.md)。
