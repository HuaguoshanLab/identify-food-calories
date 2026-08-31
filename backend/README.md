# Backend

## 职责

`backend/` 是 Python 3.11+ FastAPI 模块化单体，负责 HTTP API、应用服务、持久化、安全边界以及后续 Agent 编排。它不包含 React 页面，也不允许模型编排层绕过领域服务直接访问数据库。

## 允许依赖

- FastAPI、Pydantic Settings、SQLAlchemy 2、Alembic、Psycopg 3。
- PostgreSQL/pgvector 是权威持久化与后续语义检索基础；测试禁止回退到 SQLite。
- 邮件通过可替换 Provider 发送，本地只连接 Mailpit，不需要云凭据。
- 依赖方向固定为 API → Application/Service → Repository → Model。

## 本地运行

```bash
cp .env.example .env
python3.11 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
.venv/bin/alembic upgrade head
.venv/bin/python scripts/setup_local_checkpointer.py
.venv/bin/uvicorn app.main:app --reload
```

`setup_local_checkpointer.py` 只会在 `APP_ENV=local`、loopback 主机和固定 `food_agent_dev` 数据库上幂等创建 LangGraph 的短期 State 表；它不会 reset、迁移或写入业务数据。缺少这一步时，健康检查仍会通过，但首次 Agent 分析会失败。

健康检查位于 `GET /api/v1/health`。从仓库根目录启动数据库和 Mailpit：

```bash
docker compose up -d --wait postgres postgres-test mailpit
```

连接边界：开发库 `localhost:5432/food_agent_dev`，测试库 `localhost:55432/food_agent_test`，Mailpit SMTP `localhost:1025`，UI `http://localhost:8025`。生产配置会拒绝弱密钥、非 Secure Cookie、通配 CORS、本地 Mailpit 和缺失 SMTP 凭据。

视觉模型默认关闭。只有在已人工核实 Model Studio 的区域、业务空间、模型可用性及数据处理条款后，才能在未提交的 `.env` 设置 `VISION_PROVIDER_MODE=qwen`、`QWEN_API_KEY`、业务空间的 `QWEN_BASE_URL`、模型和人民币价格快照。Qwen adapter 仅使用经过安全解码和元数据剥离后的短期图片引用；它不会记录图片、base64、prompt、完整模型输出或密钥。测试环境无条件使用 Fake Provider，不会触发付费模型调用。

测试必须显式使用 `APP_ENV=test` 和独立的 `TEST_DATABASE_URL`；配置保护会拒绝 SQLite、开发库以及不以 `_test` 结尾的测试库。

所有真实 PostgreSQL 测试 child 必须通过受版本控制的环境合同和唯一 wrapper 启动；wrapper 保持 `DATABASE_URL` 指向开发哨兵、`TEST_DATABASE_URL` 指向隔离库，拒绝同目标、非 loopback、错误端口或错误库名，且不回显密码：

```bash
.venv/bin/python tests/run_pg.py --env-file .env.test.example -- .venv/bin/python -m pytest tests/integration -q
```

迁移命令在 `APP_ENV=test` 时只读取通过上述保护的 `TEST_DATABASE_URL`。全栈 E2E 会先清空隔离库，再从 `0001` 显式升级到 `head`；开发库绝不参与这个过程：

```bash
APP_ENV=test \
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev \
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test \
.venv/bin/alembic upgrade head
```

完成后运行全部后端质量门禁：

```bash
APP_ENV=test DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev \
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test \
.venv/bin/python -m pytest -q
ruff check .
mypy app
```

管理员只能通过后端 CLI 创建或提升，公开注册和用户 H5 没有角色输入。首次 bootstrap 必须使用已有、已验证且 active 的用户并写入 `system:bootstrap` 审计 actor；后续提升必须显式提供已验证、active 的现有管理员与非空 reason：

```bash
.venv/bin/python -m app.admin.cli bootstrap \
  --email first-admin@example.com \
  --reason "initial production administrator"

.venv/bin/python -m app.admin.cli promote \
  --actor-email existing-admin@example.com \
  --email next-admin@example.com \
  --reason "approved operational access"
```

两条命令都只接受已存在的账号；角色变化和 `admin_role_audit` 记录在同一个数据库事务内提交。CLI 拒绝匿名、未验证/inactive/non-admin actor、自我提升和空 reason。

## 文件索引

| 路径 | 职责 |
|---|---|
| `AGENTS.md` | 后端局部实现与测试约束 |
| `.gitignore` | 本地环境、缓存与测试产物排除规则 |
| `.env.example` | 可提交的环境变量契约，不包含真实密钥 |
| `.env.test.example` | 真实 PostgreSQL 测试 child 的固定、互异开发哨兵与测试库环境合同 |
| `pyproject.toml` | Python 包、运行依赖与测试配置 |
| `requirements.lock` | Python 3.11 下由 pip report 和下载产物生成的 hash-complete 依赖锁 |
| `lock_dependencies.py` | 生成并校验 pyproject 直接依赖、传递闭包与 SHA-256 锁文件的 CLI |
| `supply-chain-evidence-v1.schema.json` | 新增依赖人工或固定扫描器审核证据的版本化 JSON Schema |
| `supply-chain-evidence.json` | 当前新增依赖的 fail-closed 审核状态；`pending` 时禁止安装 |
| `validate_supply_chain.py` | 不执行 PATH 扫描器的供应链证据校验与自检 CLI |
| `alembic.ini` | Alembic CLI 与迁移脚本位置配置 |
| `app/` | FastAPI 应用代码 |
| `openapi-agent-v1.json` | 从运行时 FastAPI 生成并冻结的 Agent v1 公开合同；前端生成器会逐字校验 |
| `migrations/` | Alembic schema 变更脚本目录 |
| `evals/` | 无真实用户数据的 Phase 2 冻结 Agent 评测案例与离线 hash/语义校验器 |
| `scripts/` | 受保护的测试数据库初始化、开发 Checkpointer 初始化与应用启动入口 |
| `tests/` | 单元、集成和 API 合约测试 |
