# Phase 5: 饮食规划子图 - Research

**Researched:** 2026-09-01
**Domain:** 可审计的成人一日三餐规划、LangGraph Human-in-the-loop 与 H5 资料管理
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

**Source:** [CITED: .planning/phases/05-diet-planning-subgraph/05-CONTEXT.md]

### Locked Decisions

### 身体资料、目标与个人资料

- **D-01:** 首次创建计划必须填写身高、体重、年龄、性别、活动水平、目标、目标速度、忌口和口味偏好；不得依靠模型猜测缺失身体资料。
- **D-02:** 活动水平固定为五档：久坐、轻度、中度、高度、非常高；每档提供用户可理解的活动示例。
- **D-03:** 目标速度只能选择保守预设档位。超出安全范围的速度直接拒绝，并提示用户咨询专业人士。
- **D-04:** 已保存的身体资料、目标和长期偏好可自动预填，但生成前必须完整展示并允许编辑。用户对本次身体资料或目标改动是否同步到个人资料有明确控制；计划页不能静默改写资料。明确的餐单反馈写入长期偏好遵循 D-11。
- **D-05:** 在“我的 → 个人资料”集中查看、编辑、删除身体资料和目标；删除后后续规划不再读取这些资料。忌口和口味偏好继续在既有“记忆”页管理，避免两个编辑入口互相覆盖。

### 餐单与生成状态

- **D-06:** 默认结果按早餐、午餐、晚餐三张卡片展示；每餐列出标准菜名、建议克数或受控份量及该餐营养小计，顶部展示全天目标与计划总览。
- **D-07:** 热量和三大营养素均以“目标区间 + 计划值 + 偏低/适中/偏高状态”呈现，不能把单一精确值伪装为医学精度。
- **D-08:** 每道菜显示简短做法或口味标签，以及命中的偏好/忌口约束；不扩张为复杂配方、烹饪步骤或购物清单能力。
- **D-09:** 前端仅展示读取资料与偏好、计算目标、组合餐单、校验约束、完成或需要调整等稳定业务阶段；严禁暴露逐 token、模型推理、工具原文或内部重排细节。

### 反馈恢复与约束冲突

- **D-10:** 用户说“换清淡”“不吃某菜”等反馈时，默认只替换直接受影响菜品；其余餐次和仍有效的已确认约束保持不变。
- **D-11:** 这类明确自然语言反馈自动写入长期偏好，并在当前及后续计划中使用；写入必须沿用 Phase 4 的白名单、来源审计、用户隔离和删除语义，不能把模型推测自动记忆化。
- **D-12:** 替换完成后直接展示更新后的三餐卡片，明确标记替换内容、满足新约束的依据和全天营养是否仍在目标区间；用户无需额外确认即可继续调整。
- **D-13:** 若没有严格合格的受控替代项，系统可自动放宽每日热量或宏量目标后继续生成，但必须显著说明偏离的目标、幅度和原因。忌口、用户明确排除项及高风险安全规则不得被自动放宽。
- **D-14:** 同一规划线程最多自动重排 3 次；达到上限后停止并给出可解释结果，允许用户新建计划或修改资料/目标，禁止无限循环。

### 健康与数据安全

- **D-15:** 涉及疾病诊断或治疗、用药剂量、孕期或哺乳期、未成年人、进食障碍、自伤，或极端减重/增重目标的请求，必须拒绝生成个性化餐单。
- **D-16:** 拒绝后页面说明无法提供该类个性化建议，建议联系医生或注册营养师；仅可给出不涉及疾病或体重操控的通用饮食安全原则。
- **D-17:** “普通饮食参考，不替代医疗建议”在首次进入计划页时展示，并在每份计划结果底部持续保留；一次性弹窗不能替代持续提示。
- **D-18:** 身体资料和目标按数据最小化原则持久化，仅保存生成和后续调整确实需要的数据；个人资料页必须支持用户查看、编辑和删除，删除后不得被后续检索或规划读取。

### the agent's Discretion

- 依据当前官方资料和安全评估，确定保守目标速度预设、各活动档示例、身体资料字段的运行时校验范围，以及确定性能量/宏量公式和版本标识。
- 确定受控菜谱的最小数据模型、检索和组合策略、重复度计算、目标偏离阈值及排序，但所有最终营养数字和校验结论必须来自确定性服务。
- 确定 LangGraph State、子图节点、interrupt/resume payload、SSE/OpenAPI 事件、幂等键、三次重排的精确预算和安全失败码；必须保留既有线程所有权、成本、时长和工具调用上限。
- 确定“个人资料”页面的具体路由、控件、无资料/删除确认文案和可访问性细节；必须复用现有 H5 壳和公开 API 边界。

### Deferred Ideas (OUT OF SCOPE)

- 完整配方、烹饪步骤和购物清单 — 独立能力，不属于 Phase 5。
- 摄入趋势、周复盘和图表看板 — Phase 6。
- 管理员受控菜谱/营养目录维护界面 — Phase 6。
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|---|---|---|
| PLN-01 | 用户可提交身高、体重、活动水平、目标、忌口和口味偏好。 | `planning` 领域资料 API、只读记忆预填与计划前完整复核。 [CITED: .planning/REQUIREMENTS.md] |
| PLN-02 | 确定性工具计算每日热量与宏量营养目标，模型不自行编造公式结果。 | 版本化目标计算 Service 与窄 Tool Port；模型只选择受控候选。 [CITED: AGENTS.md] |
| PLN-03 | 规划子图检索受控菜谱，生成一日三餐候选。 | 版本化受控菜谱/食材快照、确定性检索与组合。 [CITED: .planning/REQUIREMENTS.md] |
| PLN-04 | 校验工具检查总热量、宏量营养比例、忌口与重复度，不合格时有界重排。 | `validate_plan` 返回闭合集合动作；状态内 `replan_count <= 3`。 [CITED: .planning/phases/05-diet-planning-subgraph/05-CONTEXT.md] |
| PLN-05 | 用户可以通过自然语言要求替换、变清淡或排除食物，图在保留约束后重新规划。 | 同一线程 checkpoint 恢复、显式偏好捕获、仅替换受影响菜品。 [CITED: .planning/phases/05-diet-planning-subgraph/05-CONTEXT.md] |
| PLN-06 | 所有建议明确标注为普通饮食参考，不提供疾病治疗或医疗诊断。 | 入口/结果持续提示与高风险请求确定性拒绝。 [CITED: .planning/REQUIREMENTS.md] |
</phase_requirements>

## Project Constraints (from AGENTS.md)

- 后端保持 Python 3.12+、FastAPI、Pydantic v2、SQLAlchemy 2 同步 Session 与 PostgreSQL；前端保持独立 React + TypeScript + Vite SPA。 [CITED: AGENTS.md; backend/AGENTS.md; frontend/AGENTS.md]
- 不把项目改成 Next.js、微服务、Kafka 或 Kubernetes；用户 H5 与未来独立后台不能混合。 [CITED: AGENTS.md]
- 必须保持 `API → Application/Service → Repository → Model`；API 只翻译 HTTP，Repository 不提交事务或决定业务规则。 [CITED: AGENTS.md; backend/AGENTS.md; backend/ARCHITECTURE.md]
- Graph 只能经 `agent/tools.py` 的窄端口调用领域 Service；Graph、Schema、ORM 和 Provider DTO 必须分离。 [CITED: AGENTS.md; backend/AGENTS.md; backend/ARCHITECTURE.md]
- 营养、目标、计算和校验必须由确定性工具完成；模型绝不是数值真相来源。 [CITED: AGENTS.md]
- PostgreSQL 是权威业务存储，Checkpoint 只保存短期图状态，Mem0 只保存白名单长期偏好。 [CITED: AGENTS.md]
- 每张图均须有最大循环、工具调用、超时、成本和终止条件；不得记录密钥、原图/base64、完整模型思维链或无必要敏感数据。 [CITED: AGENTS.md]
- 受保护资源必须按 `user_id` 过滤；UUID 不是授权能力；配置 fail closed，测试不得回落开发库或 SQLite。 [CITED: backend/AGENTS.md; backend/ARCHITECTURE.md]
- 所有 schema 变更走 Alembic migration，所有 API/工具/State/模型输出做运行时校验，模型/提示词/工具/目录/计算规则均须有版本标识。 [CITED: AGENTS.md]
- 密钥仅来自未提交环境变量；普通饮食建议不可伪装为医疗诊断或治疗。 [CITED: AGENTS.md]
- 新目录必须同次增加并维护含职责、允许依赖和文件索引的 README。 [CITED: AGENTS.md; backend/AGENTS.md; frontend/AGENTS.md]
- 后端 Service 用 fake repository 单测，Repository 用真实 PostgreSQL 集成测试，Agent 图用 Fake Provider 测路由、interrupt/resume 和循环终止；本阶段还必须写中文 `docs/learning/` 教学文档。 [CITED: AGENTS.md; backend/AGENTS.md]
- 前端 API 只通过公开 `/api/v1`，TanStack Query 管服务端状态，React Hook Form + Zod 管表单；页面不直接 `fetch` 或定义后端 DTO。 [CITED: frontend/AGENTS.md; frontend/ARCHITECTURE.md]
- 任何用户可见页面、表单、路由与跨栈交互必须补组件测试、Playwright，并用 Codex 内置浏览器从真实页面和公开 API 验收；浏览器不可用时必须如实记录。 [CITED: AGENTS.md; frontend/AGENTS.md]
- H5 必须遵守四 Tab、`100dvh`、唯一主滚动区、语义 token、44px 触控目标、可见 label/focus 与响应式验收矩阵；不得引入第二 UI 库。 [CITED: docs/ui/h5-foundation.md]

## Summary

Phase 5 应新增一个受控的 `planning` 领域：它拥有最小化的身体资料/目标、版本化食谱与确定性目标和餐单校验；`agent` 只负责线程、运行账本、Checkpoint、稳定事件和向该领域的窄工具调用。现有 `MealAnalysisGraph`、`AgentService` 与 `/api/v1/agent` 已经持有线程所有权、幂等命令账本、PostgreSQL Checkpointer 和 SSE 回放，规划功能必须复用这条路径而不是建设平行的“计划执行器”。 [CITED: backend/app/agent/graph.py; backend/app/agent/service.py; backend/app/agent/api.py; backend/app/main.py]

模型的职责应严格收缩为：把用户反馈归类为显式约束、从确定性检索结果中选择可替换候选，或请求缺失资料；所有 BMR/TDEE、宏量目标、候选汇总、忌口、重复度和目标偏差结论都由版本化 Service 返回。受控菜谱必须引用已有合格食材目录及其版本，并由重新计算而非菜谱预填数字决定最终营养值。 [CITED: AGENTS.md; backend/app/nutrition/schemas.py; backend/app/nutrition/service.py]

个人资料与长期偏好不能混存：资料 CRUD 只持久化 D-18 所需的身体/目标字段；忌口、口味偏好继续只由 `memory` 的白名单账本管理。计划页应完整展示当前资料与偏好，让用户明确确认“无忌口/无特别口味”或先跳转记忆页维护，避免在资料页复制偏好编辑器。 [CITED: .planning/phases/05-diet-planning-subgraph/05-CONTEXT.md; backend/app/memory/service.py; frontend/src/features/memory/README.md]

**Primary recommendation:** 先建立 `app/planning` 的确定性资料/目标/菜谱/校验边界和 Alembic 数据模型，再将 `DietPlanningGraph` 通过扩展后的 `agent/tools.py` 接到现有线程生命周期，最后交付 `features/plans/` 与“我的 → 个人资料”。 [ASSUMED]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| 资料与目标 CRUD | API / Backend | Database / Storage | 请求必须由后端认证并以 `user_id` 过滤；资料是权威业务数据。 [CITED: backend/ARCHITECTURE.md; AGENTS.md] |
| TDEE、宏量与餐单校验 | API / Backend | Database / Storage | 数值真相来自确定性 Service 和版本化目录，不能在浏览器或模型端计算。 [CITED: AGENTS.md; backend/app/nutrition/service.py] |
| 菜谱候选检索 | API / Backend | Database / Storage | 受控食材/菜谱版本与资格条件需要服务器端强制。 [ASSUMED] |
| 规划编排、重排与暂停恢复 | API / Backend | Database / Storage | 子图经服务器工具端口运行，Checkpoint 按 `thread_id` 保存短期状态。 [CITED: backend/app/agent/service.py; https://docs.langchain.com/oss/python/langgraph/persistence] |
| 长期偏好读取/显式反馈写入 | API / Backend | Database / Storage | Memory Service 已强制白名单、来源、用户隔离和删除语义。 [CITED: backend/app/memory/service.py; backend/app/retrieval/service.py] |
| 资料表单、三餐卡片和稳定进度 | Browser / Client | API / Backend | H5 仅调用公开 API、渲染已验证 DTO 和稳定业务事件。 [CITED: frontend/AGENTS.md; docs/ui/h5-foundation.md] |

## Standard Stack

### Core

| Library / project module | Version | Purpose | Why Standard |
|---|---:|---|---|
| Python + FastAPI + Pydantic | Python `>=3.12`, FastAPI `0.137.0` | 资料/计划 API、DTO 校验与错误映射 | 项目已锁定该后端栈；Pydantic 边界契约符合现有架构。 [CITED: backend/pyproject.toml; AGENTS.md] |
| LangGraph + PostgreSQL Checkpointer | `1.2.11` + `3.1.2` | 有界图、同线程恢复和持久检查点 | 现有运行时已打开 `AsyncPostgresSaver`；官方文档确认持久 checkpointer + `thread_id` 是 HITL 恢复前提。 [CITED: backend/pyproject.toml; backend/app/main.py; https://docs.langchain.com/oss/python/langgraph/interrupts] |
| SQLAlchemy 2 + Alembic + PostgreSQL | `2.0.52` + `1.16.5` | 资料、受控菜谱及其版本迁移 | 已锁定为权威数据与 schema 演进路径。 [CITED: backend/pyproject.toml; AGENTS.md] |
| React + TanStack Query + RHF + Zod | React `19.2.8`; Query `5.102.6`; RHF `7.86.0`; Zod `4.4.3` | H5 服务端状态、资料表单与 API 校验 | 已锁定；避免计划页散落 `fetch` 与手写校验。 [CITED: frontend/package.json; frontend/AGENTS.md] |

### Supporting

| Library / project module | Version | Purpose | When to Use |
|---|---:|---|---|
| `app.nutrition` | `nutrition-tools-v1` | 受控食材、克数换算和营养重算 | 每个食谱 ingredient 和整日汇总必须走它或同等确定性 planning service。 [CITED: backend/app/nutrition/schemas.py; backend/app/nutrition/service.py] |
| `app.memory` + `app.retrieval` | current project module | 白名单偏好、来源审计与偏好优先上下文 | 读取资料预填、解析明确的“换清淡/不吃某菜”反馈时使用。 [CITED: backend/app/memory/service.py; backend/app/retrieval/service.py] |
| 既有 Agent SSE hook | `eventsource-parser 3.1.0` | snapshot-first、Last-Event-ID 去重/gap 修复 | 计划 API 复用同一线程事件协议；不要手写第二个 SSE parser。 [CITED: frontend/package.json; frontend/src/features/agent/stream/README.md] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|---|---|---|
| PostgreSQL 受控菜谱与版本 | 外部食谱/API 实时搜索 | 外部结果不能保证受控食材、许可、版本、忌口或可复算性；本阶段不采用。 [CITED: AGENTS.md; .planning/phases/05-diet-planning-subgraph/05-CONTEXT.md] |
| 确定性组合/校验 | 让模型直接生成完整菜谱与营养数字 | 模型生成不能成为数值真相，且无法可靠证明忌口、重复度和目标偏差。 [CITED: AGENTS.md] |
| 一个通用 Agent 线程 API | 新建计划专用执行通道 | 新通道会绕开既有所有权、租约、幂等、Checkpoint 和事件账本；本阶段不采用。 [CITED: backend/app/agent/service.py; backend/app/agent/api.py] |

**Installation:** 不新增第三方包；Phase 5 使用已锁定依赖和项目模块。 [CITED: AGENTS.md; backend/pyproject.toml; frontend/package.json]

**Package legitimacy:** 不适用；研究没有推荐安装外部包，因此不产生 Package Legitimacy Audit。 [CITED: AGENTS.md]

## Architecture Patterns

### System Architecture Diagram

```text
H5 /app/plans + 我的→个人资料
        │ public /api/v1 requests, validated DTOs
        ▼
planning API ──► PlanningService ──► PlanningRepository ──► PostgreSQL
        │                │                    │
        │                │                    ├─ user planning profile (minimal fields)
        │                │                    └─ versioned controlled recipes → qualified food catalog
        │                ▼
        │        deterministic target / retrieve / compose / validate
        ▼
existing AgentService ─► DietPlanningGraph ─► agent/tools.py narrow port
        │                       │                       │
        │                       │                       ├─ PlanningService
        │                       │                       └─ Memory/Retrieval services
        │                       ▼
        ├─ Agent ledger + stable SSE events
        └─ PostgreSQL Checkpointer (same user-owned thread_id)

Feedback: “换清淡 / 不吃某菜” → validated resume payload → affected-slot replacement
                                              │
                                              └─ explicit whitelist capture → Memory ledger
```

The diagram is a proposed implementation decomposition constrained by the project’s existing service/tool boundaries. [ASSUMED]

### Recommended Project Structure

```text
backend/app/
├── planning/                 # profile, target policy, controlled recipes, deterministic validator
│   ├── api.py                # /api/v1/planning/profile public contract
│   ├── schemas.py            # HTTP/domain DTOs; never Graph State/ORM/Provider DTO
│   ├── service.py            # target calculation, composition and validation orchestration
│   ├── ports.py              # planning persistence/retrieval ports
│   ├── repository.py         # tenant-filtered profile and controlled recipe queries
│   ├── models.py             # profile and controlled recipe persistence models
│   ├── data/                 # versioned seed recipes, no user data
│   └── README.md
├── agent/                    # extend State facade, tool port and lifecycle wiring only
└── migrations/versions/      # Alembic revision for planning tables

frontend/src/
├── features/plans/
│   ├── api/                  # Zod contracts / API client
│   ├── components/           # PlanPage, profile form, meal cards, status/empty/error states
│   ├── stream/               # only if feature-specific safe event projection is needed
│   ├── format.ts
│   └── README.md
└── app/                      # My page composes a link to personal-profile detail route only
```

The locations follow the declared backend and frontend ownership contracts; each new directory must include the README described above. [CITED: backend/ARCHITECTURE.md; frontend/ARCHITECTURE.md; AGENTS.md]

### Pattern 1: Deterministic target and plan validation as a closed-action tool

**What:** `PlanningService` receives a runtime-validated profile snapshot and candidate recipe slots, returns a typed `PASS | REPLAN | RELAX | BLOCK` result with rule/version/measurements; the graph branches on that action and never recomputes numbers. [ASSUMED]

**When to use:** every first generation and every resumed adjustment. [CITED: .planning/REQUIREMENTS.md]

**Implementation rule:** calculate food nutrition from the qualified catalogue at ingredient grams, aggregate unrounded decimals, then compare only to policy-defined intervals; round only in the public report. Existing nutrition tools already make the same “unrounded internal values; validated result” distinction. [CITED: backend/app/nutrition/schemas.py]

### Pattern 2: Slot-local replacement with immutable constraints

**What:** represent breakfast/lunch/dinner as stable slots with `slot_id`, selected controlled recipe, ingredient food IDs/grams, tags, matched constraints, and nutrition subtotal. On feedback, derive `affected_slot_ids`; preserve all other slot selections, fixed exclusions and prior valid profile/target snapshot. [ASSUMED]

**When to use:** “换清淡”“不吃某菜” and equivalent explicit feedback. [CITED: .planning/phases/05-diet-planning-subgraph/05-CONTEXT.md]

**Implementation rule:** first perform deterministic exclusion/tag matching; only the model’s structured feedback classifier may identify a natural-language target. If classification is ambiguous, interrupt for a menu/meal choice rather than replacing every meal. [ASSUMED]

### Pattern 3: Idempotent interrupt/resume boundary

**What:** store only a JSON-safe `PlanningInterrupt` payload (missing profile fields, conflict explanation, optional selected slot) and resume through the existing thread owner. LangGraph documents that an interrupt requires a persistent checkpointer and `thread_id`; resuming can rerun the whole node, so pre-interrupt side effects must be idempotent. [CITED: https://docs.langchain.com/oss/python/langgraph/interrupts; https://docs.langchain.com/oss/python/langgraph/persistence]

**When to use:** first-time required-field collection, ambiguous feedback target, or a conflict that cannot be safely relaxed. [CITED: .planning/phases/05-diet-planning-subgraph/05-CONTEXT.md]

**Implementation rule:** make profile save and explicit-memory capture idempotent with user-scoped request keys; do not put a side-effecting write before an interrupt unless the retry key is durable. Existing `AgentRun` already enforces `(thread_id, command_key)` uniqueness, and MemoryService derives an opaque direct-write key. [CITED: backend/app/agent/models.py; backend/app/memory/service.py]

### Pattern 4: One profile authority, one preference authority

**What:** `planning_profiles` stores only body/goal fields; Memory ledger remains the only mutable repository for avoidance/stable preference records. The plan form reads both, exposes them before generation, and records an explicit “none” confirmation in the plan request/state rather than manufacturing a memory. [ASSUMED]

**When to use:** initial plan creation, profile edit/delete, and later prefill. [CITED: .planning/phases/05-diet-planning-subgraph/05-CONTEXT.md]

### Anti-Patterns to Avoid

- **把 `MealAgentState` 的餐食分析字段强塞进规划：** 资料、餐单 slot、重排计数和健康拒绝需要独立版本化 State；服务层当前硬编码 `MealAgentState` 与 `meal-analysis` namespace，必须先抽象可验证 state codec/namespace，不能悄悄覆盖餐食分析 checkpoint。 [CITED: backend/app/agent/state.py; backend/app/agent/service.py]
- **在 React 或 Provider 中计算热量/宏量：** 这会制造两份数值真相，直接违反项目架构。 [CITED: AGENTS.md]
- **把菜谱预存总热量当权威：** 食谱内容和目录会演进，最终值必须按选中目录版本和克数重算。 [ASSUMED]
- **把“偏好”复制到个人资料表：** 两个可写入口会覆盖/漂移，违反 D-05。 [CITED: .planning/phases/05-diet-planning-subgraph/05-CONTEXT.md]
- **用 raw token/tool stream 驱动 UI：** UI 只消费稳定业务阶段和安全 summary，不泄露内部重排或推理。 [CITED: .planning/phases/05-diet-planning-subgraph/05-CONTEXT.md; backend/app/agent/api.py]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| 图暂停/恢复 | `thread_id` 到内存字典的自制会话状态 | PostgreSQL Checkpointer + 既有 AgentService 生命周期 | 持久 checkpoint 才能跨请求恢复，且现有服务已有所有权和租约。 [CITED: backend/app/main.py; backend/app/agent/service.py; https://docs.langchain.com/oss/python/langgraph/persistence] |
| 食材营养计算 | 浮点数、模型估算或前端总计 | 既有 `NutritionService` 的 Decimal、合格目录和校验模式 | 已有的计算 contract 明确要求可计算食材与确定性结果。 [CITED: backend/app/nutrition/schemas.py; backend/app/nutrition/service.py] |
| 长期偏好写入/删除 | 新 `preferences` 表或直接调用 Mem0 | `MemoryService.capture_explicit_preferences` / 现有 ledger | 它已强制类别白名单、用户隔离、来源和可删除外部同步。 [CITED: backend/app/memory/service.py] |
| SSE parser/reconnect | feature 内第二个手写 parser | `useAgentEventStream` 的 snapshot-first、Last-Event-ID 模式 | 既有实现覆盖分片、重复和序列 gap。 [CITED: frontend/src/features/agent/stream/README.md] |
| 密码/认证/鉴权 | 计划模块本地 token 或 `user_id` 参数信任 | `AuthenticatedPrincipal` + 服务端 tenant-filtered repository | 现有受保护 API 约定不把 UUID 当授权能力。 [CITED: backend/AGENTS.md; backend/ARCHITECTURE.md] |

**Key insight:** 本阶段真正复杂的部分不是“生成三道菜”，而是可重复的约束执行、状态恢复、授权隔离和可解释失败；这些都已有基础设施或明确领域边界，不能用 prompt 拼接掩盖。 [ASSUMED]

## Target and Recipe Policy

### Deterministic target policy

1. 接受范围限定为非孕/非哺乳、非未成年人、无疾病/用药/进食障碍/自伤或极端体重操控请求的成人普通饮食参考；任一高风险 flag 直接返回 `BLOCK_HEALTH_SCOPE`，不进入计算或食谱检索。D-15 已锁定这一产品边界；孕期营养确有不同的能量/营养需求，CDC/ACOG/WHO 类资料支持将其转介给临床专业人员。 [CITED: .planning/phases/05-diet-planning-subgraph/05-CONTEXT.md; https://www.acog.org/womens-health/faqs/healthy-eating-during-pregnancy; https://www.who.int/tools/elena/interventions/nutrition-counselling-pregnancy]
2. 用 Mifflin–St Jeor 的健康成人 REE 公式计算基数：男性 `10W + 6.25H - 5A + 5`，女性 `10W + 6.25H - 5A - 161`；原始研究的样本为 19–78 岁健康/肥胖成年人，因此实现必须将其称为估算值，不能扩展为医学诊断。 [CITED: https://pubmed.ncbi.nlm.nih.gov/2305711/]
3. 将 REE 乘以**版本化、五档、可解释**活动因子并叠加受限目标速度的能量调整；五档因子、最小热量地板及增重档位不是上游已冻结的规范，须集中在 `target-policy.v1`、有单元测试并在 UI 显示“估算”。 [ASSUMED]
4. 采用成人 AMDR 作为宏量的宽区间 guard：碳水 45–65% 能量、蛋白质 10–35%、脂肪 20–35%；目标 g 数必须以 4/4/9 kcal/g 在确定性工具内推导。AMDR 不是针对任何个人的处方，不能消除 D-15 拒绝边界。 [CITED: https://www.nationalacademies.org/read/27957/chapter/5]
5. 减重只提供“维持、渐进减重”保守预设；渐进减重上限可设为不超过约 0.5 kg/week，而超出速度拒绝/转介。CDC 将约每周 1–2 lb 描述为渐进、稳定的减重节奏；这里选择更保守的 0.5 kg/week 是项目安全政策，不是医学处方。 [CITED: https://www.cdc.gov/healthy-weight-growth/losing-weight/index.html] [ASSUMED]

### Controlled recipe minimum model

| Entity | Required data | Constraint |
|---|---|---|
| `PlanningProfile` | `user_id`, height, weight, age, sex enum, activity level, goal, speed preset, policy version, timestamps/deleted marker | 一位用户最多一个 active profile；所有读取/更新/删除按 `user_id`；不存忌口和口味。 [ASSUMED] |
| `ControlledRecipe` | stable recipe ID, recipe/catalog version, meal slot eligibility, short method/flavor tags, active/audited flag, source/license metadata | 只包含本阶段展示所需短标签，非完整配方或购物清单。 [CITED: .planning/phases/05-diet-planning-subgraph/05-CONTEXT.md] [ASSUMED] |
| `ControlledRecipeIngredient` | recipe ID, qualified `food_catalog_item` ID, catalog version, grams/controlled portion, ordering | 食材必须指向合格目录；最终营养由目录重算。 [CITED: backend/app/nutrition/models.py; backend/app/nutrition/schemas.py] [ASSUMED] |
| `PlanValidationResult` | target interval, plan totals, macro energy shares, exclusions checked, repeat score, violations, relaxation delta/reason, rule version | 这是工具 DTO/State 摘要，不是 ORM 或 Provider DTO。 [ASSUMED] |

### Composition and relaxation order

1. 过滤不活跃、未审计、食材不合格或违反不可放宽排除项的 recipe。 [ASSUMED]
2. 按早餐/午餐/晚餐槽位、已确认偏好标签和当前 profile 目标组成候选；计算 recipe/日总计。 [ASSUMED]
3. 先以严格热量和宏量范围验证，再以 deterministic `repeat_score`（同 recipe、同主食材、同烹饪标签分别计分）验证。 [ASSUMED]
4. 若无严格候选，只能放宽热量/宏量区间，记录精确偏离与原因；不得放宽忌口、显式排除项或健康拒绝。 [CITED: .planning/phases/05-diet-planning-subgraph/05-CONTEXT.md]
5. 每次失败/放宽都消耗一次 `replan_count`；达到三次后产出 `LIMIT_REACHED` 可解释报告，不再调用模型或工具。 [CITED: .planning/phases/05-diet-planning-subgraph/05-CONTEXT.md]

## Common Pitfalls

### Pitfall 1: 资料默认值被当成用户确认

**What goes wrong:** 预填档案或记忆存在时，页面直接生成，用户从未复核本次身体数据、目标或偏好。 [CITED: .planning/phases/05-diet-planning-subgraph/05-CONTEXT.md]

**How to avoid:** 所有字段在生成前可见、可编辑，且用显式“本次使用/保存到个人资料”控制；“无忌口/无特别偏好”也应是用户确认值。 [ASSUMED]

### Pitfall 2: 规划 State 覆盖餐食分析 checkpoint

**What goes wrong:** 现有 `_load_checkpoint` 和 `_persist_checkpoint` 固定使用 `meal-analysis` namespace 与 `MealAgentState`，直接复用会使两个子图读写同一个 schema。 [CITED: backend/app/agent/service.py]

**How to avoid:** 先定义 graph-kind → State model → checkpoint namespace 的显式映射，例如 `meal-analysis` 与 `diet-planning`；任何 resume 先验证 state kind、线程所有权和状态版本。 [ASSUMED]

### Pitfall 3: interrupt 前的副作用重复执行

**What goes wrong:** LangGraph 在恢复后会从节点开头重新执行；无幂等的资料保存、记忆写入或外部调用会重复。 [CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]

**How to avoid:** 将副作用放在可恢复、可重试、带稳定 request key 的 service 操作中；测试同一 resume 两次只产生一个 profile/memory 结果。 [ASSUMED]

### Pitfall 4: 把限制食材的自然语言当作模型推测记忆

**What goes wrong:** “不吃某菜”是明确用户反馈，应该按白名单写入；而模型从历史中猜出的偏好不能自动成为长期记忆。 [CITED: .planning/phases/05-diet-planning-subgraph/05-CONTEXT.md; backend/app/memory/service.py]

**How to avoid:** 复用 `capture_explicit_preferences` 规则/账本，新增的规划 feedback parser 只能产生 allowlisted canonical statement；无法确定时只影响当前计划或追问。 [ASSUMED]

### Pitfall 5: 用单点目标或多余小数伪造医疗精度

**What goes wrong:** Mifflin–St Jeor 是 REE 预测公式，健康饮食构成也随个人与生活环境变化。 [CITED: https://pubmed.ncbi.nlm.nih.gov/2305711/; https://www.who.int/news-room/fact-sheets/detail/healthy-diet]

**How to avoid:** UI 显示区间、计划值和偏低/适中/偏高；底部持续显示非医疗提示，拒绝 D-15 范围。 [CITED: .planning/phases/05-diet-planning-subgraph/05-CONTEXT.md]

### Pitfall 6: 前端绕开 H5 壳或把偏好编辑复制进“我的”

**What goes wrong:** 详情页和 Tab 页混用会产生双滚动、底部栏遮挡；复制偏好表单会引入两份写入口。 [CITED: docs/ui/h5-foundation.md; .planning/phases/05-diet-planning-subgraph/05-CONTEXT.md]

**How to avoid:** `/app/plans` 在 `AppShell` 内；个人资料编辑在 `DetailLayout`；“我的”只新增个人资料入口，偏好跳回既有记忆页。 [ASSUMED]

## Code Examples

### Resume-safe planning interrupt

```python
# Source pattern: https://docs.langchain.com/oss/python/langgraph/interrupts
# Proposed project shape; payload contains business-safe data only.
from langgraph.types import Command, interrupt

def require_complete_profile(state: PlanningAgentState) -> dict[str, object]:
    missing = state.profile_snapshot.missing_required_fields()
    if missing:
        answers = interrupt({
            "kind": "planning_profile_required",
            "missing_fields": missing,
            "safe_message": "请补全资料后继续生成普通饮食参考。",
        })
        return {"profile_snapshot": PlanningProfileInput.model_validate(answers)}
    return {}

# Boundary service verifies owned thread and resumes using Command(resume=validated_payload).
```

The payload must remain JSON-serializable, and operations before `interrupt()` must be idempotent because the node restarts on resume. [CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]

### Closed deterministic validation result

```python
# Proposed project domain DTO; the model does not calculate these values.
class PlanValidationAction(StrEnum):
    PASS = "PASS"
    REPLAN = "REPLAN"
    RELAX = "RELAX"
    BLOCK = "BLOCK"
    LIMIT_REACHED = "LIMIT_REACHED"

def validate_plan(target: DailyTarget, plan: MealPlan, constraints: Constraints) -> PlanValidationResult:
    totals = nutrition_tool.recalculate_all(plan.ingredients)
    violations = rules.evaluate(totals=totals, constraints=constraints)
    return rules.closed_result(totals=totals, violations=violations)
```

The proposed shape follows the existing nutrition module’s closed action and runtime-validation pattern. [CITED: backend/app/nutrition/schemas.py]

## State of the Art

| Old / unsafe approach | Current project approach | Impact |
|---|---|---|
| Stateless prompt continuation or a process-memory conversation | Persistent checkpoints keyed by `thread_id`, with a durable run ledger | A user can continue the owned thread after a pause; process restart does not inherently lose the checkpoint. [CITED: backend/app/agent/service.py; https://docs.langchain.com/oss/python/langgraph/persistence] |
| Model-generated nutrition totals | Versioned controlled catalogue + deterministic calculations | Numeric conclusions become replayable and testable. [CITED: AGENTS.md; backend/app/nutrition/schemas.py] |
| Raw model/tool streaming to user | Snapshot + persisted safe SSE summaries | UI can show stable stages without leaking provider text or chain of thought. [CITED: backend/app/agent/api.py; .planning/phases/05-diet-planning-subgraph/05-CONTEXT.md] |
| A single mutable “profile/preferences” blob | Separate authoritative profile and audited preference ledger | Avoidance/stable preference deletion and isolation keep their existing semantics. [CITED: backend/app/memory/service.py; .planning/phases/05-diet-planning-subgraph/05-CONTEXT.md] |

**Deprecated/outdated for this phase:** Treating `diet_planning_not_available()` as a route implementation is no longer valid once Phase 5 begins; replace only that closed branch while preserving main-graph routing and lifecycle controls. [CITED: backend/app/agent/graph.py; .planning/ROADMAP.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | A new `app/planning` bounded-context module is the correct owner for profile, recipes and deterministic validation. | Summary / Structure | Directory ownership and API scope may need a different project-wide decision. |
| A2 | Five activity factors, safe speed deltas, calorie floors and gain presets must be explicitly selected in `target-policy.v1`; no frozen authoritative project policy supplied their exact values. | Target and Recipe Policy | An unsafe or misleading target policy could be shipped. |
| A3 | Profile should store a singleton active record per user while preferences remain only in Memory ledger. | Pattern 4 / Model | An alternate history/version requirement would need a schema adjustment. |
| A4 | Recipe ingredient totals should be recomputed from qualified food records rather than trusted recipe totals. | Patterns / Model | Incorrect snapshots could cause false nutrition reports. |
| A5 | Slot-local replacement and the proposed repeat-score dimensions are the safest MVP implementation of D-10/D-14. | Pattern 2 / Composition | User feedback could be applied too narrowly or too broadly without adequate tests. |

## Resolved Implementation Contracts

以下结论为本阶段冻结的实现合同。它们是面向普通成年人的产品安全策略与版本化算法参数，不是医疗处方，也不声称对个人具备医学有效性。

### R-01: `target-policy.v1`（已冻结）

- 仅接受年龄 `19..78`、明确选择 Mifflin–St Jeor 公式变体、且不触发 D-15 高风险标记的资料。低于 19 岁、超过公式研究样本范围、孕哺、疾病/治疗/用药、进食障碍/自伤或极端体重操控意图一律返回 `BLOCK_HEALTH_SCOPE`，在计算和检索前终止。
- 五档活动因子固定为：`sedentary=1.20`、`light=1.375`、`moderate=1.55`、`high=1.725`、`very_high=1.90`。它们是 `target-policy.v1` 的可解释产品常量；D-02 的五档用户示例必须逐字对应这些枚举。
- 目标/速度固定为三个不接受自由数值输入的预设：`maintain=0 kcal/day`、`gradual_loss=-250 kcal/day`、`gradual_gain=+200 kcal/day`。任何未知枚举、自定义速度或“更快”意图都返回 `BLOCK_HEALTH_SCOPE` 与 D-16 转介文案。`gradual_loss` 低于研究中所述约 `0.5 kg/week` 的保守项目上限；`gradual_gain` 是产品策略，不是医疗建议。
- 基础目标为 `Mifflin–St Jeor REE × activity_factor + preset_delta`。若结果小于 `1200 kcal/day`，返回 `BLOCK_HEALTH_SCOPE`，不截断、不暗中抬高。公共能量目标区间是该结果的 `±100 kcal/day`，下限同样低于 1200 时拒绝。碳水、蛋白质、脂肪区间分别以 AMDR `45–65%`、`10–35%`、`20–35%` 和 `4/4/9 kcal/g` 从能量区间确定性换算；内部用 `Decimal`，仅公共报告取整。所有 DTO 都带 `target-policy.v1` 与 `mifflin-st-jeor.v1`。

### R-02: 公式参数安全合同（已冻结）

- 字段命名为 `formula_variant`，只允许用户明确选择 `mifflin_st_jeor_male` 或 `mifflin_st_jeor_female`；它不是身份推断字段，前端不可根据姓名、资料、历史记录或模型输出默认选择。
- 用户未选择、撤回选择或不能使用这两个公开公式变体时，`DietPlanningStartCommand` 返回 `NEEDS_INPUT`，不得生成个性化目标或餐单；页面仅保留 D-16 所允许的通用、非医疗均衡饮食原则入口。
- 该字段及其限制必须在服务测试、严格启动命令 DTO、个人资料表单和公开错误映射中一致出现；UI 标示“用于目标估算的身体参数”，不把结果表述为诊断。

### R-03: 受控菜谱来源、许可与审核合同（已冻结）

- v1 seed 仅可使用项目自有、结构化的短菜名/份量/标签数据；禁止运行时抓取、复制或改写第三方食谱正文、图片、步骤或购物清单。每条 seed 的 `source_kind` 必须为 `project_authored`，`source_reference` 为仓库内可追溯引用，`license` 为 `LicenseRef-Project-Authored-v1`，并且 `recipe_version` 与 `catalog_version` 非空。
- 只有含 `audit_status=approved`、`audited_at`、`audited_by_role=nutrition_catalog_reviewer`、`audit_version` 的记录才可激活。`nutrition_catalog_reviewer` 是项目中获授权核验“来源权利、标签与合格食材目录映射”的审核角色；它不宣称医学营养师资质。
- `ControlledRecipe` DTO、JSON seed、ORM/Alembic 约束和 repository 激活查询必须同时强制这些字段。缺失、未知许可、非 `approved` 状态、无审核角色/时间、catalog 版本不匹配或非合格食材引用的 recipe 必须被拒绝；测试覆盖全部拒绝分支。最终营养仍只从合格食材目录和克数重算。

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|---|---|---|---|---|
| Node.js / npm | frontend build, test and Playwright | ✓ | Node `22.23.2`, npm `10.9.8` | — [VERIFIED: local shell] |
| Docker CLI | PostgreSQL/pgvector integration environment | ⚠️ client only | Docker `29.4.0`; daemon access denied | Start/authorize OrbStack Docker daemon before integration/browser runs. [VERIFIED: local shell] |
| Python runtime | backend execution | ⚠️ system runtime is too old | system Python `3.9.6`; project requires `>=3.12` | Use an already-provisioned Python 3.12 project environment; current `uv python find` is blocked by sandbox cache permissions. [VERIFIED: local shell] [CITED: backend/pyproject.toml] |
| PostgreSQL client/service | repository integration checks | ✗ / not detected | — | Docker-backed project database once daemon is available. [VERIFIED: local shell] |
| Context7 CLI | external library documentation lookup | ✗ | — | Official LangGraph/FastAPI docs were used via web lookup. [VERIFIED: local shell] |

**Missing dependencies with no fallback:** Docker daemon authorization blocks real PostgreSQL integration and cross-stack browser execution in this environment. [VERIFIED: local shell]

**Missing dependencies with fallback:** System Python is not sufficient, but the repository’s declared Python 3.12 environment is the expected execution path once provisioned. [VERIFIED: local shell] [CITED: backend/pyproject.toml]

## Security Domain

### Applicable ASVS Categories

OWASP ASVS is a security-control verification standard; its current guide includes authentication, session management, access control, validation/sanitization and stored cryptography categories. [CITED: https://devguide.owasp.org/en/03-requirements/05-asvs/]

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | yes | Existing `AuthenticatedPrincipal`; planning/profile routes remain protected. [CITED: backend/AGENTS.md; backend/ARCHITECTURE.md] |
| V3 Session Management | yes | Existing short access token + HttpOnly rotating refresh token; do not create planning-specific session state. [CITED: AGENTS.md] |
| V4 Access Control | yes | Tenant-filter every profile, recipe-selection result, Agent thread/run/event and delete operation by authenticated `user_id`. [CITED: backend/AGENTS.md; backend/app/agent/repository.py] |
| V5 Input Validation | yes | Pydantic `extra=forbid`, field range/enum validation, server-side high-risk classifier/guard, structured resume payload validation. [CITED: AGENTS.md; backend/app/nutrition/schemas.py; https://cornucopia.owasp.org/taxonomy/asvs-4.0.3/05-validation-sanitization-and-encoding/01-input-validation] |
| V6 Cryptography | yes | Reuse existing authentication/security primitives; do not implement custom hashing/encryption for profile data or request keys. [CITED: AGENTS.md; backend/AGENTS.md] |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---|---|---|
| Foreign user reads/updates/deletes a profile or planning thread by UUID | Information disclosure / Tampering | Authenticate first and use `user_id` in every repository predicate; test foreign IDs as indistinguishable unavailable. [CITED: backend/AGENTS.md; backend/app/agent/repository.py] |
| Prompt-injected/freeform feedback tries to bypass exclusions or medical boundary | Elevation of privilege / Tampering | Parse only into validated, closed feedback intents; deterministic guard and validator own exclusions/health refusal. [ASSUMED] |
| Replayed resume duplicates a preference or profile write | Tampering | Durable idempotency key, existing run uniqueness and Memory ledger direct request key; test duplicate resume. [CITED: backend/app/agent/models.py; backend/app/memory/service.py] |
| Health details/provider reasoning appear in logs or SSE | Information disclosure | Persist only minimized profile fields, safe report/event fields and stable summaries; never raw prompts, thinking or secrets. [CITED: AGENTS.md; backend/app/agent/api.py; backend/app/agent/models.py] |
| Infinite candidate relaxation / tool loop | Denial of service | Enforce graph/tool/time/cost budgets plus `replan_count <= 3`; terminal response must stop. [CITED: AGENTS.md; .planning/phases/05-diet-planning-subgraph/05-CONTEXT.md] |

## Sources

### Primary (HIGH confidence)

- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) — persistent `thread_id`, JSON-safe payloads, `Command(resume=...)`, node re-execution and idempotency rule.
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) — checkpoint/thread persistence requirements.
- [LangGraph subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs) — subgraph persistence modes and interrupt inheritance.
- [Mifflin–St Jeor original study record](https://pubmed.ncbi.nlm.nih.gov/2305711/) — healthy adult REE equation and study scope.
- [National Academies AMDR table](https://www.nationalacademies.org/read/27957/chapter/5) — adult carbohydrate/protein/fat AMDR ranges.
- [CDC gradual weight-loss guidance](https://www.cdc.gov/healthy-weight-growth/losing-weight/index.html) — gradual 1–2 lb/week framing.
- [WHO healthy diet fact sheet](https://www.who.int/news-room/fact-sheets/detail/healthy-diet) — diet varies by individual characteristics and is based on adequacy/balance/moderation/diversity.
- [ACOG pregnancy nutrition guidance](https://www.acog.org/womens-health/faqs/healthy-eating-during-pregnancy) — pregnancy has distinct nutrition considerations and dietitian/clinician role.
- [OWASP ASVS guide](https://devguide.owasp.org/en/03-requirements/05-asvs/) — ASVS categories and verification intent.
- Project sources: `AGENTS.md`, `backend/AGENTS.md`, `frontend/AGENTS.md`, `backend/ARCHITECTURE.md`, `frontend/ARCHITECTURE.md`, `docs/ui/h5-foundation.md`, phase context and current backend/frontend modules cited inline.

### Secondary (MEDIUM confidence)

- [FastAPI StreamingResponse documentation](https://fastapi.tiangolo.com/advanced/custom-response/) — generator cancellation behaviour; existing SSE implementation is finite replay rather than a live provider stream.

### Tertiary (LOW confidence)

- None; all unverified implementation choices are explicitly listed in the Assumptions Log.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — pinned project dependencies and existing runtime wiring were inspected; primary LangGraph/FastAPI docs were checked. [CITED: backend/pyproject.toml; frontend/package.json; backend/app/main.py]
- Architecture: HIGH — existing Agent/Service/Tool/Repository and H5 contracts were inspected; the new `planning` module placement itself remains an assumption. [CITED: backend/ARCHITECTURE.md; frontend/ARCHITECTURE.md]
- Nutrition target policy: MEDIUM — equation/AMDR/safety references are primary, but exact factors, floors and speed presets are intentionally not frozen. [CITED: https://pubmed.ncbi.nlm.nih.gov/2305711/; https://www.nationalacademies.org/read/27957/chapter/5]
- Pitfalls: HIGH — checkpoint/interrupt restart behaviour is official and project checkpoint namespace coupling was inspected. [CITED: https://docs.langchain.com/oss/python/langgraph/interrupts; backend/app/agent/service.py]

**Research date:** 2026-09-01
**Valid until:** 2026-09-30 for framework/library facts; target-policy assumptions require confirmation before implementation. [ASSUMED]
