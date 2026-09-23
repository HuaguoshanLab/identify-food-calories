# 基于 LangGraph 的多模态饮食健康智能 Agent

本仓库承载一个前后端分离、可追问、可校验、可追溯的饮食健康 Agent。当前已交付认证、分析与确认保存、长期偏好、饮食规划、用户 records 看板及独立管理员后台。未经过冻结评测和安全测试的能力不会在这里宣称达到生产指标；用户看板与后台的历史浏览器证据、自动化门禁与仍待复验边界见 [`docs/verification/2026-09-04-dashboard-admin-browser.md`](docs/verification/2026-09-04-dashboard-admin-browser.md)。

当前餐食分析、饮食规划与周总结均使用原生 LangGraph `StateGraph`；餐食分析和饮食规划通过 PostgreSQL Checkpointer 保存状态，并使用 `interrupt()` / `Command(resume=...)` 完成追问恢复。餐单由确定性规则生成：目标驱动候选组合、受控标签约束调整、目录重算与最终校验。流程测试仍不能替代真实模型效果评测。

日常变更门禁见 [Application quality](.github/workflows/quality.yml)：完整后端测试、两个前端的类型检查/单测/构建，以及餐单生成调整、后台运行配置和权限两组公开浏览器流程。其余历史 E2E 套件与 macOS 专用截图不在此门禁范围，真实模型评测独立于 CI。

## 产品与验证边界

产品场景、业务规则与验收条件见 [产品说明](docs/product.md)，待解决的问题见 [后续事项](docs/backlog.md)。

本地餐单生成、调整、刷新与历史版本已有[验收记录](docs/verification/2026-09-15-planning-optimization.md)。文本 Agent 的保留发布报告仍为 `FAIL`；真实模型质量、完整安全验收和生产部署不能从离线流程测试中推导。

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

本地基础设施提供独立开发/测试 pgvector 数据库与 Mailpit：

```bash
docker compose up -d --wait postgres postgres-test mailpit
docker compose ps
```

默认端口：开发库 `5432`、测试库 `55432`、Mailpit SMTP `1025`、Mailpit UI `8025`。所有端口只绑定本机回环地址。

服务端口与验证命令以 [`backend/README.md`](backend/README.md) 为准。生产密钥只通过未提交的环境变量提供；`.env.example` 仅记录变量名和安全占位值。

### 可选的本地追踪

Langfuse 是默认关闭的开发辅助栈，不影响主应用启动。需要时复制 `.env.langfuse.example`，生成独立强密钥，再使用 `docker-compose.langfuse.yml` 启动。完整配置、安全字段和排错方法见 [`docs/learning/feature-observability.md`](docs/learning/feature-observability.md)。

### 容器化应用启动

`docker-compose.app.yml` 构建并运行 FastAPI、用户端、管理端和独立 PostgreSQL。先创建生产环境使用的 `backend/.env`，至少设置强随机认证密钥、显式 CORS、Secure Cookie、邮件与实际启用的 Provider 配置；再设置数据库密码并执行迁移：

```bash
export POSTGRES_PASSWORD='replace-with-a-strong-random-password'
docker compose -f docker-compose.app.yml build
docker compose -f docker-compose.app.yml run --rm migrate
docker compose -f docker-compose.app.yml up -d backend frontend admin-frontend
docker compose -f docker-compose.app.yml ps
```

用户端和后台分别绑定本机 `5178`、`5179`。正式发布若要回滚应用，需预先保存上一版本的 immutable image；数据库迁移只能在确认对应 revision 支持降级后单独执行 `alembic downgrade`，不能把清库当作回滚。该 Compose 提供可重复的单机交付路径，不等于完成公网 TLS、备份恢复、密钥托管和生产安全验收。

上线前先在隔离环境演练数据库备份与恢复，并确认应用版本和数据库 revision 匹配。备份示例（在仓库根目录执行，归档放在仓库外并按敏感数据保护）：

```bash
umask 077
mkdir -p ../food-agent-backups
chmod 700 ../food-agent-backups
docker compose -f docker-compose.app.yml exec -T postgres \
  pg_dump -U postgres -d food_agent -Fc > ../food-agent-backups/food_agent.dump
docker compose -f docker-compose.app.yml exec -T postgres \
  pg_restore --list < ../food-agent-backups/food_agent.dump > /dev/null
```

`pg_restore --list` 只检查归档目录；必须在独立数据库中实际恢复，并通过公开 API 验证数据和业务路径，才能认定备份可用。恢复不得覆盖正在运行的业务库。应用回退时使用已保存的上一版本镜像，先核对 Alembic revision 与兼容性；不兼容时需要已验证的迁移降级或隔离恢复方案。当前 Compose 使用本地构建，未定义 immutable image 发布流程，因此此处尚不能宣称生产回退已通过。

## 启动、迁移与验收

先安装 Docker Compose、uv 和 Node.js（>=22.12.0）。不要把测试库当成开发库；`postgres-test` 是自动化测试唯一允许清空的数据源。

### 日常一键启动

完成下方首次配置后，在仓库根目录运行（macOS/Linux，需要 Python 3）：

```bash
python3 dev.py
```

自动启动 Docker 开发数据库、Mailpit、后端和两个前端，保留热更新，三个应用日志输出在同一个终端。按一次 `Ctrl+C` 统一停止应用及其子进程；任一应用进程退出时也会停止其余应用。端口被占用时会提示，不会终止已有服务。

数据库和 Mailpit 保留运行，可用 `docker compose stop postgres mailpit` 停止。基础设施已自行启动时可用 `python3 dev.py --skip-infra`。此命令不安装依赖、不修改 `.env`、不执行数据库迁移或数据初始化；拉取包含新迁移的代码后，先在 `backend/` 执行 `uv run alembic upgrade head`。

### 首次配置或分别启动

以下每个终端都从仓库根目录开始；首次完成依赖安装、环境配置、迁移及初始化后，可跳过分别启动三个应用的命令，改用上方一键启动。

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

混合菜品检索、受控索引构建和激活命令见 [检索评测与发布说明](backend/evals/phase_06_3/README.md)。release 不依赖 Langfuse 或付费 Provider：必须在真实 PostgreSQL 上运行完整测试及 `evaluate.py --verify-release`。只有 hash-bound PASS 证据、数据库管理员身份和明确 immutable build 同时存在时，才可按 `activate.py --help` 请求原子激活；不要猜测或复制生产参数。

混合检索的 GitHub CI 门禁定义在 [`.github/workflows/phase-063-frozen-retrieval.yml`](.github/workflows/phase-063-frozen-retrieval.yml)。它只启动 `postgres-test`，并固定执行：受保护初始化与 seed → 在 CI 临时目录生成 release → `--verify-release` → 相关真实 PostgreSQL 集成测试。需要本地复现时，在已启动 `postgres-test` 的前提下，从 `backend/` 依次运行：

```bash
uv run python tests/run_pg.py --env-file .env.test.example -- uv run python scripts/run_initialized_app.py --prepare-only
uv run python tests/run_pg.py --env-file .env.test.example -- uv run python evals/phase_06_3/evaluate.py --output /tmp/phase063-release.json
uv run python tests/run_pg.py --env-file .env.test.example -- uv run python evals/phase_06_3/evaluate.py --verify-release --output /tmp/phase063-release.json
uv run python tests/run_pg.py --env-file .env.test.example -- uv run --extra dev pytest -q tests/integration/test_hybrid_food_search.py tests/integration/test_catalog_embedding_jobs.py tests/integration/test_embedding_budget_ledger.py
```

## 架构摘要

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
  AGENT --> PROVIDERS[DeepSeek / Qwen-VL / Fake Providers]
```

两份 SPA 只能经公开 HTTP 合约访问后端，管理员授权由后端实时读取 PostgreSQL 角色。LangGraph 只通过受控 tools 调用领域服务，模型不是营养数字或权限真相。详细依赖方向见三个应用的 `ARCHITECTURE.md`。

## 调试与可追溯验收

- 后端读模型、cursor、facts-first cache：[`backend/app/dashboard/service.py`](backend/app/dashboard/service.py)、[`backend/tests/dashboard/test_dashboard_service.py`](backend/tests/dashboard/test_dashboard_service.py)。
- SSE 安全阶段：[`backend/app/agent/api.py`](backend/app/agent/api.py)、[`backend/tests/agent/test_safe_stream_stage_mapping.py`](backend/tests/agent/test_safe_stream_stage_mapping.py)。
- 管理员 DB RBAC、不可变目录和运行配置快照：[`backend/app/admin/service.py`](backend/app/admin/service.py)、[`backend/tests/admin/test_catalog_lifecycle_service.py`](backend/tests/admin/test_catalog_lifecycle_service.py)、[`backend/tests/admin/test_runtime_config_service.py`](backend/tests/admin/test_runtime_config_service.py)。
- 真实浏览器成功路径、边界和未完成项：[`docs/verification/2026-09-04-dashboard-admin-browser.md`](docs/verification/2026-09-04-dashboard-admin-browser.md)。

管理员创建、真实 Provider 评测和图片冻结评测都不是日常启动步骤。请分别查看 [`backend/README.md`](backend/README.md)、[`docs/learning/README.md`](docs/learning/README.md) 与 [`docs/verification/README.md`](docs/verification/README.md)；任何会调用付费 Provider 的评测都需要当次明确授权。

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

## 文档维护

只有新建顶级应用或业务模块根目录时必须提供 `README.md`。约定俗成的子目录不强制单独 README，普通文件增删不连锁更新多级索引。

### 今日计划存档

成功生成的三餐自动保存到 PostgreSQL，计划页刷新后恢复今日餐单；历史入口可查看旧版本并删除整日计划。个人身体资料仍由用户显式选择保存，计划不会直接计入实际摄入。升级执行 `cd backend && .venv/bin/python -m alembic upgrade head`。设计与验证方法见 [中文教学](docs/learning/feature-plan-archive.md)。
