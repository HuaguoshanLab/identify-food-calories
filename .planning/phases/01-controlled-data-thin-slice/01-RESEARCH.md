# Phase 1: 受控数据与可运行薄切片 - Research

**Researched:** 2026-08-26  
**Domain:** React/Vite + FastAPI + SQLAlchemy 2/Alembic/PostgreSQL 的受控菜品目录与确定性热量计算薄切片  
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### 首个可运行流程

- **D-01:** 第一条用户路径固定为“选择一道菜 → 输入克数 → 点击计算热量 → 查看结果”，本阶段不支持手动组合多道菜。
- **D-02:** 菜品选择使用可搜索下拉框，支持中文标准菜名和别名匹配；不能使用约 100 项的普通原生下拉框。
- **D-03:** 选择菜品后自动填入该菜的常见外卖份量，用户可以精确修改克数。
- **D-04:** 克数变化不会自动请求后端；用户点击明确的“计算热量”按钮后才调用 FastAPI。
- **D-05:** 第一阶段前端只突出菜名、克数和计算后的热量，不显示误差区间或营养数据来源。
- **D-06:** 营养来源和授权信息必须保存在数据库中并由 API 返回，但前端第一阶段不展示。

#### 首批菜品数据

- **D-07:** 先用 15 道代表菜验证 schema、迁移、别名搜索、种子导入和热量计算；数据结构稳定后在本阶段结束前扩充到约 100 道。
- **D-08:** 首批 15 道为：白米饭、蛋炒饭、炒面、番茄炒蛋、宫保鸡丁、鱼香肉丝、青椒肉丝、红烧肉、回锅肉、麻婆豆腐、土豆烧牛肉、清炒时蔬、酸辣土豆丝、红烧茄子、炸鸡排。
- **D-09:** 每道菜第一阶段只保留一套标准外卖配方；数据库设计可为未来多配方预留关系，但本阶段不实现多配方行为。
- **D-10:** 每道菜至少保存稳定 `dishId`、标准菜名、别名、每 100g 热量、常见份量克数、来源、授权状态和数据版本。
- **D-11:** 允许明确标记为 `demo_only` 的研究或人工整理值用于本地开发学习；只有 `production_approved` 数据可以进入公开生产环境。
- **D-12:** 应建立可自动验证的生产阻断，不能只靠文档提醒避免 `demo_only` 数据上线。

#### 后端学习深度

- **D-13:** API 从第一阶段使用 `/api/v1` 路径前缀，并保留 FastAPI `/docs` 和 `/openapi.json`。
- **D-14:** 后端严格拆分 API、Service、Repository、Schema 和 Model：API 处理 HTTP，Service 执行业务规则，Repository 负责持久化，Schema 定义 Pydantic 契约，Model 定义 SQLAlchemy 映射。
- **D-15:** API 不得直接调用 SQLAlchemy 查询；Pydantic Schema 与 SQLAlchemy Model 必须分离，公共 API 不能直接暴露 ORM Model。
- **D-16:** Service 单元测试使用假的 Repository，不连接数据库。
- **D-17:** Repository 集成测试连接独立 PostgreSQL 测试库，不用 SQLite 替代 PostgreSQL。
- **D-18:** API 测试验证状态码、请求/响应 Schema 和结构化错误响应。
- **D-19:** 根目录 `README.md` 说明项目结构和完整启动顺序；`backend/README.md` 说明分层职责、依赖方向、环境变量、迁移和测试命令。
- **D-20:** 文档包含 FastAPI 自动文档入口、查询菜品/计算热量/错误响应的 `curl` 示例，以及一张简洁数据流图；不编写大段理论教程。

#### 本地启动体验

- **D-21:** Docker Compose 默认只启动 PostgreSQL，不把 pgAdmin 或其他数据库 GUI 作为项目依赖。
- **D-22:** 文档可以使用 DBeaver Community 作为图形化数据库查看示例，但开发者也可使用 DataGrip、VS Code PostgreSQL 扩展或 `psql`。
- **D-23:** 前端和后端分别维护 `.env.example`；真实 `.env` 必须被 Git 忽略，前端环境只暴露允许公开的配置。
- **D-24:** Alembic migration 和菜品种子导入使用独立、显式命令；FastAPI 启动时不得自动建表、迁移或灌数据。
- **D-25:** 本地默认端口固定为 Vite `5173`、FastAPI `8000`、PostgreSQL `5432`。
- **D-26:** 开发环境 CORS 只允许 `http://localhost:5173`，不得使用 `*`。
- **D-27:** 前端与后端分别在独立终端启动，日志分开查看；不要求一条命令隐藏所有启动步骤。

### the agent's Discretion

- 在已批准分层内确定具体 Python 包路径、类名、函数名和依赖注入写法。
- 确定数据库表名、字段名、索引和约束，只要完整支持上述数据与授权规则。
- 确定热量显示的合理取整方式、表单校验细节和第一阶段的视觉样式。
- 选择符合批准技术栈的包管理器、lint/format 工具和测试目录结构，并在 README 中给出明确命令。

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|---|---|---|
| ARCH-01 | 独立 `frontend/` 和 `backend/` 项目 | 推荐结构、独立依赖清单、根 Compose 与 README。 |
| ARCH-02 | React/TypeScript/Vite 经 REST 调后端 | Vite React TS、TanStack Query 与显式 mutation 流程。 |
| ARCH-03 | FastAPI/Python/SQLAlchemy 2/Alembic | 分层依赖方向、同步 SQLAlchemy 2、Alembic 与测试策略。 |
| ARCH-04 | PostgreSQL 保存受控目录关系 | `dish`、`dish_alias`、`standard_recipe`、`nutrition_record`、`data_version` 的关系及约束。 |
| ARCH-05 | 版本化 OpenAPI 契约 | `/api/v1` 路由、Pydantic schema、`/openapi.json` 契约快照测试。 |
| ARCH-06 | Compose 启动 PostgreSQL | 最小 `compose.yaml`、健康检查、端口与 `.env` 边界。 |
| DATA-01 | 稳定菜品、别名、配方、营养、来源、授权、版本 | 种子 manifest、稳定外部 `dishId`、可追溯关系与完整性检查。 |
| DATA-04 | 未获商用授权的数据不可公开发布 | 由数据库资格字段、种子验证和 release-preflight 命令共同执行的硬门禁。 |
| CAL-01 | 受控营养数据决定性计算热量 | Service 只接收 `dish_id` 与克数，Repository 返回已批准的营养记录；公式单一实现并测试。 |
</phase_requirements>

## Project Constraints (from AGENTS.md)

- 必须保持 React + TypeScript + Vite 前端，以及 FastAPI + Pydantic + SQLAlchemy 2 + Alembic + PostgreSQL 后端；`frontend/`、`backend/` 是独立项目。 [VERIFIED: AGENTS.md]
- 不得改回 Next.js 单体；首版只能有一个前端、一个 FastAPI 后端和一个 PostgreSQL。未经真实延迟/可靠性证据，不引入微服务、消息队列或分布式任务系统。 [VERIFIED: AGENTS.md]
- 热量只能由受控菜品目录与营养数据决定性计算；视觉模型不能输出最终热量。 [VERIFIED: AGENTS.md]
- PostgreSQL 保存菜品、别名、营养版本、匿名结构化结果和用户修正；原图仅当次分析后删除且不长期保存。 [VERIFIED: AGENTS.md]
- 共享 API/计算规则必须保持单一事实来源；禁止前后端复制公式导致漂移。 [VERIFIED: AGENTS.md]
- 数据库 schema 的任何变更必须走 Alembic migration；API 输入/输出与模型响应必须运行时校验。 [VERIFIED: AGENTS.md]
- 不记录原图、base64、完整模型响应或其他不必要敏感信息；质量指标来自冻结评测集。 [VERIFIED: AGENTS.md]
- 除非用户明确绕过，实施应走合适的 GSD 工作流；本次研究仅产出规划文件。 [VERIFIED: AGENTS.md]

## Summary

Phase 1 应建立一个真正可运行的单菜垂直切片，而不是伪造数据或只做 UI。浏览器只做选择、克数输入和显示；FastAPI API 只做 HTTP/Pydantic/OpenAPI；Service 执行“受支持菜品 + 正克数 + 已批准营养记录”的业务规则；Repository 是唯一访问 SQLAlchemy 的位置；PostgreSQL 通过 Alembic 管理 schema。这个边界直接满足 D-14/D-15，也为 Phase 2 的识别和 Phase 3 的修正留下稳定接点。 [VERIFIED: project CONTEXT.md + AGENTS.md]

数据许可门禁不能写成 README 里的句子。将 `data_version.release_status` 约束为 `demo_only | production_approved`，让 `nutrition_record` 外键指向版本；公开生产配置的 `release-preflight` 必须查询并失败于任何正在提供的非 `production_approved` 记录、缺来源 URL、缺 license/reference、或缺 derivation note。种子导入也必须在事务内做相同校验。这样本地可使用标注清楚的 demo 数据，生产则无从“意外带入”。PostgreSQL 的 `CHECK` 只适合当前行不变量，跨表批准资格应由显式 preflight 查询保证；官方文档明确警告不要用跨行/跨表 `CHECK` 维持一致性。 [CITED: https://www.postgresql.org/docs/current/ddl-constraints.html]

迁移和种子必须分开：`alembic upgrade head` 只改变结构，`python -m app.scripts.seed_catalog` 只在显式命令下导入可复现数据。不要在 FastAPI lifespan/startup 调 `create_all()`、迁移或 seed；那会让运行服务有不可审计的 schema/data 副作用，并直接违反 D-24。Alembic 官方把自动生成定义为候选迁移，要求人工审阅；可用 `alembic check` 阻止 ORM metadata 与迁移历史漂移。 [CITED: https://alembic.sqlalchemy.org/en/latest/autogenerate.html]

**Primary recommendation:** 使用同步 SQLAlchemy 2 + `psycopg` 的 PostgreSQL 连接、Alembic 管理 schema、JSON/CSV 受控种子 manifest、显式 `release-preflight`，并交付 `GET /api/v1/dishes?query=` 与 `POST /api/v1/calculations` 的最小 OpenAPI 契约。 [VERIFIED: official FastAPI, SQLAlchemy, Alembic, Psycopg documentation]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| 中文菜名/别名搜索与选择 | Browser / Client | API / Backend | 客户端承载可访问 combobox；API 提供受控搜索结果，不能让前端复制目录。 [VERIFIED: project CONTEXT.md] |
| 常见份量预填和克数格式校验 | Browser / Client | API / Backend | UI 从选中 dish 返回的默认克数填表；API 仍对克数边界做权威校验。 [VERIFIED: project CONTEXT.md] |
| 热量计算 | API / Backend | Database / Storage | 公式只在 Service 一处执行；数值和资格来自数据库，浏览器不复制计算规则。 [VERIFIED: AGENTS.md] |
| 菜品/别名/配方/营养/版本/许可的持久化 | Database / Storage | API / Backend | PostgreSQL 是受控目录与可追溯链的事实来源；Repository 负责读写。 [VERIFIED: AGENTS.md] |
| 公共发布数据资格 | API / Backend | Database / Storage | preflight 扫描数据库并根据运行环境失败，不能靠 UI 或文档。 [VERIFIED: project CONTEXT.md] |
| REST/OpenAPI 契约 | API / Backend | Browser / Client | Pydantic schema 从 API 生成 OpenAPI；前端是消费者并在 CI 验证契约。FastAPI 会把声明和依赖校验纳入 OpenAPI。 [CITED: https://fastapi.tiangolo.com/tutorial/dependencies/] |

## Standard Stack

### Core

| Library | Version to lock during implementation | Purpose | Why Standard |
|---|---:|---|---|
| `fastapi` | `0.128.8` | API、Pydantic 驱动的输入输出校验、OpenAPI/docs | FastAPI 基于 OpenAPI/JSON Schema 并提供自动交互文档；当前 PyPI index 已核对版本。 [VERIFIED: PyPI index + https://fastapi.tiangolo.com/features/] |
| `SQLAlchemy` | `2.0.52` | ORM model、关系、事务、Repository | 需求已锁定 SQLAlchemy 2；使用 `DeclarativeBase`、`Mapped`、`mapped_column` 的 2.0 风格。 [VERIFIED: PyPI index + https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html] |
| `alembic` | `1.16.5` | 可审阅、可升级的 PostgreSQL schema migration | Alembic 是 SQLAlchemy 的轻量 migration 工具，当前 PyPI index 已核对版本。 [VERIFIED: PyPI index + https://alembic.sqlalchemy.org/en/latest/] |
| `psycopg[binary]` | `3.2.13` | 同步 PostgreSQL DBAPI | 官方安装文档确认包名为 `psycopg`，开发环境可选 binary extra；SQLAlchemy 对应 URL 是 `postgresql+psycopg://`。 [VERIFIED: PyPI index + https://www.psycopg.org/psycopg3/docs/basic/install.html + https://docs.sqlalchemy.org/en/20/dialects/postgresql.html] |
| `react` / `react-dom` | `19.2.8` / `19.2.8` | 单页客户端 UI | 项目批准的前端基础；版本已由 npm registry 核对。 [VERIFIED: npm registry + AGENTS.md] |
| `vite` + `typescript` + `@vitejs/plugin-react` | `8.2.2` / `7.0.2` / `6.1.0` | React TypeScript 开发与构建 | Vite 官方提供 React TypeScript 模板；当前 Node `22.23.2` 满足 Vite 要求的 Node `20.19+` 或 `22.12+`。 [VERIFIED: npm registry + https://vite.dev/guide/] |
| `@tanstack/react-query` | `5.102.5` | 菜品查询缓存与“点击计算” mutation 的 pending/error 状态 | 官方定位为 server state 的 fetching/caching/synchronizing；不把网络状态手写散落进组件。 [VERIFIED: npm registry + https://tanstack.com/query/latest/docs/framework/react/overview] |
| `@headlessui/react` | `2.2.10` | 可访问的搜索 combobox | 官方 Combobox 是带键盘支持的 accessible autocomplete，且把过滤逻辑留给应用；正合 D-02。 [VERIFIED: npm registry + https://headlessui.com/react/combobox] |

### Supporting

| Library | Version to lock during implementation | Purpose | When to Use |
|---|---:|---|---|
| `pydantic-settings` | `2.11.0` | 后端 `DATABASE_URL`、`CORS_ORIGINS`、`APP_ENV` 等配置加载和校验 | 所有运行配置集中在 `Settings`；官方支持 `.env` 且环境变量优先。 [VERIFIED: PyPI index + https://docs.pydantic.dev/latest/concepts/pydantic_settings/] |
| `uvicorn[standard]` | `0.39.0` | 本地 ASGI server | 单独启动 FastAPI 的开发命令；官方说明 Uvicorn 是可手动安装的 ASGI server。 [VERIFIED: PyPI index + https://fastapi.tiangolo.com/deployment/manually/] |
| `tailwindcss` + `@tailwindcss/vite` | `4.3.3` / `4.3.3` | 移动优先样式 | 项目锁定 Tailwind；官方 Vite 集成明确使用该 plugin。 [VERIFIED: npm registry + https://tailwindcss.com/docs/installation/using-vite] |
| `react-router-dom` | `7.18.2` | 前端路由骨架 | 现在只需一个主页面，但按批准栈建立 `BrowserRouter`，避免以后迁移路由结构。 [VERIFIED: npm registry + AGENTS.md] |
| `pytest` + `httpx` | `8.4.2` / `0.28.1` | 后端单元、PostgreSQL integration、FastAPI API 测试 | FastAPI `TestClient` 依赖 `httpx`，可直接以 pytest 测状态码与 JSON。 [VERIFIED: PyPI index + https://fastapi.tiangolo.com/tutorial/testing/] |
| `vitest` [WARNING: slopcheck flagged as suspicious — verify before using.] | `4.1.11` | 前端单元/组件测试 | 官方文档指定 `npm install -D vitest`；slopcheck 的 `vite` 近似名规则误报为 SUS，但实施前仍必须执行人工包名核验。 [VERIFIED: npm registry + https://vitest.dev/guide/] |
| `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event` | `16.3.2`, `7.0.1`, `14.6.6` | 以用户可见 DOM、真实交互测试表单/combobox | Testing Library 建议按 DOM/用户视角查询；`user-event` 模拟完整浏览器交互。 [VERIFIED: npm registry + https://testing-library.com/docs/react-testing-library/intro/ + https://testing-library.com/docs/user-event/intro/] |
| `playwright` | `1.62.1` | 跨前后端的浏览器 smoke/E2E | 项目批准 Playwright；官方提供现有项目安装流程。 [VERIFIED: npm registry + https://playwright.dev/docs/intro] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|---|---|---|
| Headless UI Combobox | 原生 `<select>` | 禁止：约 100 项且需中文别名搜索，原生 select 不满足 D-02。 [VERIFIED: project CONTEXT.md] |
| PostgreSQL integration tests | SQLite | 禁止：D-17 明确要求独立 PostgreSQL 测试库；不同 dialect 会掩盖约束、数值与 migration 问题。 [VERIFIED: project CONTEXT.md] |
| 同步 SQLAlchemy Session | async SQLAlchemy | Phase 1 不需要并发型 I/O；同步 Session + 普通 Repository 更小、更适合学习边界。 [ASSUMED] |
| JSON/CSV seed manifest + import command | data migration 塞入每个 Alembic revision | schema migration 和可重复数据装载会耦合，许可数据更新会变成不可回滚的 migration 历史；Phase 1 采用独立 seed 命令。 [ASSUMED] |

**Installation:** 实施时锁定到上述已核对的版本并生成 lockfile；不要照抄浮动 `latest`。 [VERIFIED: npm registry + PyPI index]

```bash
# frontend/
npm install react@19.2.8 react-dom@19.2.8 @tanstack/react-query@5.102.5 \
  react-router-dom@7.18.2 @headlessui/react@2.2.10 tailwindcss@4.3.3 @tailwindcss/vite@4.3.3
npm install -D vite@8.2.2 typescript@7.0.2 @vitejs/plugin-react@6.1.0 \
  vitest@4.1.11 @testing-library/react@16.3.2 @testing-library/jest-dom@7.0.1 \
  @testing-library/user-event@14.6.6 playwright@1.62.1

# backend/ (exact package manager is discretionary; examples show package names)
pip install fastapi==0.128.8 "uvicorn[standard]==0.39.0" sqlalchemy==2.0.52 \
  alembic==1.16.5 "psycopg[binary]==3.2.13" pydantic-settings==2.11.0
pip install pytest==8.4.2 httpx==0.28.1
```

**Version verification:** 2026-08-26 已对 Python 包执行 `pip index versions <pkg>`、对 Node 包执行 `npm view <pkg> version`，并检查所有推荐 npm 包的 `scripts.postinstall` 字段；未返回 postinstall 值。实施前再次运行同一命令并写入 lockfile，因为 registry 版本会变化。 [VERIFIED: PyPI index + npm registry]

## Package Legitimacy Audit

> 审计使用了只读 `slopcheck scan <package> --pkg <ecosystem> --json`，而没有按旧协议的 `slopcheck install`：该子命令会真的安装所有通过包，超出“只研究、不得改项目依赖”的授权。所有候选均已被 registry 扫描；无 SLOP。 [VERIFIED: local slopcheck 0.6.1 CLI/source]

| Package group | Registry | Current version | Source evidence | slopcheck | Disposition |
|---|---|---:|---|---|---|
| `fastapi`, `sqlalchemy`, `alembic`, `psycopg`, `pydantic-settings`, `uvicorn`, `pytest`, `httpx` | PyPI | `0.128.8`, `2.0.52`, `1.16.5`, `3.2.13`, `2.11.0`, `0.39.0`, `8.4.2`, `0.28.1` | 各自官方文档与 PyPI index | OK | Approved. [VERIFIED: PyPI index] |
| `react`, `react-dom`, `vite`, `typescript`, `@vitejs/plugin-react`, `@tanstack/react-query`, `react-router-dom` | npm | `19.2.8`, `19.2.8`, `8.2.2`, `7.0.2`, `6.1.0`, `5.102.5`, `7.18.2` | 项目批准栈/官方文档与 npm registry | OK | Approved. [VERIFIED: npm registry] |
| `tailwindcss`, `@tailwindcss/vite`, `@headlessui/react` | npm | `4.3.3`, `4.3.3`, `2.2.10` | 官方安装/组件文档与 npm registry | OK | Approved. [VERIFIED: npm registry] |
| `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `playwright` | npm | `16.3.2`, `7.0.1`, `14.6.6`, `1.62.1` | 官方测试文档与 npm registry | OK | Approved. [VERIFIED: npm registry] |
| `vitest` | npm | `4.1.11` | 官方 Vitest 安装文档与 npm registry | SUS (`vite` 近似名启发式误报) | Flagged — 实施计划必须含 `checkpoint:human-verify`，确认官方 vitest.dev 与 package name 后再安装。 [VERIFIED: npm registry + https://vitest.dev/guide/] |

**Packages removed due to slopcheck [SLOP] verdict:** none.  
**Packages flagged as suspicious [SUS]:** `vitest` — 这是 slopcheck 的字符串近似告警，不是官方来源的否定结论；仍按协议保留人工核验 checkpoint。 [VERIFIED: local slopcheck scan]

## Architecture Patterns

### System Architecture Diagram

```text
Mobile browser (localhost:5173)
  │ type Chinese standard name/alias
  ▼
React page ── useQuery(query) ──► GET /api/v1/dishes?query=宫保
  │                                  │
  │ selected {dishId, typicalServingGrams}  ▼
  │                              API Router → DishService → DishRepository
  │                                                  │           │
  │                                                  ▼           ▼
  │                                            Pydantic Schema  PostgreSQL
  │                                                          dishes/aliases/
  │                                                          recipes/nutrition/
  │                                                          data_versions
  │
  │ edit grams locally; no HTTP call
  ▼
click “计算热量”
  └── useMutation ─────────────► POST /api/v1/calculations
                                      │
                                      ▼
                              CalculationService
                              validates grams + approved record
                                      │
                                      ▼
                              deterministic kcal calculation
                                      │
                                      └────► `{dishId, grams, kcal}` response

Explicit developer commands:
`docker compose up -d db` → `alembic upgrade head` → `seed_catalog` → API/frontend start
Production preflight: `release-preflight` fails if served data is not production-approved.
```

FastAPI 应保留默认 `/docs` 和 `/openapi.json`；官方文档说明它会自动生成 OpenAPI JSON、Swagger UI 与 ReDoc。业务 API 路径应另用 `/api/v1`，不要把 `/docs` 误移到版本前缀下，才能同时满足 D-13。 [CITED: https://fastapi.tiangolo.com/tutorial/first-steps/]

### Recommended Project Structure

```text
.
├── compose.yaml                     # only PostgreSQL service and healthcheck
├── .gitignore
├── README.md                         # exact startup order + architecture/data-flow diagram
├── frontend/
│   ├── .env.example                  # VITE_API_BASE_URL=http://localhost:8000
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── api/                      # typed fetch wrappers only
│   │   ├── features/calculator/      # combobox, grams field, result card
│   │   ├── routes/                   # route composition
│   │   ├── test/                     # setup and test utilities
│   │   └── main.tsx
│   └── tests/e2e/                    # one Playwright thin-slice flow
└── backend/
    ├── .env.example
    ├── pyproject.toml
    ├── alembic.ini
    ├── alembic/versions/             # immutable reviewed schema revisions
    ├── app/
    │   ├── api/v1/                   # routers + HTTP exception mapping only
    │   ├── core/                      # settings, database session dependency
    │   ├── models/                    # SQLAlchemy mappings only
    │   ├── schemas/                   # Pydantic request/response/error contracts only
    │   ├── repositories/              # SQLAlchemy queries only
    │   ├── services/                  # calculator and release policy only
    │   ├── scripts/                   # explicit seed_catalog/release_preflight commands
    │   └── main.py
    ├── data/catalog/                  # versioned JSON/CSV source manifest, no raw images
    └── tests/
        ├── unit/
        ├── integration/               # real isolated PostgreSQL
        └── api/
```

### Pattern 1: Directional dependency boundary

**What:** `api → services → repositories → models`；`schemas` 仅作为 API 的输入输出 DTO；`core` 提供 settings/session；较内层绝不能 import API router。 [VERIFIED: project CONTEXT.md]

**When to use:** Phase 1 的每个 endpoint，包括简单搜索，均适用；“简单所以 router 直接 select”是未来无法测试、无法维护的垃圾债。 [VERIFIED: project CONTEXT.md]

**Example:**

```python
# Source: project CONTEXT.md D-14/D-15; FastAPI dependency pattern
@router.post("/calculations", response_model=CalculationResponse)
def calculate(
    payload: CalculationRequest,
    service: Annotated[CalculationService, Depends(get_calculation_service)],
) -> CalculationResponse:
    return service.calculate(payload)

# service uses a Repository protocol; it owns validation and formula.
```

FastAPI 会把 dependency 的参数与验证纳入 OpenAPI，因此在 router 注入 Service 不会牺牲契约可见性。 [CITED: https://fastapi.tiangolo.com/tutorial/dependencies/]

### Pattern 2: Immutable external IDs and versioned controlled records

**What:** 使用 UUID/ULID-like stable `dish_id`（字符串或 UUID）作为公共标识，不暴露自增 PK；`dish` 存身份，`dish_alias` 存可搜索别名，`standard_recipe` 存一份当前标准配方，`nutrition_record` 存 `kcal_per_100g` 与来源字段，`data_version` 存版本和 release status。 [VERIFIED: project CONTEXT.md]

**When to use:** 所有 API 返回 `dishId`；数据库内部仍可有 surrogate PK，但前端与未来模型结果都只依赖稳定 ID。 [VERIFIED: project CONTEXT.md]

**Required constraints:** `dish_id` 唯一；每个 alias 在 normalised form 上唯一；克数、`kcal_per_100g`、常见份量均 `> 0`；`release_status` 为受限枚举；`nutrition_record` 必须引用 `data_version`。PostgreSQL 的 `CHECK` 可表达单行正数约束，`UNIQUE`/FK 可表达别名和关系完整性。 [CITED: https://www.postgresql.org/docs/current/ddl-constraints.html]

### Pattern 3: Explicit schema migration plus idempotent seed

**What:** 初始 Alembic revision 创建 schema/constraints/indexes；`seed_catalog` 读取仓库内 manifest，按 stable ID upsert 数据，输出导入摘要，并在一个 transaction 中 rollback 任一无效记录。 [ASSUMED]

**When to use:** 开发者从空库复现 Phase 1；15 菜验结构后，将同一 manifest 扩到约 100 菜。绝不在 app startup 自动运行。 [VERIFIED: project CONTEXT.md]

**Migration workflow:**

```bash
cd backend
alembic upgrade head
python -m app.scripts.seed_catalog --source data/catalog/v1.json
python -m app.scripts.release_preflight --environment local
alembic check
```

Alembic autogenerate 只能生成候选 revision，必须手审；`alembic check` 能在 CI 检出“ORM 已变化但没新 migration”的情况。 [CITED: https://alembic.sqlalchemy.org/en/latest/autogenerate.html]

### Pattern 4: Data eligibility policy is executable

**What:** `release-preflight --environment production` 运行以下零容忍规则：

1. 任何目录中可查询/可计算的 nutrition record 不是 `production_approved` 即失败；
2. 任何该记录没有来源、license/commercial-use reference、或 derivation chain 即失败；
3. 种子 manifest 与 DB 查询都产生 machine-readable JSON 报告，并以非零 exit 退出；
4. release/deploy 命令在启动应用前调用该 preflight；本地 `APP_ENV=local` 可允许 `demo_only`，但 API response 必须保留其状态给未来 UI/运营。 [VERIFIED: project CONTEXT.md]

**Why both DB and source checks:** 只验仓库源文件会漏掉数据库残留；只验数据库会漏掉待导入的无资格数据。两者都验证才是 D-12 的可执行门禁。 [ASSUMED]

### Pattern 5: Thin REST contract and one calculation authority

**What:**

```text
GET  /api/v1/dishes?query=<1..50 chars>&limit=<1..20>
200  {"items":[{"dishId","name","matchedAlias","typicalServingGrams","dataStatus","sourceReference","licenseStatus","dataVersion"}]}

POST /api/v1/calculations
body {"dishId":"...","grams":180}
200  {"dishId":"...","dishName":"宫保鸡丁","grams":180,"kcal":342,"sourceReference":"...","licenseStatus":"demo_only","dataVersion":"v1"}
404  {"code":"DISH_NOT_FOUND","message":"..."}
422  FastAPI/Pydantic validation response or project-normalised error envelope
```

`grams` 必须是严格正数、上限由服务端冻结；`dishId` 必须存在并有可供本地环境使用的受控营养记录；请求体不接受也不读取“模型热量”“每 100g 热量”“来源”等客户提供字段。响应 schema 只能公开所需字段，不能直接序列化 ORM。FastAPI 的 `response_model` 会校验和过滤输出，是防止内部字段泄露的额外防线。 [CITED: https://fastapi.tiangolo.com/tutorial/response-model/]

### Anti-Patterns to Avoid

- **Router 里直接 `select()`/`session.commit()`：** 违反 D-14/D-15，破坏 Service fake-repository unit test；改为 API 只调用 Service。 [VERIFIED: project CONTEXT.md]
- **启动时 `Base.metadata.create_all()` / `alembic upgrade` / seed：** 违反 D-24；改为人和 CI 可观察、可失败的显式命令。 [VERIFIED: project CONTEXT.md]
- **用 float 算/存可审计热量：** 改用 `Decimal` 或数据库 `NUMERIC`，只在 API 边界按展示规则量化。 [ASSUMED]
- **前端拷贝目录或 kcal 公式：** 会制造单一事实来源漂移；前端只发送 stable ID 与 grams，结果由 API 返回。 [VERIFIED: AGENTS.md]
- **仅靠 enum 或 README 阻止 demo 数据发布：** enum 只限制值域，不能证明可服务数据都获批；必须跑 preflight。 [VERIFIED: project CONTEXT.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| 可访问搜索下拉 | 自制 keyboard/focus/ARIA autocomplete | `@headlessui/react` `Combobox` | 官方组件已处理 keyboard navigation 与 ARIA，应用只负责中文标准名/别名过滤。 [CITED: https://headlessui.com/react/combobox] |
| HTTP server/OpenAPI | 手写 WSGI、路由、JSON Schema 文档 | FastAPI + Pydantic schemas | FastAPI 基于 OpenAPI/JSON Schema 并提供 docs。 [CITED: https://fastapi.tiangolo.com/features/] |
| schema migration | `create_all`、手改数据库、启动时 DDL | Alembic revision + upgrade/check | 审阅的 migration history 可复现；autogenerate 必须人工修订。 [CITED: https://alembic.sqlalchemy.org/en/latest/autogenerate.html] |
| 数据库替身 | SQLite 假装 PostgreSQL | 独立 PostgreSQL test database | D-17 强制真实 PostgreSQL；测试必须覆盖真实 dialect/constraint 行为。 [VERIFIED: project CONTEXT.md] |
| server-state pending/cache | 手写 `useEffect` race/cache 状态机 | TanStack Query | 官方库解决 fetch/cache/synchronization，适用于搜索 query 与提交 mutation。 [CITED: https://tanstack.com/query/latest/docs/framework/react/overview] |
| API output exposure | 返回 ORM 的 `__dict__` | Pydantic response model | response model 会文档化、验证、转换与过滤输出。 [CITED: https://fastapi.tiangolo.com/tutorial/response-model/] |

**Key insight:** Phase 1 的“简单”只限业务流程，不能牺牲数据资格、迁移和契约边界。自己手搓这些基础设施不是学习，是把本可由标准工具覆盖的失败模式藏起来。 [ASSUMED]

## Common Pitfalls

### Pitfall 1: 把 15 道试验数据当作 100 道完成
**What goes wrong:** schema/test 只对少量 demo 数据工作，阶段结束时未达到约 100 个 stable `dishId`。  
**Why it happens:** 将 D-07 的先验证理解成阶段终态。  
**How to avoid:** seed manifest、导入报告与 integration test 断言阶段末 catalog count 约为 100，且 D-08 的 15 道均存在。 [VERIFIED: project CONTEXT.md]  
**Warning signs:** README 只描述“sample seed”；测试没有 catalogue count 或必需菜 ID 断言。 [ASSUMED]

### Pitfall 2: 许可字段存在但不可执行
**What goes wrong:** 有 `license_status` 字段，却没有 production preflight；`demo_only` 仍能通过公开运行配置查询和计算。  
**Why it happens:** 将列设计误当作 release control。  
**How to avoid:** 让 preflight 对 DB + manifest 做非零退出检查，并在生产启动/CI release job 调用；写 integration test 注入一条 demo 数据并断言 preflight 失败。 [VERIFIED: project CONTEXT.md]  
**Warning signs:** 任意 `SELECT` 都返回 demo 记录，或者 deploy 命令根本不运行 preflight。 [ASSUMED]

### Pitfall 3: migration 与种子互相污染
**What goes wrong:** 初始化数据藏在 schema revision，或 FastAPI 启动时自行 seed；不同环境得到不同目录。  
**Why it happens:** 想用“一键运行”掩盖开发流程。  
**How to avoid:** migration 只 DDL，seed 只 DML；使用 `alembic upgrade head` 后显式 seed，且在空库 integration test 完整重放。 [VERIFIED: project CONTEXT.md + https://alembic.sqlalchemy.org/en/latest/tutorial.html]  
**Warning signs:** `main.py` imports/executes migration 或 seed，或 revision 包含大量业务数据。 [ASSUMED]

### Pitfall 4: ORM Model 冒充公共 API schema
**What goes wrong:** 内部许可、审计、ID、关系字段被意外返回；数据库重构变成破坏 API。  
**Why it happens:** 看起来少写几个 class，但直接违反 D-15。  
**How to avoid:** 每个 endpoint 有独立 Pydantic request/response schema，并以 `response_model` 限制输出。 [VERIFIED: project CONTEXT.md + https://fastapi.tiangolo.com/tutorial/response-model/]  
**Warning signs:** Router return type 是 SQLAlchemy entity，或 `from_attributes` 被当作“可公开整个 entity”。 [ASSUMED]

### Pitfall 5: 搜索在每个键入字符都计算热量
**What goes wrong:** 违反 D-04，造成无意义网络请求和难以理解的加载状态。  
**Why it happens:** 将“搜索 API”与“计算 API”混为一个 onChange 副作用。  
**How to avoid:** 搜索 query 可 debounce；grams 只维护 local state；仅 button submit 调用 calculation mutation。 [VERIFIED: project CONTEXT.md]  
**Warning signs:** grams input 的 onChange 调 `POST /calculations`。 [ASSUMED]

### Pitfall 6: 用 SQLite 或共享开发库跑 integration test
**What goes wrong:** PostgreSQL 的 constraint、numeric、migration 或 text-search 行为未被覆盖，测试并发污染。  
**Why it happens:** 图省事，或没有 `TEST_DATABASE_URL`。  
**How to avoid:** 使用专用 PostgreSQL database/compose test service；每 test 或每 module 在外层 transaction + savepoint 内运行并 rollback。SQLAlchemy 官方给出 external transaction + `join_transaction_mode="create_savepoint"` 的测试 recipe。 [CITED: https://docs.sqlalchemy.org/en/20/orm/session_transaction.html]  
**Warning signs:** `sqlite://` 出现在 tests，或测试指向开发 `DATABASE_URL`。 [VERIFIED: project CONTEXT.md]

### Pitfall 7: CORS 用 `*`
**What goes wrong:** 放宽了本地浏览器来源边界并直接违反 D-26。  
**Why it happens:** 复制最短示例。  
**How to avoid:** 仅 `allow_origins=["http://localhost:5173"]`，并显式枚举本阶段实际 method/header；FastAPI 官方建议显式 allowed origins。 [VERIFIED: project CONTEXT.md + https://fastapi.tiangolo.com/tutorial/cors/]  
**Warning signs:** `allow_origins=["*"]` 或从前端环境变量无验证地接收任意 origin。 [ASSUMED]

## Code Examples

Verified/locked patterns; class and module names remain implementation discretion.

### SQLAlchemy 2 model base and session dependency

```python
# Source: https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html
#         https://docs.sqlalchemy.org/en/20/orm/session_basics.html
from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

class Base(DeclarativeBase):
    pass

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
```

`Engine`/`sessionmaker` 是 module-scope factory，而 Session 是 function/request scope；这是 SQLAlchemy 官方 session 使用模式。 [CITED: https://docs.sqlalchemy.org/en/20/orm/session_basics.html]

### Explicit calculation request/response contract

```python
# Source: FastAPI response model + project D-13 through D-18
from decimal import Decimal, ROUND_HALF_UP
from pydantic import BaseModel, Field

class CalculationRequest(BaseModel):
    dish_id: str = Field(min_length=1, max_length=64)
    grams: Decimal = Field(gt=0, le=Decimal("3000"), max_digits=7, decimal_places=1)

class CalculationResponse(BaseModel):
    dish_id: str
    dish_name: str
    grams: Decimal
    kcal: int
    source_reference: str
    license_status: str
    data_version: str

def kcal_for(grams: Decimal, kcal_per_100g: Decimal) -> int:
    return int((grams * kcal_per_100g / Decimal("100")).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    ))
```

上面只示范公式形状：正式实现必须把 `kcal_for` 放在 Service/纯 calculation module，且 unit test 固定 rounding；Repository 返回的受控 `kcal_per_100g` 是唯一输入来源。 [VERIFIED: AGENTS.md + project CONTEXT.md]

### Search combobox with client-only grams editing

```tsx
// Source: https://headlessui.com/react/combobox
const [query, setQuery] = useState('');
const [grams, setGrams] = useState('');
const dishes = useDishSearch(query); // GET only
const calculate = useCalculationMutation(); // POST only on submit

<Combobox value={selectedDish} onChange={setSelectedDish}>
  <ComboboxInput
    aria-label="搜索菜品"
    displayValue={(dish) => dish?.name ?? ''}
    onChange={(event) => setQuery(event.target.value)}
  />
  <ComboboxOptions>{/* standard name + matched alias */}</ComboboxOptions>
</Combobox>
<input value={grams} onChange={(event) => setGrams(event.target.value)} />
<button onClick={() => calculate.mutate({ dishId: selectedDish.id, grams })}>
  计算热量
</button>
```

`grams` 的 onChange 不得调用 mutation；选中 dish 时将 `typicalServingGrams` 复制进 local form state。 [VERIFIED: project CONTEXT.md]

### PostgreSQL Repository test isolation

```python
# Source: https://docs.sqlalchemy.org/en/20/orm/session_transaction.html
connection = engine.connect()
outer_transaction = connection.begin()
session = Session(bind=connection, join_transaction_mode="create_savepoint")
try:
    # repository tests may call session.commit(); outer transaction remains rollbackable
    yield session
finally:
    session.close()
    outer_transaction.rollback()
    connection.close()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| SQLAlchemy 1.x `declarative_base()` style | SQLAlchemy 2 typed `DeclarativeBase` + `Mapped` + `mapped_column` | SQLAlchemy 2.x | 使用 2.0 typed mapping，避免遗留 Query API 风格进入新代码。 [CITED: https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html] |
| 手工维护 API 文档 | FastAPI 由 Pydantic declarations 生成 OpenAPI、`/docs` 与 `/openapi.json` | FastAPI current docs | 将 OpenAPI JSON 纳入契约测试，不复制手写 schema。 [CITED: https://fastapi.tiangolo.com/tutorial/first-steps/] |
| Tailwind v3 的 PostCSS-centric Vite setup | Tailwind current Vite integration uses `@tailwindcss/vite` | Tailwind current docs | 直接采用官方 Vite plugin，避免从旧教程复制无关配置。 [CITED: https://tailwindcss.com/docs/installation/using-vite] |

**Deprecated/outdated:** 不要在此项目里采用 FastAPI startup `create_all()` 教程片段；它适合极简 SQLite 教程，但与已锁定的 Alembic/PostgreSQL/显式迁移流程冲突。 [VERIFIED: project CONTEXT.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | Phase 1 使用同步 SQLAlchemy 比 async 更合适 | Alternatives Considered | 低：可在实现前改成 async，但会改变 session/repository/test patterns。 |
| A2 | JSON/CSV manifest 独立 seed 比将目录数据放入 Alembic data migration 更合适 | Alternatives Considered / Pattern 3 | 中：需要 planner 明确 seed 数据格式与 idempotency 细节。 |
| A3 | 用 `Decimal`/`NUMERIC` 而非 float 保存、计算 kcal 更适合可审计数字 | Anti-Patterns | 低：取整规则若改，必须同步更新 calculation tests。 |
| A4 | DB + manifest 双重 preflight 是避免资格遗漏的最佳实现形态 | Pattern 4 | 中：release 系统细节尚未存在，必须把它写进 Phase 1 CI/命令。 |
| A5 | 搜索 query 可 debounce | Pitfall 5 | 低：延迟阈值和 debounce 时间不应在 Phase 1 锁定。 |

## Open Questions (RESOLVED)

1. **约 100 道菜的正式来源、商业授权文本与推导链何时可用？ — RESOLVED**
   - Decision: Phase 1 的约 100 道菜全部是有来源/授权状态/推导链字段的本地开发 `demo_only` 数据，不得声称商业授权完整，也不能通过 production preflight。商业授权关闭、字段级真实审核与公开发布判断属于 Phase 5 release gate。 [VERIFIED: STATE.md + CONTEXT.md D-11/D-12]
   - Verification evidence: `test_seed_catalog.py` 断言约 100 项、D-08 15 项、稳定 ID 和 `demo_only`；`test_release_policy.py`/`test_release_preflight.py` 证明 production 对 demo 数据非零失败。

2. **生产 preflight 接入哪个实际部署/CI 命令？ — RESOLVED**
   - Decision: Phase 1 不虚构云 CI 或部署。`python -m app.scripts.release_preflight --environment production` 是唯一可独立运行的 CI 接点；root/backend runbook 在本地与未来 CI 的 release candidate 步骤中调用它，后续平台只调用此命令而不重写 policy。 [VERIFIED: current repository has no CI/deploy pipeline]
   - Verification evidence: fake-repository unit matrix 和隔离 PostgreSQL integration suite 覆盖 JSON report 与 production non-zero exit；runbook replay command 必须执行 preflight。

3. **公开 API 是否应返回数据治理信息？ — RESOLVED**
   - Decision: 为严格满足 D-06，`GET /api/v1/dishes` 的每个 item 与 `POST /api/v1/calculations` 的 response 都返回最小的 `sourceReference`、`licenseStatus`、`dataVersion`，并保留 `dataStatus`。API schemas/Service/Repository/route/OpenAPI/API contract tests 必须覆盖这些字段。Phase 1 前端不使用字段请求参数，也不将它们映射到 UI DTO 或渲染；浏览器只显示菜名、克数和后端 kcal。 [VERIFIED: CONTEXT.md D-05/D-06]
   - Verification evidence: API/OpenAPI tests assert all four governance fields; frontend transport/component tests assert UI DTO 和 DOM 中没有 source/license/version 字段。

## Environment Availability

| Dependency | Required By | Available | Version / status | Fallback |
|---|---|---|---|---|
| Node.js | Vite/Vitest/Playwright | ✓ | `v22.23.2`; Vite 文档要求 `20.19+` 或 `22.12+`。 [VERIFIED: local command + https://vite.dev/guide/] | — |
| npm | frontend dependency install | ✓ | `10.9.8` | — |
| Python | FastAPI/SQLAlchemy/Alembic | △ — blocking | 当前仅确认 `3.9.6`；Psycopg 支持窗口为 Python `3.10–3.14`，且 3.9 支持止于 3.3 前。Phase 1 必须通过 `python3.11 --version` 的 3.11.x checkpoint 后，才可创建 `.venv` 或安装后端依赖。 [VERIFIED: local command + https://www.psycopg.org/psycopg3/docs/basic/install.html] | 用 pyenv、Homebrew `python@3.11` 或官方安装器安装/选择 Python 3.11；失败时修复 PATH 或重新安装，禁止回退到 3.9。 |
| pip | backend dependency install | ✓ | `21.2.4` | 与新的 Python 一起使用对应 pip。 |
| Docker CLI | Compose PostgreSQL | ✓ | Docker `29.4.0` | — |
| Docker Compose | Compose PostgreSQL | Not probed | Docker client 已在，但本轮未执行 `docker compose version`。 [VERIFIED: local command] | Wave 0 先运行 `docker compose version` 与 `docker compose up db`。 |
| PostgreSQL server / `psql` | 本地 DB 与 repository integration tests | ✗ (host) | `psql`/`pg_isready` 未发现；按锁定方案由 Docker Compose 提供。 [VERIFIED: local command + project CONTEXT.md] | Docker Compose `db` service；不得回退 SQLite。 |

**Missing dependencies with no fallback:** Python 3.10+ 是实施当前 Psycopg 文档线所需的 blocker；必须在 Wave 0 固定 Python 3.11+。 [CITED: https://www.psycopg.org/psycopg3/docs/basic/install.html]

**Missing dependencies with fallback:** 本机 `psql` 缺失不阻断，因为 Compose PostgreSQL 是批准的本地依赖；管理员可用 DBeaver/DataGrip/VS Code extension 查看 DB，但它们不是项目依赖。 [VERIFIED: project CONTEXT.md]

## Security Domain

OWASP ASVS 5.0.0 是当前稳定版；它用于验证 web 应用技术安全控制。Phase 1 不处理认证/上传，但仍要落实输入校验、最小暴露、CORS、机密配置、SQL 注入防护与发布数据资格。 [CITED: https://owasp.org/www-project-application-security-verification-standard/]

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | no | Phase 1 无账号/login；不要提前引入 auth。 [VERIFIED: PROJECT.md] |
| V3 Session Management | no | Phase 1 无 session/cookie；CORS `allow_credentials=False`。 [VERIFIED: PROJECT.md] |
| V4 Access Control | yes, limited | `release-preflight` 是 deployment/data eligibility control；未来运维数据 endpoint 必须独立授权。 [VERIFIED: project CONTEXT.md] |
| V5 Input Validation | yes | Pydantic request query/body bounds、schema response filtering、normalised search length limit。 [CITED: https://fastapi.tiangolo.com/tutorial/response-model/] |
| V6 Cryptography | no | Phase 1 不储存密码/原图；不手写 crypto。 [VERIFIED: AGENTS.md] |
| V7 Error Handling and Logging | yes | 结构化错误 code，日志不记录 `.env`、DB URL、原图/base64/模型响应。 [VERIFIED: AGENTS.md] |
| V13 API and Web Service | yes | `/api/v1`、OpenAPI contract test、只允许 `localhost:5173` 的 CORS。 [VERIFIED: project CONTEXT.md] |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---|---|---|
| SQL injection through search/ID | Tampering | SQLAlchemy bound parameters/ORM expressions；禁止拼接 SQL 字符串。 [ASSUMED] |
| 内部授权、来源或 DB 字段随 ORM response 外泄 | Information Disclosure | 独立 Pydantic response schema + `response_model` output filtering。 [CITED: https://fastapi.tiangolo.com/tutorial/response-model/] |
| 任意网站读取本地 API | Information Disclosure | FastAPI `CORSMiddleware` 明确仅允许 `http://localhost:5173`，绝不 `*`。 [CITED: https://fastapi.tiangolo.com/tutorial/cors/] |
| demo 数据公开发布 | Tampering / Repudiation | immutable seed manifest、DB release status、production preflight 非零退出和 integration test。 [VERIFIED: project CONTEXT.md] |
| `.env` 或数据库 URL 进入 Git/log | Information Disclosure | `.env.example` 只列键名/安全开发值；`.env` gitignore；Pydantic settings 验证值。 [VERIFIED: project CONTEXT.md + https://docs.pydantic.dev/latest/concepts/pydantic_settings/] |

## Sources

### Primary (HIGH confidence)

- [FastAPI response models](https://fastapi.tiangolo.com/tutorial/response-model/) — response filtering/validation and public schema boundary.
- [FastAPI dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/) — dependency declarations enter OpenAPI.
- [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/) — explicit origins versus wildcard.
- [FastAPI metadata and docs URLs](https://fastapi.tiangolo.com/tutorial/metadata/) — `/docs` and `/openapi.json` behavior.
- [SQLAlchemy 2 declarative mapping](https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html) and [session basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html) — typed mappings and session factory scope.
- [SQLAlchemy test transaction recipe](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html) — outer transaction + savepoint isolation.
- [Alembic autogenerate](https://alembic.sqlalchemy.org/en/latest/autogenerate.html) — manual review and `alembic check`.
- [PostgreSQL constraints](https://www.postgresql.org/docs/current/ddl-constraints.html) — check/unique/FK scope.
- [Psycopg installation](https://www.psycopg.org/psycopg3/docs/basic/install.html) — package name, binary option, Python support window.
- [Headless UI Combobox](https://headlessui.com/react/combobox) — accessible combobox and controlled filtering.
- [Vite guide](https://vite.dev/guide/) and [Tailwind Vite installation](https://tailwindcss.com/docs/installation/using-vite) — current setup and Node compatibility.
- [Vitest guide](https://vitest.dev/guide/), [Testing Library React](https://testing-library.com/docs/react-testing-library/intro/), [Playwright installation](https://playwright.dev/docs/intro/) — approved test stack.
- `AGENTS.md`, `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, and `01-CONTEXT.md` — locked project constraints and phase scope.

### Secondary (MEDIUM confidence)

- Local registry checks on 2026-08-26: `pip index versions` for Python packages; `npm view <package> version` and `scripts.postinstall` for npm packages.
- Local read-only slopcheck 0.6.1 scans: all listed packages OK except `vitest` marked SUS by its typo-similarity heuristic.

### Tertiary (LOW confidence)

- None; every [ASSUMED] implementation preference is listed in the Assumptions Log rather than presented as fact.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — locked project stack, official docs, registry checks and package scan.
- Architecture: HIGH — locked API/Service/Repository/Schema/Model boundaries plus official FastAPI/SQLAlchemy/Alembic patterns.
- Pitfalls: HIGH — Phase constraints directly identify the critical failure modes; migration/session/CORS details verified in primary docs.

**Research date:** 2026-08-26  
**Valid until:** 2026-09-02 for fast-moving package versions; re-run registry and package audit immediately before dependency installation.
