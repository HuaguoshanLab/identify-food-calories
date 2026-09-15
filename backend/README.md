# Backend

## 职责

`backend/` 是 Python 3.12+ FastAPI 模块化单体，负责 HTTP API、应用服务、持久化、安全边界以及后续 Agent 编排。它不包含 React 页面，也不允许模型编排层绕过领域服务直接访问数据库。

## 允许依赖

- FastAPI、Pydantic Settings、SQLAlchemy 2、Alembic、Psycopg 3。
- PostgreSQL/pgvector 是权威持久化与后续语义检索基础；测试禁止回退到 SQLite。
- 邮件通过可替换 Provider 发送，本地只连接 Mailpit，不需要云凭据。
- 依赖方向固定为 API → Application/Service → Repository → Model。

## 本地运行

先从仓库根目录启动依赖：`docker compose up -d --wait postgres postgres-test mailpit`。以下命令在 `backend/` 目录执行，要求已安装 uv；已有 `.env` 时保留原配置。

```bash
[ -f .env ] || cp .env.example .env
uv python install 3.12
uv sync --extra dev --locked
```

先按下方说明编辑 `.env`，再继续：

```bash
uv run alembic upgrade head
uv run python scripts/bootstrap_local_planning_data.py
uv run python scripts/setup_local_checkpointer.py
uv run uvicorn app.main:app --reload
```

运行后可访问 `http://127.0.0.1:8000/api/v1/health`。用户 H5 由 `frontend` 的 5178 端口代理公开 `/api/v1`；独立后台由 `admin-frontend` 的 5179 端口代理公开 `/api/v1/admin/*` 以及登录必要的公开认证路径。不要将两个 SPA 的端口、开发代理或管理员 access token 当作生产授权边界。

### 本地 Langfuse 调用追踪

根目录的独立 Compose 提供本地 Langfuse Web、Worker、Redis、PostgreSQL、ClickHouse 和 MinIO。先按 [`docs/learning/feature-observability.md`](../docs/learning/feature-observability.md) 生成 `.env.langfuse`、启动服务并在页面创建 `food-agent-dev` 项目。随后把项目 API Key 写入未提交的 `backend/.env`，设置：

```dotenv
TRACING_ENABLED=true
TRACING_BACKEND=langfuse
TRACING_HMAC_KEY=<openssl rand -base64 32>
TRACING_SERVICE_NAME=food-agent-backend
TRACING_SERVICE_VERSION=local-dev
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=http://127.0.0.1:3001
LANGFUSE_ENVIRONMENT=development
```

重启 FastAPI 后配置才会生效。开发环境可选 Langfuse；生产环境仍只允许 Phoenix。两种后端共享同一字段白名单，禁止发送用户身份、饮食原文、健康信息、图片、完整 Prompt、模型原文或思维链。

`.env.example` 当前开启 `REASONING_PROVIDER_MODE=deepseek`、`VISION_PROVIDER_MODE=qwen` 和 `EMBEDDING_PROVIDER_MODE=dashscope`，但不包含密钥。真实功能需要分别填写 `DEEPSEEK_API_KEY`、`QWEN_API_KEY` 和 `DASHSCOPE_API_KEY`，并确认对应模型、端点和价格快照适用于自己的服务配置。不能只填 DeepSeek Key 就认为图片识别和向量检索也可用。

只需离线调试时，在 `.env` 中将 `REASONING_PROVIDER_MODE`、`VISION_PROVIDER_MODE`、`EMBEDDING_PROVIDER_MODE` 和 `MEMORY_PROVIDER_MODE` 均设为 `fake`；这不提供真实模型能力。长期记忆默认 Fake，真实 Mem0 需另行配置。保持 `APP_ENV=local` 和模板开发库地址。规划种子与 Checkpointer 初始化脚本不读取 `.env`，默认连接本地 `food_agent_dev`；请勿让应用连接到另一数据库。

需要本地后台账号时，先在 `.env` 设置 `LOCAL_BOOTSTRAP_ADMIN_PASSWORD`（12–128 个字符），然后另开终端在 `backend/` 执行：

```bash
uv run python scripts/bootstrap_local_admin.py
```

使用 `admin@admin.com` 和自己设置的密码登录；重复执行不会重置已有管理员密码。

`bootstrap_local_admin.py` 只会在 `APP_ENV=local`、loopback 主机和固定 `food_agent_dev` 数据库上幂等创建 `admin@admin.com` 管理员，并保留角色审计记录。它要求在每台电脑未提交的 `backend/.env` 设置 `LOCAL_BOOTSTRAP_ADMIN_PASSWORD`；仓库和 `.env.example` 不保存密码。`bootstrap_local_planning_data.py` 只会在同一受保护范围内幂等导入受控食材与三餐种子；它不会 reset 数据库或写入用户资料。缺少这一步时，饮食规划没有合格候选，不能生成餐单。`setup_local_checkpointer.py` 只会在同一受保护的本地范围内幂等创建 LangGraph 的短期 State 表；它不会 reset、迁移或写入业务数据。缺少这一步时，健康检查仍会通过，但首次 Agent 分析会失败。

健康检查位于 `GET /api/v1/health`。从仓库根目录启动数据库和 Mailpit：

```bash
docker compose up -d --wait postgres postgres-test mailpit
```

连接边界：开发库 `localhost:5432/food_agent_dev`，测试库 `localhost:55432/food_agent_test`，Mailpit SMTP `localhost:1025`，UI `http://localhost:8025`。生产配置会拒绝弱密钥、非 Secure Cookie、通配 CORS、本地 Mailpit 和缺失 SMTP 凭据。

代码默认视觉模式为 Fake，但当前 `.env.example` 已显式开启 Qwen。只有在已人工核实 Model Studio 的区域、业务空间、模型可用性及数据处理条款后，才能在未提交的 `.env` 设置 `VISION_PROVIDER_MODE=qwen`、`QWEN_API_KEY`、业务空间的 `QWEN_BASE_URL`、模型和人民币价格快照。Qwen adapter 仅使用经过安全解码和元数据剥离后的短期图片引用；它不会记录图片、base64、prompt、完整模型输出或密钥。测试环境无条件使用 Fake Provider，不会触发付费模型调用。

图片分析先通过认证的 `POST /api/v1/agent/threads/image` 创建空图片线程，再以 multipart `POST /api/v1/agent/threads/{thread_id}/images` 上传且必须带 `Idempotency-Key`；不需要伪造文字命令。服务端先验证线程所有权，再按 MIME、大小、像素和真实解码规则归一化图片；持久化层只保留 opaque locator、digest、尺寸、过期/删除状态与受控调用计量。视觉调用结束后立即删除临时文件；保留 worker 会重试清理过期或待删除的 handle。线程快照只额外提供安全 recovery code，绝不公开 Provider 原文。

测试必须显式使用 `APP_ENV=test` 和独立的 `TEST_DATABASE_URL`；配置保护会拒绝 SQLite、开发库以及不以 `_test` 结尾的测试库。

所有真实 PostgreSQL 测试 child 必须通过受版本控制的环境合同和唯一 wrapper 启动；wrapper 保持 `DATABASE_URL` 指向开发哨兵、`TEST_DATABASE_URL` 指向隔离库，拒绝同目标、非 loopback、错误端口或错误库名，且不回显密码：

完整测试通过 `pyproject.toml` 的 `--import-mode=importlib` 按完整模块路径加载，避免 unit 与 integration 下同名测试相互覆盖。测试服务需启动 `postgres-test` 与 Mailpit；本机运行完整门禁时设置 `SMTP_HOST=127.0.0.1 SMTP_PORT=1025`。

```bash
uv run python tests/run_pg.py --env-file .env.test.example -- uv run python -m pytest tests/integration -q
```

迁移命令在 `APP_ENV=test` 时只读取通过上述保护的 `TEST_DATABASE_URL`。全栈 E2E 会先清空隔离库，再从 `0001` 显式升级到 `head`；开发库绝不参与这个过程：

```bash
APP_ENV=test \
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev \
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test \
uv run alembic upgrade head
```

完成后运行全部后端质量门禁：

```bash
APP_ENV=test DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev \
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test \
uv run pytest -q
uv run ruff check .
uv run mypy app
```

管理员只能通过后端 CLI 创建或提升，公开注册和用户 H5 没有角色输入。首次 bootstrap 必须使用已有、已验证且 active 的用户并写入 `system:bootstrap` 审计 actor；后续提升必须显式提供已验证、active 的现有管理员与非空 reason：

```bash
uv run python -m app.admin.cli bootstrap \
  --email first-admin@example.com \
  --reason "initial production administrator"

uv run python -m app.admin.cli promote \
  --actor-email existing-admin@example.com \
  --email next-admin@example.com \
  --reason "approved operational access"
```

两条命令都只接受已存在的账号；角色变化和 `admin_role_audit` 记录在同一个数据库事务内提交。CLI 拒绝匿名、未验证/inactive/non-admin actor、自我提升和空 reason。

## Phase 6 调试路径

```bash
# Dashboard / weekly-review 的 fake-repository 单测与冻结 eval
uv run pytest tests/dashboard tests/evals/test_weekly_review_eval.py -q

# 管理员 Service 与 HTTPX 合约
uv run pytest tests/admin tests/unit/test_admin_rbac_api.py tests/unit/test_admin_catalog_api.py tests/unit/test_admin_run_api.py -q

# 真实 PostgreSQL read model / publication / records（通过受保护 wrapper）
uv run python tests/run_pg.py --env-file .env.test.example -- \
  uv run pytest tests/integration/test_dashboard_repository.py tests/integration/test_dashboard_overview_projection.py tests/integration/test_catalog_publish_eligibility.py -q
```

Phase 6 迁移沿单一链顺延：Phase 5 的 `0011/0012` 后依次使用 `0013`（本地日）、`0014`（completion projection）、`0015`（weekly cache）、`0016`（admin audit）、`0017`（catalog draft）、`0018`（catalog lifecycle）与 `0019`（runtime config）。Phase 6.1 再接 `0020`（餐次）、`0021`（计划存档）、`0022`（餐食目录版本）、`0023`（成品菜候选）和 `0024`（候选可引用后台已发布目录）。只运行 `uv run alembic upgrade head`；不要手写 revision、跳过前驱或对开发库做测试 reset。

## 文件索引

| 路径 | 职责 |
|---|---|
| `AGENTS.md` | 后端局部实现与测试约束 |
| `ARCHITECTURE.md` | 后端模块地图、依赖方向、新代码落点和变更门禁 |
| `.gitignore` | 本地环境、缓存与测试产物排除规则 |
| `.env.example` | 可提交的本地环境模板；真实 Provider 需分别配置密钥，离线调试需改为 Fake |
| `.env.test.example` | 真实 PostgreSQL 测试 child 的固定、互异开发哨兵与测试库环境合同 |
| `pyproject.toml` | Python 包、运行依赖与测试配置 |
| `uv.lock` | 由 uv 维护的 Python 3.12+ 完整依赖锁；安装必须使用 `uv sync --locked` |
| `supply-chain-evidence-v1.schema.json` | 新增依赖人工或固定扫描器审核证据的版本化 JSON Schema |
| `supply-chain-evidence.json` | 当前新增依赖的 fail-closed 审核状态；`pending` 时禁止安装 |
| `validate_supply_chain.py` | 不执行 PATH 扫描器的供应链证据校验与自检 CLI |
| `alembic.ini` | Alembic CLI 与迁移脚本位置配置 |
| `app/` | FastAPI 应用代码 |
| `openapi-agent-v1.json` | 从运行时 FastAPI 生成并冻结的 Agent v1 公开合同；前端生成器会逐字校验 |
| `migrations/` | Alembic schema 变更脚本目录 |
| `evals/` | 无真实用户数据的 Phase 2 文字与 Phase 3 多模态冻结评测案例、Fake 回放和离线 hash/语义校验器 |
| `scripts/` | 受保护的测试数据库初始化、开发规划种子与 Checkpointer 初始化、应用启动入口 |
| `tests/` | 单元、集成和 API 合约测试 |
| `app/dashboard/` | 用户看板读模型、签名 cursor、facts-first 周复盘 cache 与安全 graph |
| `app/admin/` | DB-RBAC、审计、运行配置、目录草稿与 immutable publication 生命周期 |
| `app/planning/` | 身体资料、目标、计划存档，以及由营养目录引用支撑的受控菜谱和管理员候选餐单池。 |

### 正式餐单存档

`planning/archive_*` 提供 `/api/v1/planning/plans`（历史）、`/today`、`/{id}?version=N` 和 DELETE。运行完成与餐单版本同事务保存；迁移 `0021` 新增两张表。日期沿用确认的统计时区，旧临时结果不自动补存。详见 [教学文档](../docs/after/daily-plan-archive.md)。
