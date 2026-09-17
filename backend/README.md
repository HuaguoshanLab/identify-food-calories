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
uv run python -m app.core.run
```

运行后可访问 `http://127.0.0.1:8000/api/v1/health`。用户 H5 由 `frontend` 的 5178 端口代理公开 `/api/v1`；独立后台由 `admin-frontend` 的 5179 端口代理公开 `/api/v1/admin/*` 以及登录必要的公开认证路径。不要将两个 SPA 的端口、开发代理或管理员 access token 当作生产授权边界。

### 运行日志与查询

后端使用 Python 标准日志库，统一输出到标准输出；本地在启动终端查询，不自动保存文件。`.env` 可设置 `LOG_LEVEL=INFO`（可选 DEBUG/WARNING/ERROR/CRITICAL）和 `LOG_FORMAT=text`（可选 json）。第三方默认 WARNING；非结构化消息原文不会输出。需要开发自动重载时使用 `uv run python -m app.core.run --reload`，不要绕过该入口启用原始 Uvicorn 访问日志。

每次 HTTP 请求返回服务端生成的 `X-Request-ID`；已有错误响应的 `error.request_id` 与其一致。浏览器网络面板查看响应头，在终端按编号搜索 `http_complete`，再查看相同编号的 Agent、工具和模型事件。`execution_id` 仅关联本次 Agent 执行，恢复追问会生成新编号，不保证跨请求或跨重启关联。SSE 耗时包含整个连接持续时间。

常用事件：`http_failed`、`agent_start/complete/failed`、`tool_start/complete/failed`、`planning_search`、`planning_validation`、`deepseek_call_complete`、`qwen_vision_complete`。模型指标中的 cost 由 Provider 已有价格快照计算；DeepSeek 为 USD、Qwen 为 CNY。日志不记录饮食和身体资料、用户身份、请求/响应正文、查询参数、密钥或完整模型思维链。异常只保留类型与不含源代码/局部变量的堆栈位置。

当前根 Docker Compose 没有后端服务，不能用 `docker compose logs backend` 查本项目应用日志。将来容器化时由 Docker 收集标准输出，建议配置 `max-size: "10m"`、`max-file: "3"`；跨重启留存与集中搜索需要运行环境另行提供。管理员审计仍在 PostgreSQL，不能用尽力输出的运行日志代替。输出失败不会中断业务，但日志可能丢失。

验证：`uv run pytest tests/unit/test_operational_logging.py tests/planning/test_search_diagnostics.py -q`。回滚恢复日志基础设施、编号处理和匹配的启动入口，无数据库迁移；管理员审计不变。

### 餐单筛选预算

无需因菜谱库增长修改总数上限。服务按餐次和当前目录资格分批读取，只保留少量候选；管理员候选和初始受控菜谱使用同一套预算。在未提交的 `backend/.env` 可覆盖以下默认值，修改后重启后端：

```dotenv
PLANNING_BATCH_SIZE=64
PLANNING_SCAN_PER_SLOT=2048
PLANNING_OPTIONS_PER_SLOT=12
PLANNING_MAX_COMBINATIONS=1728
PLANNING_SCAN_SECONDS_PER_SLOT=3
PLANNING_COMBINATION_SECONDS=2
```

每餐最多扫描 2,048 条或用时 3 秒，每页最多 64 条；保留最多 12 个选项，其中默认预留最多 4 项给不同食物引用、食材组合或做法。组合阶段最多尝试 1,728 次或用时 2 秒，先到哪个限制就停止，使用已找到的最佳组合并继续营养校验。扫描预算按餐次独立分配，餐库超过预算不会直接报错；本次未找到完整组合时返回可重试结果，不放宽忌口和健康边界。

时间限制在查询、计算之间检查，不能中断正在执行的同步数据库查询，因此不是严格的请求总耗时保证。提高预算会增加查询量和延迟；有限搜索可能错过扫描范围外的合适菜谱，也不保证全库最优。配置在启动时校验，零、负值和超出安全配置范围的数值会被拒绝。只回滚代码及上述配置即可撤销本次算法调整，无需数据库迁移。

筛选诊断默认输出到后端标准日志：搜索 `planning_search` 查看各餐扫描量、淘汰数量、耗时和停止原因；搜索 `planning_validation` 查看最终校验规则及目标调整状态。日志只记录版本、枚举原因和数值计数，不包含用户身份、偏好原文、菜名或身体资料。候选失败不再原样重试三次，允许的目标范围调整只复用餐单校验一次。无需数据库迁移，回滚时同时恢复 planning 和 Agent 工具/图代码。

### 三维菜谱分类（迁移 0031）

在 `backend/` 执行 `uv run alembic upgrade head`，再重启后端并更新后台。0030 增加分类对象，0031 删除废弃的 `managed_recipe_candidates.meal_role`；已有三维分类保持不变，仅尚无分类且旧角色明确的记录在删列前转换为组合组成项。旧按钮、列表列、写接口及候选 DTO 字段已删除。

新 CSV 为原七列加“配餐用途、餐内角色、食材标签、分类依据”，共十一列；填写分类时用途、角色、依据必填，食材标签以 `|` 分隔。仍接受不带分类的七列文件，导入后不参选，需补齐分类。旧八列模板不再接受。导出包含三维分类及依据；导入始终新增候选，不覆盖现有记录，启用状态仍需人工确认。

历史餐单中每个组成项的 `meal_role` 是不可变快照，继续保留；历史迁移与旧审计也保留。0031 降级可恢复兼容列，但只能从新分类投影，无法精确恢复删除前的旧值；需要精确恢复时应使用删列前备份。不要在新旧实例同时运行时切换 schema。

### 午晚餐组合预算

```dotenv
PLANNING_BUNDLE_ENABLED=true
PLANNING_BUNDLE_OPTIONS_PER_ROLE=4
PLANNING_BUNDLE_MAX_COMBINATIONS=64
PLANNING_BUNDLE_SECONDS=0.5
PLANNING_BUNDLE_STAPLE_WEIGHT=45
PLANNING_BUNDLE_PROTEIN_WEIGHT=35
PLANNING_BUNDLE_VEGETABLE_WEIGHT=20
```

每个午餐、晚餐角色保留最多 4 种不同目录食物（可配 1–8），随后最多尝试 64 种餐内组合（1–512）或 0.5 秒（大于 0、不超过 5）。角色权重按总和归一化，用于初筛及各项份量的热量分配，不代表营养推荐比例；管理员原始数据不变。组合再与单独候选共享每餐 12 项和全天 1,728 次的原预算；营养校验、目标范围、偏好和近期重复相当时优先组合餐。有限搜索不保证找到所有可行搭配。

每项都检查目录资格与已知忌口；要求清淡时，每个组成菜品都须有清淡标签。更换午餐或晚餐替换整餐，暂不支持只替换其中一道菜；指定菜名替换仍从单独候选中选择。快照保存各项份量、营养和当时的来源修订，前端只汇总一次。后续停用、改分类不会改写历史。

设置 `PLANNING_BUNDLE_ENABLED=false` 并重启可停止新组合，仍可读取已保存明细；本轮无新增迁移，但必须先有 0029。不要直接回退到不认识组合快照的旧代码。搜索日志新增每餐 `components`、`bundle_attempts`、`bundles`、`adapted_components`、`adapted_bundles` 和 `bundle_stop`，不记录菜名或偏好原文。

### 餐次分配与候选多样性

以下是候选筛选策略，不是强制的每餐热量处方；餐次权重用于选菜和计算可调整份量，最终仍校验全天营养。在未提交的 `backend/.env` 配置，重启后生效：

```dotenv
PLANNING_BREAKFAST_WEIGHT=25
PLANNING_LUNCH_WEIGHT=40
PLANNING_DINNER_WEIGHT=35
PLANNING_DIVERSITY_SLOTS=4
PLANNING_DIVERSITY_WEIGHT=0.05
PLANNING_FLAVOUR_DIVERSITY_WEIGHT=0.25
```

- 三个餐次权重必须大于 0、最多 1000；按总和归一化，默认等价于 25% / 40% / 35%。单餐替换先扣除固定餐次和加餐，再把剩余营养目标按待选餐次权重分配；剩余目标最低为零。
- `DIVERSITY_SLOTS` 范围 0–64，实际最多占每餐候选数减一，始终保留至少一个营养优先候选。默认 12 个名额中先留 8 个营养优先项，再从不同搭配代表和剩余候选中补足 4 个。没有不同搭配时可用相似菜补足，不增加最终候选数或组合上限。
- 流式缓冲每餐最多保留两组各 K 个候选：营养优先项和不同搭配代表，默认合计最多 24 个。最终进入组合搜索的仍最多 12 个。
- `DIVERSITY_WEIGHT` 范围 0–1，控制组合排序中相似食物引用/已知食材、做法和口味的惩罚强度；校验等级、全天目标范围、口味与近期重复仍先比较。随后综合全天中点偏差、餐次分配偏差与相似程度，不强求每餐精确落在比例上。
- `FLAVOUR_DIVERSITY_WEIGHT` 范围 0–1，默认 0.25，控制口味在相似度中的权重；组合阶段再乘以 `DIVERSITY_WEIGHT`。口味同时参与候选分组和多样性名额筛选。设为 `0` 可单独关闭这次新增的口味分组、口味预留排序与口味评分，恢复只看食材和做法的多样性。
- 只比较目录已有口味标签，先规范化空白、大小写和全半角，再按完全匹配识别。用户明确喜欢的标签不计入口味重复惩罚，多样性预留名额优先保留匹配这些口味的选项。例如喜欢“清淡”时三餐清淡仍可接受，同时可在其他已有标签之间变化。缺少或仅含空白的标签不能获得“新口味”优势；没有替代候选时仍可重复，不新增拒绝条件。换餐可以使用已保存餐卡的口味标签，不修改固定餐次。
- 初始食谱使用已知食材 ID；管理员成品菜使用其关联营养条目的 ID，缺少配料结构时只使用已有引用和做法信息，不猜主食或蛋白质类别。食材证据只用于本次筛选，不进入公开餐单卡片或日志。

恢复等权初筛：三个权重均设为 `1`。关闭两处多样性偏好：`PLANNING_DIVERSITY_SLOTS=0` 且 `PLANNING_DIVERSITY_WEIGHT=0`。算法仍是有限搜索，改变名额分配可能错过被初筛淘汰的可行组合；多样性不能绕过营养或忌口校验。无需数据库迁移。

### 份量适配与目标偏差

`planning-selection.v10` 对单独候选保留原份量，按剩余热量和餐次权重，为每条可用菜谱最多增加一个份量选项。所有选项仍共用每餐 12 项、组合 1,728 次的预算。同一菜谱的不同份量不能出现在一天的两个餐次。

```dotenv
PLANNING_PORTION_ADJUSTMENT_ENABLED=true
PLANNING_PORTION_MIN_MULTIPLIER=0.75
PLANNING_PORTION_MAX_MULTIPLIER=1.25
PLANNING_MAX_TARGET_DEVIATION=0.10
```

- 份量默认限定在各菜谱原克数的 75%～125%，取区间内整数克且不超过 2,000g。上下倍率配置分别限定在 0.5～1、1～1.5。这是软件搜索范围，不是医学建议；同时应用于单独候选和组合餐各项，未提供逐菜谱调整范围的后台表单。
- 管理员成品菜按新克数调用目录计算；受控食谱按同一倍率调整各食材计算克数再求和。每条菜谱最多计算两种份量，扫描条数不变，营养查询量可能增加一倍。原目录和固定餐次不改写；加餐先从剩余目标扣除。调整后不继续展示原来的包子个数、碗数等份量描述。
- `planning-validation.v2` 对能量、蛋白质、脂肪和碳水分别检查。低于下限时以原下限为分母，高于上限时以原上限为分母；任一项超出 10% 都不能自动放宽。阈值可设为 0～0.25，设为 `0` 即禁用范围放宽。忌口、最低能量和宏量比例仍不可放宽。
- 前端保留原目标，显示四项实际总量和距最近边界的差值；允许偏差内的结果仍显示未达原目标。旧计划不会重算，但也会显示原目标差距。

组合餐对每种食物组合交错尝试原份量和一套逐项适配份量，共享餐内 64 次及时间预算。仅对每类保留的 K 项按角色热量重算并缓存，每餐最多增加 3K 次营养计算（默认 12 次），不枚举各项新旧份量的所有混合。计算失败保留原组合；预算可能使部分食物组合未被遍历。同总克数但各项克数不同的选项独立比较，换餐仍排除原食物组合的全部份量。

关闭份量适配：`PLANNING_PORTION_ADJUSTMENT_ENABLED=false`，重启后生效；偏差上限仍保留。无需迁移数据库。份量适配是有限搜索，不保证找到所有可行组合；目录不足时允许明确失败，不通过无上限放宽制造成功。

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

#### Mem0 云端长期记忆

在未提交的 `backend/.env` 设置 `APP_ENV=local`、`MEMORY_PROVIDER_MODE=mem0`、`MEM0_API_KEY` 和 `MEM0_ENDPOINT=https://api.mem0.ai`，然后重启后端。使用锁定的 `mem0ai` 依赖，无需额外安装 OpenMemory 或自建向量库。`APP_ENV=test` 始终选择 Fake。

新增偏好先保存本地账本并唤醒后台同步；Mem0 仅接收白名单偏好和隔离用户标识。现有 Fake 编号不能直接交给 Mem0 编辑。获得该用户的云端迁移授权后，在 `backend/` 执行（替换用户 UUID）：

```bash
uv run python scripts/migrate_fake_memories.py --user-id <用户UUID>
uv run python scripts/migrate_fake_memories.py --user-id <用户UUID> --apply
```

第一条仅预览，第二条只给该用户的有效 Fake 副本建立迁移待办；重复执行不会重置已迁移或正在同步的记录。保留本地记录编号、正文、来源及创建时间。脚本限定本机 `food_agent_dev`，后端必须运行以处理待办；后台默认轮询间隔为 300 秒，新增记忆和删除操作会主动唤醒。迁移不修改数据库结构；失败保留本地正文和待办，不得用清库或盲目重建处理未知云端结果。

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

### 旧菜谱三维分类整理

迁移 `0030` 增加 `managed_recipe_candidates.classification`，执行常规 `alembic upgrade head` 后可在后台勾选记录并“补齐三维分类”。保存包含用途、角色、已知食材标签、依据和 `recipe-classification.v1` 版本；默认不覆盖已有分类；选择复核待确认时只补齐具有新依据的未知角色。未识别信息明确待确认。名称线索不等于完整配料证据。新分类已直接驱动生成（`planning-selection.v11`），废弃的候选 `meal_role` 已通过 0031 删除；营养计算及旧历史不变。

公开接口为 `POST /api/v1/admin/recipe-candidates/classification-preview` 和 `classification-backfill`，均检查当前管理员角色；写入要求预览修订、原因、确认及幂等键，最多 1000 条。CSV 导出包含三个维度和分类依据。回填前后快照用于追溯，审计保留逐条前后值。不要通过降级迁移删除已补齐分类；停止使用回填入口即可停止新增修改，精确回退应另走带审计及版本检查的修正操作。


三维分类编辑与配餐接入：`POST /api/v1/admin/recipe-candidates/classification-review` 接收版本、分类依据、修改原因和幂等键，执行当前 RBAC、整批版本检查和逐项审计。后台每行“编辑分类”可修改三个维度。`whole_meal`/`both` 可整餐参选；`component`/`both` 中的主食、蛋白质菜、蔬菜可参与午晚餐组合；缺少分类或角色/用途待确认的不参选，不回退旧角色。汤羹、饮品、水果等组成项尚无组合模板。食材标签只补充已知类别忌口匹配，不代表完整过敏原检查。

本轮没有新增切换开关。修正分类通过同一编辑接口完成并留审计；代码异常可回退本轮代码，保留 0030 字段与已保存分类，避免删数据。新 CSV 可直接填写分类；七列无分类文件导入后需补齐或编辑才能参选。
