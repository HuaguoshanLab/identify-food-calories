# Phase 2: 可追问的 Agent 核心 - Research

**Researched:** 2026-08-28  
**Domain:** LangGraph 可恢复工作流、确定性营养工具、FastAPI SSE 与 React H5  
**Confidence:** HIGH（外部包合法性门禁因网络失败降为待人工复核）

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### 文字餐食解析与追问节奏

- **D-01:** 用户可使用克数或营养目录中的受控常见份量描述食物，例如“一碗”“半个”“一份”。只有目录存在明确、版本化的换算关系时才能直接换算；否则追问克数、大小或其他必要信息。
- **D-02:** Agent 先展示已理解的整餐项目清单，再在单轮中集中询问所有阻塞计算的缺失字段，不为每个字段或每道菜机械地产生一轮对话。
- **D-03:** 用户可用自然语言定向修正，例如“米饭改成半碗”或“第二项不是鸡肉，是鱼”。系统保留其他已确认信息，只让受影响项目重新查询、计算和校验。
- **D-04:** 当输入完整、目录匹配唯一且没有阻塞校验问题时，Agent 直接调用确定性工具计算，不增加固定的“计算前确认”步骤。

#### 模糊菜名与目录外食物

- **D-05:** 目录查询出现歧义时，最多展示 3 个具备计算资格的候选，并提供能帮助区分的做法、常见份量或来源信息；图中断并等待用户选择，禁止自动采用相似度最高项。
- **D-06:** 只有目录明确登记且唯一的受控别名，以及大小写、空白等无语义规范化，可以自动映射到标准食物。拼写相似、方言猜测和模型推断只能形成候选，不能自动确定。
- **D-07:** Phase 2 建立小型、真实、版本化且可追溯的 MVP 营养种子目录，优先覆盖演示和冻结测试需要的常见主食、肉蛋奶、蔬果及少量常见菜；不把本阶段扩张为大规模中国菜数据库建设。
- **D-08:** 用户不需要预先提供营养数据。研究阶段负责确认适合的合法数据源、授权和引用方式；每条公开可计算记录必须满足 NUT-01/NUT-02 的来源、授权、版本和资格约束。
- **D-09:** 目录外食物不允许模型估算营养值。用户可以改名、选择有效候选或排除该项；其他已知项目仍可计算，但逐项结果和整餐汇总必须明确列出未计入项目，不能把部分结果伪装成完整整餐结果。

#### 文本分析结果与会话收口

- **D-10:** 最终结果同时展示逐项明细和整餐汇总。每项至少包含标准菜名、输入份量/换算克数、热量、蛋白质、脂肪和碳水；汇总区同时展示未计入项目与非阻塞校验提示。
- **D-11:** 展示层把热量舍入为整数 kcal，把蛋白质、脂肪和碳水展示为 1 位小数；确定性计算和校验内部保留足够精度，禁止用展示舍入值反向参与累计计算。
- **D-12:** 校验异常按严重度确定性分流：可修正异常先重新核算；缺失信息触发追问；负数、严重营养密度异常、总量不一致等硬错误阻止最终报告；非阻塞误差提示可以随可信结果展示。模型不能覆盖工具校验结论。
- **D-13:** 报告生成后本轮运行标记为完成，不增加没有保存语义的确认步骤。用户仍可在同一线程中定向修正并触发受影响部分重算；分析另一餐必须创建新线程。确认并保存餐食留到 Phase 4。

#### SSE、失败反馈与断线恢复

- **D-14:** SSE 发送稳定、版本化的业务阶段事件，例如理解输入、等待补充、查询目录、计算营养、校验结果、完成和失败；事件只携带安全摘要与结构化数据，不逐 Token 暴露模型中间文本，更不能输出思维链。
- **D-15:** 页面刷新、短暂断网或 SSE 连接断开后，前端使用同一 `thread_id` 自动重新获取权威线程快照并继续接收事件。已完成节点、模型调用和工具调用不得重跑或重复计费。
- **D-16:** 只有超时、限流和临时网络错误等瞬时故障可以在总体循环、调用、时间和费用预算内自动重试一次。参数错误、目录无结果和确定性校验失败不得盲目重试；自动重试仍失败时保留 Checkpoint，并提供用户触发的重试入口。
- **D-17:** 达到最大循环、最大工具调用、超时或费用上限时，运行进入明确、可测试的终止状态。前端显示安全且稳定的失败类别，如需要更多信息、目录无可用数据、服务暂时不可用或达到运行上限，并按情况提供补充信息或重试入口；禁止返回堆栈、Provider 原文或内部节点细节。

### the agent's Discretion

- 在不削弱 D-07/D-08 的前提下，由研究与规划确定 MVP 种子目录的具体条目数量、合法数据源、导入格式和版本标识。
- 由研究与规划确定 LangGraph State 字段、节点拆分、条件边、事件 Schema、幂等键、Checkpoint 表结构和具体预算数值，但必须实现上述用户行为及 AGT-02/AGT-05/AGT-07 的可追溯约束。
- 在稳定事件类别和错误语义不变的前提下，可以调整用户可见阶段文案、候选说明文案、重连退避和非阻塞提示样式。
- 可以决定 Phase 2 冻结测试样本的具体组成，但必须覆盖多菜输入、常见份量、集中追问、模糊候选、目录外部分结果、定向修正、interrupt/resume、断线恢复、幂等重放和全部终止条件。

### Deferred Ideas (OUT OF SCOPE)

- 图片上传、安全处理与 Qwen-VL 多菜识别 — Phase 3。
- 用户确认并保存餐食、历史记录、长期偏好与 Mem0 — Phase 4。
- 真实饮食规划子图与用户反馈后的餐单调整 — Phase 5。
- 大规模营养目录扩充和管理员维护界面 — Phase 6。
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|---|---|---|
| AGT-01 | LangGraph 主图按请求意图路由到餐食分析子图或饮食规划子图。 | 主图保留稳定能力枚举；Phase 2 实装餐食子图，规划意图返回明确的未开放终态，不伪造 Phase 5。 `[VERIFIED: .planning/REQUIREMENTS.md]` |
| AGT-02 | State 明确保存用户、线程、消息、图片引用、识别项、缺失字段、工具结果、校验问题、重试次数、下一动作和最终报告。 | 本文给出分层、可校验且可版本化的 `AgentState`；Phase 2 的图片引用固定为空/不接受。 `[VERIFIED: .planning/REQUIREMENTS.md]` |
| AGT-03 | 菜品模糊、识别失败或份量不足时，图通过 interrupt 暂停并向用户追问。 | 采用集中追问节点、JSON 可序列化 interrupt payload 和稳定候选 ID。 `[CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]` |
| AGT-04 | 用户回复后，系统使用同一 `thread_id` 从持久化 Checkpoint 恢复，而不是重跑整条链路。 | 使用 `Command(resume=...)`、相同 `thread_id` 与 PostgreSQL saver；节点重入要求副作用幂等。 `[CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]` |
| AGT-05 | 图设置最大循环、最大工具调用、超时和终止条件，不能无限重试。 | AI-SPEC 预算计数器前置判定，`recursion_limit` 只作为最后防线。 `[VERIFIED: .planning/phases/02-agent/02-AI-SPEC.md]` |
| AGT-06 | 每个节点、条件边和工具调用都可通过确定性测试替身验证。 | 纯节点/路由函数、Fake Provider、Fake Clock、Fake Repository 与真实 PostgreSQL checkpointer 分层测试。 `[VERIFIED: AGENTS.md]` |
| AGT-07 | Agent 运行记录包含图版本、模型版本、提示词版本、工具版本、状态与耗时。 | 本文定义 thread/run/event/invocation 审计表及版本快照。 `[VERIFIED: .planning/phases/02-agent/02-AI-SPEC.md]` |
| NUT-01 | 营养目录包含稳定 ID、别名、每 100g 营养、常见份量、来源、授权和版本。 | 采用 USDA FoodData Central CC0 数据与不可变目录版本/来源清单。 `[CITED: https://fdc.nal.usda.gov/api-guide/]` |
| NUT-02 | `search_food_catalog` 工具只返回具备可计算资格的数据。 | 查询只返回来源、授权、版本、四项营养及份量换算均通过资格门禁的记录。 `[VERIFIED: .planning/phases/02-agent/02-CONTEXT.md]` |
| NUT-03 | `calculate_nutrition` 根据菜品和克数确定性计算热量、蛋白质、脂肪和碳水。 | 使用 `Decimal` 按每 100g 比例计算，展示时才舍入。 `[VERIFIED: .planning/phases/02-agent/02-CONTEXT.md]` |
| NUT-04 | `validate_nutrition_result` 检查负数、异常密度、总量不一致与越界份量。 | 校验规则版本化并输出机器可判定 severity/action，模型无覆盖权。 `[VERIFIED: .planning/phases/02-agent/02-AI-SPEC.md]` |
| NUT-05 | 校验异常时按明确规则重新核算、追问或终止，模型不能覆盖校验结果。 | 条件边只消费工具的结构化决定：`RECALCULATE/ASK/BLOCK/WARN/PASS`。 `[VERIFIED: .planning/phases/02-agent/02-CONTEXT.md]` |
| ARC-05 | 前后端使用版本化 OpenAPI 契约；流式 Agent 事件使用 SSE。 | 命令、快照和事件流分离；事件使用 SSE `id/event/data/retry` 字段及版本化 payload。 `[CITED: https://html.spec.whatwg.org/multipage/server-sent-events.html]` |
| ARC-06 | 模型 Provider 可替换且具备 fake 实现，测试不依赖真实付费 API。 | 定义窄接口 `parse_meal/apply_correction`，DeepSeek 与 Fake 为适配器。 `[VERIFIED: AGENTS.md]` |
| QLT-02 | Agent 路由、interrupt/resume、循环终止和工具选择具有状态图测试。 | 本文给出冻结用例、真实 saver 重启恢复及预算边界测试矩阵。 `[VERIFIED: .planning/phases/02-agent/02-AI-SPEC.md]` |
</phase_requirements>

## Summary

Phase 2 应实现成“PostgreSQL 权威运行账本 + LangGraph 可恢复状态机 + 确定性营养领域服务 + 只读可重放 SSE”的垂直闭环。LangGraph checkpoint 负责短期图状态，不负责线程授权、业务审计、SSE 重放或恰好一次副作用；这些必须由业务表和幂等调用账本承担。`thread_id` 只是恢复游标，任何 checkpoint 访问前都必须先以当前认证用户查询 `agent_threads`。 `[CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]` `[VERIFIED: AGENTS.md]`

主图只做意图路由和预算/终态治理，餐食子图依次解析、集中补缺、目录消歧、确定性计算、确定性校验、报告组装。营养值只来自版本化目录和工具；模型只输出结构化“用户表达的解释”，不能给数值真相、选中模糊候选或覆盖校验。当前 DeepSeek 官方模型名已变化，生产适配器应配置 `deepseek-v4-flash`，而不是已经退役的 `deepseek-chat`；这不改变“DeepSeek 文本 Provider”锁定决策。 `[CITED: https://api-docs.deepseek.com/updates]`

断线恢复必须采用“先取权威快照，再从 `latest_event_seq` 续订事件”。浏览器原生 `EventSource` 不能设置现有 Bearer `Authorization`，因此前端使用认证 `fetch()` 读取 SSE，并复用现有 access-token 刷新机制；SSE 连接不能拥有或取消图运行。 `[CITED: https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events]` `[VERIFIED: frontend/src/auth/AuthProvider.tsx]`

**Primary recommendation:** 按四个可演示垂直切片推进：克数直算 → 集中追问/恢复 → 修正/幂等/断线 → 真 DeepSeek/预算/冻结评测；每个切片都同时包含后端、数据库、公开 API、H5 和验收，不做“先铺完整后端再接页面”的水平拆分。 `[VERIFIED: .planning/phases/02-agent/02-CONTEXT.md]`

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| 用户文字输入、追问回复、进度与报告 | Browser / Client | API / Backend | H5 负责交互和展示；所有判断与真值留在后端。 `[VERIFIED: frontend/AGENTS.md]` |
| 身份、线程所有权、幂等命令、快照和 SSE | API / Backend | Database / Storage | API 从认证上下文绑定用户；PostgreSQL 保存权威账本和可重放事件。 `[VERIFIED: AGENTS.md]` |
| 路由、interrupt/resume、预算和终态 | API / Backend | Database / Storage | LangGraph 编排在后端，Checkpoint 持久化线程短期状态。 `[CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]` |
| 食物目录查询、份量换算、营养计算、校验 | API / Backend | Database / Storage | Application Service 持有确定性规则，Repository 只读取版本化目录。 `[VERIFIED: backend/AGENTS.md]` |
| 文字理解与修正解析 | External Provider | API / Backend | DeepSeek 只返回经 Pydantic 验证的结构化解释；Provider 接口隔离供应商。 `[CITED: https://api-docs.deepseek.com/api/create-response/]` |
| Checkpoint、运行审计、事件重放、目录版本 | Database / Storage | API / Backend | PostgreSQL 是权威持久层；checkpointer 表与 Alembic 业务表职责分离。 `[VERIFIED: AGENTS.md]` |

## Project Constraints (from AGENTS.md)

- 保持独立 `frontend/`、`backend/`，后端为模块化单体；禁止 Next.js、微服务、Kafka 和 Kubernetes。 `[VERIFIED: AGENTS.md]`
- 后端依赖只能是 API → Application/Service → Repository → Model；图节点通过工具适配器调用 Service，不能访问 ORM/Repository。 `[VERIFIED: AGENTS.md]`
- SQLAlchemy Model、Pydantic API Schema、LangGraph State、Provider DTO 必须分离并各自运行时校验。 `[VERIFIED: backend/AGENTS.md]`
- PostgreSQL 保存权威业务数据，Checkpoint 只保存短期图状态；业务 schema 变更必须使用 Alembic。 `[VERIFIED: AGENTS.md]`
- 配置 fail closed，测试不能回退 SQLite/开发库，密钥仅来自未提交环境变量。 `[VERIFIED: backend/AGENTS.md]`
- 不记录原文餐食、密钥、完整思维链或不必要敏感信息；健康输出只作普通饮食参考。 `[VERIFIED: AGENTS.md]`
- 新目录必须同提交新增职责/依赖/文件索引 README，并同步父级索引；本阶段需新增中文教学文档。 `[VERIFIED: AGENTS.md]`
- Repository/Checkpointer 使用独立真实 PostgreSQL，图使用 Fake Provider；用户页面还必须经 Playwright 与内置浏览器真实公开 API 验收。 `[VERIFIED: AGENTS.md]`

## Standard Stack

### Core

| Library / Service | Version | Purpose | Why Standard |
|---|---:|---|---|
| `langgraph` | 1.2.11 | 主图、子图、interrupt/resume、streaming | AI-SPEC 锁定；PyPI 当前版本发布于 2026-08-11，Python ≥3.10。 `[CITED: https://pypi.org/project/langgraph/]` |
| `langgraph-checkpoint-postgres` | 3.1.2 | PostgreSQL 图 checkpoint | AI-SPEC 锁定；提供 `AsyncPostgresSaver`、`setup()` 和异步连接/连接池入口。 `[CITED: https://pypi.org/project/langgraph-checkpoint-postgres/]` |
| FastAPI / Pydantic | 0.128.8 / 2.x | 认证 API、快照、命令与 SSE 契约 | 已批准并安装；`StreamingResponse` 支持异步生成器，lifespan 适合初始化共享资源。 `[VERIFIED: backend/pyproject.toml]` `[CITED: https://fastapi.tiangolo.com/advanced/custom-response/]` |
| SQLAlchemy / Alembic / PostgreSQL | 2.0.52 / 1.16.5 / project Compose | 权威业务表、迁移和事务 | 现有同步业务数据栈；checkpointer 使用独立 psycopg 异步连接。 `[VERIFIED: backend/pyproject.toml]` |
| DeepSeek Responses API | configured `deepseek-v4-flash` | 餐食文字解析与定向修正 | 当前 Responses API 支持 JSON Schema；显式关闭 thinking 以获得受控解析。 `[CITED: https://api-docs.deepseek.com/guides/responses_api/]` |
| React / TanStack Query | 19.2.8 / 5.102.6 | H5 交互、权威快照缓存 | 现有项目栈；无限 SSE 由独立 hook 管理，Query 只管理快照。 `[VERIFIED: frontend/package.json]` |

### Supporting

| Library | Version | Purpose | When to Use |
|---|---:|---|---|
| `httpx` | 0.28.1 | DeepSeek async HTTP adapter | 从 dev 依赖提升为运行时依赖；复用 lifespan `AsyncClient`，不引入额外 SDK。 `[VERIFIED: backend/pyproject.toml]` |
| `eventsource-parser` | 3.1.0 | 在认证 `fetch()` 字节流上解析 SSE | 仅前端流 hook 使用；该版本支持标准事件字段与缓冲边界。 `[CITED: https://github.com/rexxars/eventsource-parser]` `[ASSUMED]` |
| `arize-phoenix` / `arize-phoenix-otel` | 20.3.0 / 0.17.1 | 本地评测观测与安全 trace | 仅 dev/eval；默认不得导出原始餐食、prompt 或 checkpoint。 `[CITED: https://www.arize.com/docs/phoenix/tracing/how-to-tracing/setup-tracing/setup-using-phoenix-otel]` `[ASSUMED]` |
| `openinference-instrumentation-langchain` | 0.1.72 | LangGraph/LangChain trace instrumentation | 仅 dev/eval，需字段白名单处理。 `[CITED: https://pypi.org/project/openinference-instrumentation-langchain/]` `[ASSUMED]` |
| `promptfoo` | 0.122.0 | 冻结行为样本和回归评测 | 仅 eval；不要用发布数小时的新 0.122.1。 `[CITED: https://www.npmjs.com/package/promptfoo]` `[ASSUMED]` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|---|---|---|
| 原生 `EventSource` | 认证 `fetch()` + parser | 原生 API 自动重连但不能设置 Bearer header；当前认证架构下不合格。 `[CITED: https://developer.mozilla.org/en-US/docs/Web/API/EventSource/EventSource]` |
| 运行时调用 USDA API | 离线导入受控种子目录 | 在线外部查询会把限流、数据漂移和授权审计带入每次运行；离线清单可冻结版本和推导链。 `[CITED: https://fdc.nal.usda.gov/api-guide/]` |
| Open Food Facts | USDA FoodData Central | OFF 数据库为 ODbL 且有 attribution/share-alike 条件；本阶段小型权威种子库优先 CC0。 `[CITED: https://support.openfoodfacts.org/help/en-gb/12-api-data-reuse/94-are-there-conditions-to-use-the-api]` |
| DeepSeek 工具自由调用 | 图显式调用确定性工具 | 模型 tool call 只产生参数，应用仍须执行和校验；显式图边更容易证明预算和真值边界。 `[CITED: https://api-docs.deepseek.com/guides/tool_calls/]` |

**Installation（执行前必须完成人工合法性门禁）：**

```bash
cd backend
pip install langgraph==1.2.11 langgraph-checkpoint-postgres==3.1.2
# 将 httpx==0.28.1 从 dev 依赖移入 runtime

cd ../frontend
npm install eventsource-parser@3.1.0

# 仅 eval/dev
pip install arize-phoenix==20.3.0 arize-phoenix-otel==0.17.1 \
  openinference-instrumentation-langchain==0.1.72
npm install --save-dev promptfoo@0.122.0
```

## Package Legitimacy Audit

`slopcheck 0.6.1` 可执行，但本次环境无法解析 PyPI/npm registry；`pip index`、`npm view` 与 postinstall 查询也因 DNS 失败。因此按门禁规则，所有新增包即使已由官方文档/PyPI 页面确认，仍标为 `[ASSUMED]`，规划器必须在安装前放置 `checkpoint:human-verify`。 `[VERIFIED: slopcheck local run 2026-08-28]`

| Package | Registry | Age / publish | Downloads | Source Repo | slopcheck | Disposition |
|---|---|---|---|---|---|---|
| `langgraph` 1.2.11 | PyPI | 2026-08-11 | 未取得 | `langchain-ai/langgraph` | unavailable | `[ASSUMED]` Flagged — human verify |
| `langgraph-checkpoint-postgres` 3.1.2 | PyPI | 2026-08-07 | 未取得 | `langchain-ai/langgraph` | unavailable | `[ASSUMED]` Flagged — human verify |
| `eventsource-parser` 3.1.0 | npm | 2026-05-27 | 未取得 | `rexxars/eventsource-parser` | unavailable | `[ASSUMED]` Flagged — human verify/postinstall |
| `arize-phoenix` 20.3.0 | PyPI | 2026-08-17 | 未取得 | `Arize-ai/phoenix` | unavailable | `[ASSUMED]` Flagged — human verify |
| `arize-phoenix-otel` 0.17.1 | PyPI | 2026-08-10 | 未取得 | `Arize-ai/phoenix` | unavailable | `[ASSUMED]` Flagged — human verify |
| `openinference-instrumentation-langchain` 0.1.72 | PyPI | 2026-08-25 | 未取得 | `Arize-ai/openinference` | unavailable | `[ASSUMED]` Flagged — human verify |
| `promptfoo` 0.122.0 | npm | 2026-08 | 未取得 | `promptfoo/promptfoo` | unavailable | `[ASSUMED]` Flagged — human verify/postinstall |

**Packages removed due to slopcheck [SLOP] verdict:** none（未得到 verdict）。  
**Packages flagged as suspicious [SUS]:** none（未得到 verdict；全部按更严格的 unavailable 处理）。

## Architecture Patterns

### System Architecture Diagram

```text
Authenticated H5
  ├─ POST input/resume/correct + client_request_id
  ├─ GET authoritative snapshot
  └─ GET authenticated SSE + Last-Event-ID
            │
            ▼
FastAPI Agent API ── ownership check (user_id, thread_id)
            │
            ├────────► PostgreSQL business tables
            │           threads / runs / invocations / events / catalog
            │
            ▼
Application Run Supervisor (lease + idempotency + budgets)
            │
            ▼
LangGraph Main Graph
  route_intent ── diet_planning ──► CAPABILITY_NOT_AVAILABLE (Phase 5)
       │ meal_analysis
       ▼
Meal Analysis Subgraph
 parse/correct ─► normalize ─► missing? ─yes─► interrupt ─► resume
       │                         no
       │                         ▼
       └──────────────────► catalog search ─ambiguous─► interrupt
                                   │ unique/known
                                   ▼
                            deterministic calculate
                                   ▼
                            deterministic validate
                           ┌───────┼────────┐
                        recalc    ask      block/warn/pass
                           │       │               │
                           └───────┴──────────────► report / terminal
            │
            ├─ Provider port ─► DeepSeek adapter / Fake Provider
            └─ Tool ports ────► Nutrition Application Service ─► Repository

PostgreSQL Checkpointer ◄── graph state only
SSE replay/tail ◄────────── persisted safe business events
```

该边界保证断开 SSE 不会取消运行，重连不触发图重跑，且 checkpoint 泄露或猜测的 `thread_id` 不能绕过业务所有权检查。 `[VERIFIED: .planning/phases/02-agent/02-AI-SPEC.md]`

### Recommended Project Structure

```text
backend/app/
├── agent/                  # graph state/nodes/routes, run service, API schemas/router
├── nutrition/              # catalog/calculation/validation domain + service/repository
├── providers/reasoning/    # Provider protocol, DeepSeek adapter, fake, DTO
└── core/                   # validated provider/checkpoint/budget settings
backend/scripts/
└── nutrition_catalog/      # offline manifest import/verification
frontend/src/features/agent/
├── api/                    # commands + snapshot contracts
├── stream/                 # authenticated SSE parser/reconnect
└── components/             # composer, clarification, progress, report
docs/learning/
└── phase-02-agent-core.md
```

每个新增目录同提交创建 README，并更新直接父目录索引；目录划分不能把 LangGraph State、API Schema、Provider DTO 和 ORM 混成一个“万能模型”。 `[VERIFIED: AGENTS.md]`

### Pattern 1: 主图治理、子图按调用继承持久化

餐食子图以 `checkpointer=None` 编译并作为主图节点加入；主图由 PostgreSQL saver 编译。官方文档说明这种 per-invocation 子图默认继承父图 checkpointer，适合一次主图调用内的 interrupt/persistence，且不会把不同子图调用错误共享成同一长期线程。 `[CITED: https://docs.langchain.com/oss/python/langgraph/use-subgraphs]`

主图路由枚举固定为 `MEAL_ANALYSIS | DIET_PLANNING`。Phase 2 的 `DIET_PLANNING` 分支必须产生稳定 `CAPABILITY_NOT_AVAILABLE` 终态，不实现或伪造规划结果。 `[VERIFIED: .planning/phases/02-agent/02-CONTEXT.md]`

### Pattern 2: interrupt 节点必须可重入

`interrupt()` 恢复时节点从头执行，故 interrupt 前不得直接发送邮件、计费或插入不可幂等事件；必须先通过 invocation/event 唯一键写入，重复执行读取既有结果。interrupt payload 只放 JSON 可序列化、安全、稳定的字段；恢复使用同一 `thread_id` 和 `Command(resume=validated_answer)`。 `[CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]`

### Pattern 3: Checkpoint 与业务账本分治

`AsyncPostgresSaver.setup()` 创建/迁移自身 checkpoint 表，应成为显式部署/初始化命令；应用 lifespan 只建立连接、编译图和关闭资源，不能每个 worker 启动都隐式争抢 setup。业务表仍全部走 Alembic。 `[CITED: https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-postgres/langgraph/checkpoint/postgres/aio.py]` `[VERIFIED: backend/AGENTS.md]`

现有 SQLAlchemy URL 使用 `postgresql+psycopg://`，checkpointer 需要 psycopg conninfo；用 SQLAlchemy URL 对象改变 driver 后安全渲染，禁止字符串替换或记录含密码 URL。 `[VERIFIED: backend/app/core/config.py]`

### Pattern 4: 运行与流分离

POST 命令只创建/复用 run 并返回 `202`；进程内 supervisor 通过 PostgreSQL lease 领取 run，执行图并把安全事件持久化；GET SSE 只重放/尾随事件表。这样客户端断线不拥有取消权，服务进程崩溃后可从 checkpoint 与过期 lease 恢复。v1 不需要队列或 Kafka。 `[ASSUMED]`

### Pattern 5: 版本化状态，局部失效

同线程每次用户输入/修正增加 `input_version`。餐食项有稳定 `item_id`；修正只将受影响项加入 `dirty_item_ids`，未变化项继续引用原目录版本和确定性工具结果。报告总计始终从当前有效项的内部精度结果重算。 `[VERIFIED: .planning/phases/02-agent/02-CONTEXT.md]`

### Component Responsibilities

| Component | Owns | Must Not Own |
|---|---|---|
| Agent API | auth、所有权、HTTP/SSE 映射 | 营养规则、ORM 查询细节、Provider 原文 |
| Run Service/Supervisor | 幂等、lease、预算、调用账本、运行状态 | 模型推理、营养公式 |
| LangGraph nodes | 状态转换、工具编排、interrupt payload | Repository/ORM、未记录副作用 |
| Nutrition Service | 资格、受控份量、计算、校验 | 对话、HTTP、模型决策 |
| Provider adapter | DeepSeek 请求/错误归类/DTO 验证 | 目录查询、营养真值、业务终态 |
| SSE store/stream | 有序安全业务事件、重放 | 图状态真值、token/CoT |
| H5 | 输入、追问、快照展示、连接状态 | 权威状态、营养重算、授权决定 |

### Anti-Patterns to Avoid

- **把 `thread_id` 当凭证：** 它只是恢复游标；checkpoint 前先查 `(thread_id, user_id)`。 `[CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]`
- **在 interrupt 前裸调用 Provider/工具：** 节点重入会重复计费/写入；必须走 invocation ledger。 `[CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]`
- **SSE 直接 `graph.astream(..., stream_mode="values")`：** 会泄露完整 state/messages；只投影版本化业务事件。 `[CITED: https://docs.langchain.com/oss/python/langgraph/streaming]`
- **每次请求 `setup()` checkpointer：** schema 生命周期失控；用显式初始化和 lifespan。 `[CITED: https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-postgres/langgraph/checkpoint/postgres/aio.py]`
- **用展示舍入值累计：** 会制造总量差；内部 `Decimal` 累计后统一展示。 `[VERIFIED: .planning/phases/02-agent/02-CONTEXT.md]`
- **把无结果当异常重试：** 目录无结果是确定性业务分支，不是临时故障。 `[VERIFIED: .planning/phases/02-agent/02-CONTEXT.md]`

## State, Persistence and Public Contracts

### LangGraph State

推荐 `AgentState` 至少包含：`schema_version`、`user_id`、`thread_id`、`run_id`、`input_version`、受限消息摘要、`intent`、`meal_items`、`missing_fields`、`catalog_candidates`、`tool_results`、`validation_issues`、`dirty_item_ids`、调用/步骤/活动时长/费用计数、`next_action`、`report`、图/模型/提示词/工具/目录/规则版本和稳定 `status`。图片字段为兼容未来保留空列表，但 Phase 2 API 拒绝图片输入。 `[VERIFIED: .planning/phases/02-agent/02-AI-SPEC.md]`

State 不应保存 access token、Provider key、完整原始响应或思维链。用户原始餐食文本只在业务所需最短边界内处理；checkpoint/SSE/trace 优先存结构化最小数据。 `[VERIFIED: AGENTS.md]`

### Business Tables

| Table | Required columns / constraints | Purpose |
|---|---|---|
| `agent_threads` | `id`, `user_id`, `capability`, `status`, `active_input_version`, `snapshot_revision`, `latest_event_seq`, timestamps; index `(user_id,id)` | 权威所有权与线程快照头。 `[VERIFIED: .planning/phases/02-agent/02-AI-SPEC.md]` |
| `agent_runs` | `id`, `thread_id`, `input_version`, `request_hash`, status, version快照, counters, reserved/actual cost, `active_elapsed_ms`, failure code, lease owner/until, timestamps | 可恢复运行与 AGT-07 审计。 `[VERIFIED: .planning/REQUIREMENTS.md]` |
| `agent_invocations` | unique idempotency key, run/node/item/input/provider/tool/schema versions, request hash, `PREPARED/COMPLETED/AMBIGUOUS/FAILED`, attempt, usage/cost/latency, safe result reference | Provider/工具副作用去重和费用审计。 `[ASSUMED]` |
| `agent_events` | `(thread_id, seq)` unique, run, event type/version, JSONB safe payload, snapshot revision, timestamp | SSE replay；seq 在同事务锁定 thread row 后分配。 `[ASSUMED]` |
| `nutrition_catalog_versions/sources/foods/aliases/portions` | immutable version/source/provenance/license/qualification constraints | 受控目录与推导链。 `[VERIFIED: .planning/REQUIREMENTS.md]` |

同一客户端命令的幂等键为 `(user_id, thread_id, client_request_id)`，并绑定 canonical body hash；相同键相同 hash 返回既有 run，相同键不同 hash 返回 `409`. 节点调用键至少包含 `(run_id, node, item_id, input_version, provider_or_tool_version, schema_version, request_hash)`。 `[ASSUMED]`

### Public API

| Method | Endpoint | Contract |
|---|---|---|
| `POST` | `/api/v1/agent/threads` | 新餐创建新线程；返回 thread snapshot。 `[VERIFIED: .planning/phases/02-agent/02-CONTEXT.md]` |
| `POST` | `/api/v1/agent/threads/{id}/inputs` | 新描述、interrupt 回复或修正；`client_request_id` 必填，返回 `202` + run/snapshot reference。 `[ASSUMED]` |
| `POST` | `/api/v1/agent/threads/{id}/runs/{run_id}/retry` | 仅允许稳定可重试状态；创建显式新 attempt，不伪装自动重放。 `[VERIFIED: .planning/phases/02-agent/02-CONTEXT.md]` |
| `GET` | `/api/v1/agent/threads/{id}` | 权威完整快照，包含 `snapshot_revision/latest_event_seq`。 `[ASSUMED]` |
| `GET` | `/api/v1/agent/threads/{id}/events` | 认证 fetch SSE；支持 `Last-Event-ID`，只重放安全业务事件。 `[CITED: https://html.spec.whatwg.org/multipage/server-sent-events.html]` |

所有 endpoint 先用 access-token 用户做所有权校验；不存在与越权建议统一安全映射为 `404`，避免枚举线程。 `[ASSUMED]`

### SSE Event Contract

稳定事件类型建议为：`run.accepted.v1`、`meal.understood.v1`、`clarification.required.v1`、`catalog.searching.v1`、`nutrition.calculating.v1`、`nutrition.validating.v1`、`report.completed.v1`、`run.failed.v1`。每个事件 `id` 为单线程单调 `seq`，`data` 含 `event_version/thread_id/run_id/seq/snapshot_revision/safe_payload`；不要把内部节点名当公开事件类型。 `[ASSUMED]`

响应使用 `Content-Type: text/event-stream`、`Cache-Control: no-cache, no-transform`、`X-Accel-Buffering: no`；可每约 15 秒发送 comment heartbeat，重连采用有界指数退避加抖动。heartbeat/退避具体值属于部署参数，不是业务语义。 `[CITED: https://html.spec.whatwg.org/multipage/server-sent-events.html]` `[ASSUMED]`

重连算法固定为：获取快照 → 记录 `latest_event_seq` → 以该值续订 → 丢弃 `seq <= lastSeen` → 遇到 `seq > lastSeen + 1` 立即重取快照 → waiting/terminal 事件后再取快照。进度事件只改善反馈，不作为报告真值。 `[ASSUMED]`

## LangGraph and Checkpointer Details

- 使用 `graph.stream/astream(..., version="v2", subgraphs=True)` 仅在服务端适配层接收统一 `StreamPart(type, ns, data)`；公开层只输出白名单业务投影。 `[CITED: https://docs.langchain.com/oss/python/langgraph/streaming]`
- interrupt 返回应读取 v2 `GraphOutput.value` / `.interrupts`，恢复通过 `Command(resume=...)`；禁止捕获并吞掉 interrupt 异常。 `[CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]`
- 条件边显式覆盖 `ASK/CALCULATE/RECALCULATE/BLOCK/WARN/COMPLETE/LIMIT_REACHED`，业务计数器先于昂贵调用检查；`recursion_limit` 和 `GraphRecursionError` 只兜底编程错误。 `[CITED: https://docs.langchain.com/oss/python/langgraph/use-graph-api]`
- 默认 AI-SPEC 预算：12 graph steps、4 model calls、12 tool calls、45 秒 active runtime、`$0.02/run`、瞬时错误最多自动重试 1 次。等待用户回复的墙钟时间不计入 active runtime。 `[VERIFIED: .planning/phases/02-agent/02-AI-SPEC.md]`
- `AsyncPostgresSaver.from_conn_string()` 官方实现使用 autocommit、`dict_row` 和 `prepare_threshold=0` 的异步 psycopg 连接；MVP 可先用单 saver 连接，只有验证并发瓶颈后再引入 pool。 `[CITED: https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-postgres/langgraph/checkpoint/postgres/aio.py]`
- Checkpointer 测试必须每例使用唯一 `thread_id` 与 `checkpoint_ns`，并显式清理 checkpoint tables；SQLAlchemy transaction rollback 无法回滚 saver 的独立已提交连接。 `[VERIFIED: backend/AGENTS.md]` `[ASSUMED]`

## DeepSeek Provider Contract

Provider 接口应窄化为 `parse_meal(request) -> ParsedMealDTO` 与 `apply_correction(request) -> CorrectionDTO`。DTO 只描述项目、用户表达的份量文本/数值、缺失字段、候选查询词和修正目标；不包含权威营养值。Fake Provider 按 fixture 精确返回 DTO 或分类错误。 `[VERIFIED: .planning/phases/02-agent/02-AI-SPEC.md]`

当前 DeepSeek Responses API 仅支持 `deepseek-v4-flash`，并可通过 `text.format` 请求 JSON Schema structured output；模型默认 thinking 开启，而 thinking 模式下 temperature 不生效，所以解析请求要显式关闭 thinking、限制 `max_output_tokens=800`、设置 20 秒 provider timeout，并对响应再次做 Pydantic 校验。 `[CITED: https://api-docs.deepseek.com/api/create-response/]` `[CITED: https://api-docs.deepseek.com/guides/thinking_mode/]` `[VERIFIED: .planning/phases/02-agent/02-AI-SPEC.md]`

记录配置 alias、响应 `model`、`system_fingerprint`、Provider request ID、prompt/schema 版本和 token/cost；fingerprint 变化触发冻结评测。官方文档未提供可固定底层 revision 的接口，因此不能声称 alias 永远指向同一权重。 `[CITED: https://api-docs.deepseek.com/guides/responses_api/]`

错误分类必须在 adapter 完成：400/422 为永久请求错误，429/500/503 与网络/timeout 为瞬时错误；只有后者在总预算内自动重试一次。 `[CITED: https://api-docs.deepseek.com/quick_start/error_codes/]`

官方资料未发现 DeepSeek 请求幂等键保证。若进程在 Provider 已处理但本地未提交结果之间崩溃，ledger 必须标记 `PROVIDER_OUTCOME_UNKNOWN`，重连不得自动再计费；只允许用户显式重试。先预留该调用的最大费用，再发请求。这个边界意味着系统可保证“已记录完成的调用不重跑”，不能对未知外部结果承诺绝对 exactly-once。 `[CITED: https://api-docs.deepseek.com/api/create-response/]`

## Deterministic Nutrition Domain

### Lawful Seed Data

Phase 2 只采用 USDA FoodData Central 作为公开种子来源。官方说明 FDC 数据为 public domain/CC0、可自由重用，并请求注明 FoodData Central；API key 必须私密，默认限额为 1,000 请求/小时。运行时不调用 FDC API，而由离线 importer 固化来源 manifest、下载/选择记录和内容 hash。 `[CITED: https://fdc.nal.usda.gov/api-guide/]`

优先从 Foundation Foods 与 SR Legacy 选择具备明确 prepared state、四项营养和可解释份量的记录；FNDDS 可补充少量完全匹配的组合食物。Branded Foods 不适合作为通用“米饭/鸡蛋”默认值。当前下载页列出 Foundation 2026-04、SR Legacy 2018-04 final、FNDDS 2021–2023（2024-10 发布）等版本，manifest 必须记录所用具体 release。 `[CITED: https://fdc.nal.usda.gov/download-datasets/]`

建议首版 24–30 条经人工复核的记录，覆盖冻结样本需要的熟米饭/面类、肉蛋奶、常见蔬果和少量能精确对应 FDC 的组合菜；这个数量是 MVP 规划建议，不是数据标准。 `[ASSUMED]`

每条可计算记录必须保存：内部稳定 ID、FDC ID、dataset/type/release、source URL、license、每 100g edible portion 的 kcal/protein/fat/carbohydrate、prepared state、导入 hash、资格状态与目录版本。缺少任一四项营养时不得把 null 变成 0。 `[VERIFIED: .planning/REQUIREMENTS.md]` `[CITED: https://fdc.nal.usda.gov/Foundation_Foods_Documentation/]`

“cup”不能自动等于“一碗”。只有来源 portion 与用户词义完全对应，或项目以可审计测量流程建立自有受控份量时才能换算；自有换算需记录器具容量/测量方法、复核人和版本，否则继续追问克数。 `[ASSUMED]`

### Calculation

```text
nutrient_amount = nutrient_per_100g × grams / 100
meal_total = Σ current_included_item.internal_amount
```

输入和目录数值进入 `Decimal`，全流程保留内部精度，只在 API 展示 DTO 序列化时将 kcal 四舍五入为整数、P/F/C 为 1 位小数。每项和整餐必须带 `catalog_version`、`calculation_rule_version` 和推导链。 `[VERIFIED: .planning/phases/02-agent/02-CONTEXT.md]`

### Qualification and Validation

| Check | Severity / action | Rule |
|---|---|---|
| alias 非唯一或只有相似/模型猜测 | `ASK` | 最多 3 个 qualified candidates，禁止 top-1 自动选。 `[VERIFIED: .planning/phases/02-agent/02-CONTEXT.md]` |
| 没有克数且无受控 portion | `ASK` | 集中进一次 clarification。 `[VERIFIED: .planning/phases/02-agent/02-CONTEXT.md]` |
| food/nutrient/grams 为负 | `BLOCK` | 不生成最终报告。 `[VERIFIED: .planning/REQUIREMENTS.md]` |
| `grams <= 0` 或 `grams > 2000` | `ASK` 或 `BLOCK` | AI-SPEC 锁定的单项份量边界。 `[VERIFIED: .planning/phases/02-agent/02-AI-SPEC.md]` |
| macro >100g/100g 或 energy >900 kcal/100g | `BLOCK` pending domain review | 物理上界/异常密度建议，执行前需营养专家确认。 `[ASSUMED]` |
| item/meal total 与内部重算不一致 | `RECALCULATE` 一次，仍错则 `BLOCK` | 总量只能来自有效项内部结果。 `[VERIFIED: .planning/phases/02-agent/02-CONTEXT.md]` |
| Atwater 推导与来源 energy 不同 | `WARN`，不得默认 block | 来源能量可能使用特定系数、膳食纤维或酒精，阈值需领域复核。 `[ASSUMED]` |
| 目录外项目 | `ASK/EXCLUDE` | 已知项可形成 partial report，必须列出未计入项。 `[VERIFIED: .planning/phases/02-agent/02-CONTEXT.md]` |

校验结果 DTO 必须包含 `rule_id/rule_version/severity/action/item_id/safe_message`。条件边读取 `action`，而不是让模型重新解释错误。 `[VERIFIED: .planning/phases/02-agent/02-AI-SPEC.md]`

## Frontend Integration

`useQuery(['agent-thread', userId, threadId])` 保存权威快照；创建线程、提交输入、回复和修正使用 mutation。无结束时间的 SSE 不放进 query function，而由 `useAgentEventStream` effect 管理；业务事件只更新短暂进度或 `invalidateQueries`/不可变 `setQueryData`，报告最终以快照为准。 `[CITED: https://tanstack.com/query/latest/docs/reference/QueryClient]` `[CITED: https://tanstack.com/query/latest/docs/framework/react/guides/updates-from-mutation-responses]`

流 hook 必须使用现有认证 request 能力发起 `fetch`，在 401 时完成一次 refresh/replay；不能把 access token 放 query string，也不能扩大 refresh cookie path。组件卸载可关闭本次流，但不得取消服务器 run。 `[VERIFIED: frontend/src/auth/AuthProvider.tsx]` `[VERIFIED: AGENTS.md]`

`/app/analyze` 替换诚实占位页，并在能力完成后把 `/app` 默认入口改为 `/app/analyze`。页面状态至少覆盖 idle/running/waiting/reconnecting/partial/completed/retryable-failed/terminal-failed；对部分结果明确展示未计入项。 `[VERIFIED: .planning/phases/01.1-h5-ui/01.1-CONTEXT.md]`

Phase 1.1 的“总热量区间/置信度”视觉预留不能迫使 Phase 2 伪造区间或置信度：D-10/D-11 是更晚且更具体的锁定决策，本阶段展示确定性点值与来源/误差说明；NUT-06 的置信度仍属 Phase 3。 `[VERIFIED: .planning/phases/02-agent/02-CONTEXT.md]` `[VERIFIED: .planning/REQUIREMENTS.md]`

## Vertical MVP Slicing Guidance

| Slice | End-to-end deliverable | Gate |
|---|---|---|
| A — 克数直算 | 登录用户输入完整克数餐食 → Fake Provider → 受控目录 → 计算/校验 → SSE → H5 报告；同时落 thread/run/event 审计。 | 真实 PG、公开 API、组件测试和浏览器成功路径。 `[VERIFIED: .planning/phases/02-agent/02-CONTEXT.md]` |
| B — 追问与恢复 | 多项集中补缺、最多 3 个候选、`interrupt`、同 thread resume；关闭并重建 saver 后仍能恢复。 | Fake Provider 状态图 + 真实 checkpointer 重启测试。 `[CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]` |
| C — 修正与断线 | 局部 dirty item 重算、目录外 partial、命令/调用幂等、supervisor lease、快照+事件 gap/reconnect。 | 重放零重复调用/费用、跨用户 404、断流浏览器验收。 `[ASSUMED]` |
| D — 实际 Provider 与硬化 | DeepSeek adapter、分类重试、全部预算终态、24 条冻结评测、Phoenix/Promptfoo、安全 trace、中文教学文档。 | 无真实模型 PR 测试；付费 smoke 手工开关；所有 critical eval 100%。 `[VERIFIED: .planning/phases/02-agent/02-AI-SPEC.md]` |

每个切片都应能从页面走到真实公开 API 和 PostgreSQL，不能把数据库、图、API、前端拆成互不验收的水平波次。 `[VERIFIED: user task MVP mode]`

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| 图 checkpoint | 自定义 JSON state 表 | `langgraph-checkpoint-postgres` | 官方 saver 已处理 checkpoint/version/write 语义。 `[CITED: https://pypi.org/project/langgraph-checkpoint-postgres/]` |
| SSE 帧解析 | `split('\n\n')` | `eventsource-parser` | UTF-8 分块、多行 data、id/retry 和缓冲边界容易写错。 `[CITED: https://html.spec.whatwg.org/multipage/server-sent-events.html]` `[ASSUMED]` |
| 营养真值 | 模型估算或 prompt 公式 | 版本化 FDC seed + deterministic service | 可追溯、可复算且模型不能覆盖。 `[CITED: https://fdc.nal.usda.gov/api-guide/]` |
| 份量猜测 | “一碗=固定克数”全局表 | 食物+prepared-state 绑定的受控 portion | 相同容器/食物密度差异使全局换算不可审计。 `[ASSUMED]` |
| Provider schema | 正则抽 JSON | DeepSeek JSON Schema + Pydantic DTO | Provider 约束与本地运行时校验必须双层存在。 `[CITED: https://api-docs.deepseek.com/api/create-response/]` |
| 恰好一次副作用 | 仅依赖 checkpoint | business invocation ledger + unique keys | checkpoint 不覆盖外部调用结果提交窗口。 `[CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]` |
| 密钥/身份 | SSE query token | 现有 Bearer refresh flow + authenticated fetch | query token 会进入 URL/日志；EventSource 无 header。 `[VERIFIED: frontend/AGENTS.md]` |

**Key insight:** LangGraph 解决“从哪个状态继续”，不自动解决“谁能继续、外部调用是否已收费、客户端看过哪些事件”。三者分别由所有权表、invocation ledger 和 event log 解决。 `[VERIFIED: .planning/phases/02-agent/02-AI-SPEC.md]`

## Common Pitfalls

### Pitfall 1: 恢复时重复执行 interrupt 前代码

**What goes wrong:** 同一模型/工具调用再次发生，产生重复费用或重复事件。  
**Why it happens:** LangGraph resume 会从含 interrupt 的节点开头重跑。  
**How to avoid:** 副作用拆到前置节点或使用 invocation 唯一键；interrupt 节点只组装 payload。  
**Warning signs:** 同一 `(run,node,item,input_version)` 出现多个 completed invocation。 `[CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]`

### Pitfall 2: SSE 连接成为运行生命周期

**What goes wrong:** 页面刷新取消图，重连又启动新图。  
**Why it happens:** 直接在 `StreamingResponse` generator 中执行 `graph.astream()`。  
**How to avoid:** POST 命令创建 run，supervisor 独立执行，SSE 只读 event log。  
**Warning signs:** 客户端断开后 run 变 cancelled 或 Provider call 数增加。 `[ASSUMED]`

### Pitfall 3: Checkpointer 测试污染

**What goes wrong:** 用例在本机通过、并行/重跑失败，或读到前例 checkpoint。  
**Why it happens:** saver 使用独立提交连接，不受业务测试 transaction rollback 控制。  
**How to avoid:** 每例唯一 thread/namespace、真实 test PostgreSQL、显式 teardown 和进程重开测试。  
**Warning signs:** 测试依赖执行顺序或出现幽灵 interrupt。 `[ASSUMED]`

### Pitfall 4: DeepSeek 旧模型名与 thinking 默认值

**What goes wrong:** `deepseek-chat` 请求失败，或结构化解析变慢/不可控。  
**Why it happens:** 旧 alias 于 2026-07-24 退役；当前模型默认 thinking。  
**How to avoid:** 配置 `deepseek-v4-flash`，显式关闭 thinking，响应 Pydantic 校验。  
**Warning signs:** 404/422、输出 token 激增、temperature 调整无效。 `[CITED: https://api-docs.deepseek.com/updates]` `[CITED: https://api-docs.deepseek.com/guides/thinking_mode/]`

### Pitfall 5: “真实数据”仍不可计算

**What goes wrong:** 有来源记录，却缺 prepared state/份量/四项营养，或 null 被当成 0。  
**Why it happens:** 把“存在 FDC ID”误当 NUT-02 qualification。  
**How to avoid:** importer 建立明确资格门禁，只有 qualified version 可被工具返回。  
**Warning signs:** 报告出现 0g macro 但来源实际 missing。 `[CITED: https://fdc.nal.usda.gov/Foundation_Foods_Documentation/]`

### Pitfall 6: 模型覆盖确定性校验

**What goes wrong:** prompt 说“看起来合理”后硬错误仍生成报告。  
**Why it happens:** 把 validation 结果再交给模型自由解释。  
**How to avoid:** 条件边直接读取 action enum，报告 builder 拒绝 BLOCK。  
**Warning signs:** `BLOCK` issue 与 `COMPLETED` 同时存在。 `[VERIFIED: .planning/phases/02-agent/02-CONTEXT.md]`

### Pitfall 7: 活动超时把等待用户算进去

**What goes wrong:** 用户几分钟后回复，线程立即 TIME_LIMIT。  
**Why it happens:** 用 `created_at` 到当前时间作为预算。  
**How to avoid:** 每运行片段用注入 monotonic clock 累加 `active_elapsed_ms`，interrupt 等待不累计。  
**Warning signs:** waiting run 的耗时持续增长。 `[VERIFIED: .planning/phases/02-agent/02-AI-SPEC.md]`

## Testing Architecture and Failure Budgets

`.planning/config.json` 明确设置 `workflow.nyquist_validation=false`，因此不输出标准 `Validation Architecture` 章节；但 QLT-02 和 AI-SPEC 仍要求本阶段有完整状态图与失败预算测试。 `[VERIFIED: .planning/config.json]`

| Layer | Test | Data / double | Fast command target |
|---|---|---|---|
| Nutrition Service | qualification、portion、Decimal calculation、validation action | fake repository + frozen records | `pytest backend/tests/unit/nutrition -q` `[VERIFIED: backend/AGENTS.md]` |
| Repository/importer | source/version/alias uniqueness/qualification/migrations | real test PostgreSQL | `pytest backend/tests/integration/nutrition -q` `[VERIFIED: backend/AGENTS.md]` |
| Graph state machine | route、集中追问、候选、修正、终态 | Fake Provider + fake tools + fake clock | `pytest backend/tests/unit/agent -q` `[VERIFIED: AGENTS.md]` |
| Checkpointer | interrupt/resume、process reopen、namespace isolation | real PostgreSQL saver | `pytest backend/tests/integration/agent/test_checkpoint.py -q` `[ASSUMED]` |
| API/SSE | auth/ownership/idempotency/snapshot/replay/gap/error envelope | HTTPX + real DB, fake provider | `pytest backend/tests/api/test_agent.py -q` `[VERIFIED: backend/AGENTS.md]` |
| H5 | composer、clarification、partial/report、retry/reconnect | Vitest + Testing Library + MSW | `npm test -- --run tests/agent` `[VERIFIED: frontend/AGENTS.md]` |
| Cross-stack | login → analyze → interrupt/resume → report；断流恢复 | Playwright + real public API + fake provider | project Playwright command `[VERIFIED: frontend/AGENTS.md]` |

冻结集按 AI-SPEC 建立 24 例：5 happy、5 missing/ambiguity、4 corrections、5 persistence/isolation、3 validation/budget、2 adversarial。Critical 维度必须 100%，High 至少 95%；主观 judge 平均至少 4/5 且 Spearman ≥0.70。 `[VERIFIED: .planning/phases/02-agent/02-AI-SPEC.md]`

预算边界测试必须使用注入 clock/token/cost/provider，不用 sleep：恰好达到限制允许完成，下一次调用前进入稳定 `LIMIT_REACHED`；终态后 invocation/event 数不再增加；瞬时错误恰好重试一次，400/422/目录无结果/校验失败零重试；等待用户时间不累计；`GraphRecursionError` 被映射为稳定内部失败且不泄露堆栈。 `[VERIFIED: .planning/phases/02-agent/02-AI-SPEC.md]` `[CITED: https://docs.langchain.com/oss/python/langgraph/use-graph-api]`

真实 checkpointer 隔离固定做法：suite/session 只对 test database 执行一次 `setup()`；每例 UUID thread + namespace；teardown 按测试标识删除 `checkpoint_writes/checkpoint_blobs/checkpoints`；至少一例关闭 saver/graph、重新建立进程资源后再 resume。禁止 SQLite fallback。 `[ASSUMED]` `[VERIFIED: backend/AGENTS.md]`

浏览器验收至少覆盖：完整克数直算；集中追问后恢复；SSE 断开刷新后快照恢复；目录外 partial；预算/临时失败可操作错误；跨用户 thread 不可见。必须走登录页面和公开 API，不得直接写 DB 或伪造 token。 `[VERIFIED: AGENTS.md]`

## Code Examples

### interrupt/resume 的安全形状

```python
# Source: https://docs.langchain.com/oss/python/langgraph/interrupts
from langgraph.types import Command, interrupt

def request_clarification(state: AgentState) -> dict:
    answer = interrupt({
        "event_version": 1,
        "kind": "meal_clarification",
        "items": build_safe_clarification_items(state),
    })
    return {"clarification_answer": ClarificationAnswer.model_validate(answer)}

# API/service: ownership already verified, same thread_id
config = {"configurable": {"thread_id": thread_id}}
result = await graph.ainvoke(Command(resume=validated_answer), config=config)
```

interrupt 前的 Provider/工具结果必须已经通过唯一 invocation key 持久化；上例节点自身不得产生不可幂等副作用。 `[CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]`

### DeepSeek Responses JSON Schema request

```python
# Source: https://api-docs.deepseek.com/api/create-response/
payload = {
    "model": settings.deepseek_model,  # deepseek-v4-flash
    "input": provider_messages,
    "thinking": {"type": "disabled"},
    "max_output_tokens": 800,
    "text": {
        "format": {
            "type": "json_schema",
            "name": "parsed_meal",
            "schema": ParsedMealDTO.model_json_schema(),
            "strict": True,
        }
    },
}
response = await client.post("/responses", json=payload, timeout=20.0)
parsed = ParsedMealDTO.model_validate_json(extract_output_text(response.json()))
```

HTTP 状态必须先映射为稳定 Provider error category，原始 body 不进入用户响应或普通日志。 `[CITED: https://api-docs.deepseek.com/quick_start/error_codes/]`

### SSE 编码与重放

```python
# Source: https://html.spec.whatwg.org/multipage/server-sent-events.html
def encode_event(event: AgentEvent) -> bytes:
    safe_json = AgentEventPayload.model_validate(event.payload).model_dump_json()
    return (
        f"id: {event.seq}\n"
        f"event: {event.public_type}\n"
        f"data: {safe_json}\n\n"
    ).encode("utf-8")
```

只从持久化 `agent_events` 读取；不要把任意对象 `json.dumps()` 后直接发送。 `[ASSUMED]`

### Decimal 计算

```python
from decimal import Decimal

HUNDRED = Decimal("100")

def scale(per_100g: Decimal, grams: Decimal) -> Decimal:
    if grams <= 0:
        raise InvalidPortionError("PORTION_OUT_OF_RANGE")
    return per_100g * grams / HUNDRED
```

舍入只发生在 response presenter，不发生在 `scale()` 或 meal aggregation。 `[VERIFIED: .planning/phases/02-agent/02-CONTEXT.md]`

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| DeepSeek `deepseek-chat` / `deepseek-reasoner` | `deepseek-v4-flash` / `deepseek-v4-pro`；Responses 仅 flash | 2026-07-24 retirement | AI-SPEC 中旧模型名不可直接实施，Provider 配置需更新。 `[CITED: https://api-docs.deepseek.com/updates]` |
| LangGraph v1 stream shape | `version="v2"` unified `StreamPart` | LangGraph current docs | 服务端适配统一，公开 SSE 仍是自有业务协议。 `[CITED: https://docs.langchain.com/oss/python/langgraph/streaming]` |
| Phoenix 手工 OTel 配置 | `arize-phoenix-otel` helper | current Phoenix docs | eval 环境更少样板，但仍需字段白名单。 `[CITED: https://www.arize.com/docs/phoenix/tracing/how-to-tracing/setup-tracing/setup-using-phoenix-otel]` |

**Deprecated/outdated:**

- `deepseek-chat`、`deepseek-reasoner`：官方已退役，禁止作为新实现默认值。 `[CITED: https://api-docs.deepseek.com/updates]`
- 直接向浏览器暴露 LangGraph `values/debug/messages` stream：不符合 D-14 的最小业务事件合同。 `[CITED: https://docs.langchain.com/oss/python/langgraph/streaming]`

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | 所有新增包版本因 slopcheck/registry DNS 不可用而需人工合法性复核。 | Package Legitimacy Audit | 安装供应链风险或版本不存在。 |
| A2 | `eventsource-parser` 3.1.0 是本项目优先 parser，Phoenix/Promptfoo 使用列出的稳定版本。 | Standard Stack | API/Node 兼容或供应链状态可能变化。 |
| A3 | 采用进程内 supervisor + PostgreSQL lease/event log，无外部队列。 | Architecture Patterns | 多 worker 抢占/崩溃恢复若设计不严会重复运行。 |
| A4 | 推荐业务表、幂等键、公开 endpoint 和 SSE event 名称/重连算法。 | State, Persistence and Public Contracts | 契约若晚改会影响 migration、前端和测试。 |
| A5 | MVP 目录推荐 24–30 条，并建议自有 household portion 的测量审计流程。 | Deterministic Nutrition Domain | 覆盖不足或换算可信度不够。 |
| A6 | density/Atwater 校验阈值及严重度需营养领域复核。 | Qualification and Validation | 误拦正常记录或放过异常数据。 |
| A7 | heartbeat 约 15 秒、退避和连接参数由部署配置决定。 | SSE Event Contract | 代理超时/移动网络体验可能不适配。 |
| A8 | checkpoint 表按测试标识显式清理的具体 SQL/fixture 实现。 | Testing Architecture | 上游表结构变化可能要求调整清理器。 |
| A9 | 越权/不存在统一映射 404。 | Public API | 产品安全错误规范可能选择其他稳定状态。 |

## Open Questions (RESOLVED)

1. **RESOLVED — 运行、事件与 Checkpoint 保留期：** Checkpoint 与 SSE 事件在最后活动 7 天后清理；不含餐食原文的最小运行审计元数据保留 30 天；用户主动删除 Agent 会话后 24 小时内级联清理。生产配置必须显式设置并 fail closed。 `[USER DECISION: .planning/phases/02-agent/02-CONTEXT.md D-18]`
2. **RESOLVED — Provider 结果未知时的费用与恢复策略：** 使用稳定状态 `PROVIDER_OUTCOME_UNKNOWN`，说明结果与费用状态无法确认；自动恢复、SSE 重连和 Supervisor 不得重新发起调用。只有用户显式选择重试后才能创建新的调用尝试，并仍受单次运行费用硬上限约束。 `[CITED: https://api-docs.deepseek.com/api/create-response/]`
3. **RESOLVED — 受控中文家庭份量复核：** 没有注册营养师或食物成分数据管理员按标准器具签署前，只允许发布 FDC 中食物与 portion 描述能精确对应且保留来源/版本的换算；其他“一碗/一份”输入必须追问克数或可验证大小。不得为了 demo 编造换算。 `[VERIFIED: .planning/phases/02-agent/02-CONTEXT.md D-01, D-07, D-08]`

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|---|---|---:|---|---|
| project `.venv` Python | backend/tests | ✓ | 3.11.16 | — `[VERIFIED: local command 2026-08-28]` |
| system `python3` | ad-hoc scripts | ✓ but wrong | 3.9.6 | 必须使用 `.venv` `[VERIFIED: local command 2026-08-28]` |
| Node.js / npm | frontend/eval | ✓ | 22.23.2 / 10.9.8 | — `[VERIFIED: local command 2026-08-28]` |
| Docker / Compose | real PostgreSQL tests | ✓ | 29.4.0 / v5.1.2 | — `[VERIFIED: local command 2026-08-28]` |
| test PostgreSQL service | integration tests | ✗ currently stopped | compose port 55432 | `docker compose up` before tests `[VERIFIED: docker compose ps 2026-08-28]` |
| `psql` | manual DB inspection | ✗ | — | use container/SQLAlchemy `[VERIFIED: local command 2026-08-28]` |
| `uv` | package workflow | ✗ | — | existing pip/venv `[VERIFIED: local command 2026-08-28]` |
| PyPI/npm network | package legitimacy | ✗ during research | DNS failure | human verify in network-enabled execution `[VERIFIED: local registry commands 2026-08-28]` |

**Missing dependencies with no fallback:** network-enabled package legitimacy/install remains an execution gate.  
**Missing dependencies with fallback:** `psql` and `uv` are not required；测试 PostgreSQL 可由现有 Compose 启动。

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | yes | 复用现有 access/refresh 体系，不发 SSE query token。 `[VERIFIED: AGENTS.md]` |
| V3 Session Management | yes | 401 时仅一次受控 refresh/replay，退出关闭流。 `[VERIFIED: frontend/src/auth/AuthProvider.tsx]` |
| V4 Access Control | yes | 每次 thread/snapshot/events/resume/checkpoint 前 `(user_id,thread_id)` 所有权校验。 `[VERIFIED: .planning/phases/02-agent/02-AI-SPEC.md]` |
| V5 Input Validation | yes | Pydantic/Zod、Provider DTO、tool args、state 和 SSE payload 白名单。 `[VERIFIED: AGENTS.md]` |
| V6 Cryptography | yes | 只用现有认证/secret 管理，不自研 token/加密。 `[VERIFIED: AGENTS.md]` |
| V7 Error/Logging | yes | 稳定错误码、审计版本/成本/耗时，不记录 Provider 原文/堆栈。 `[VERIFIED: AGENTS.md]` |
| V8 Data Protection | yes | 最小 checkpoint/event/trace，明确保留和删除。 `[VERIFIED: .planning/phases/02-agent/02-AI-SPEC.md]` |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---|---|---|
| 猜测 `thread_id` 越权恢复/BOLA | Spoofing / Information Disclosure | 业务所有权检查先于 checkpointer；跨用户测试。 `[VERIFIED: .planning/phases/02-agent/02-AI-SPEC.md]` |
| 重放命令导致重复 Provider 费用 | Tampering / Repudiation | client request + invocation 双层幂等键、hash mismatch 409、审计状态。 `[ASSUMED]` |
| prompt injection 要求伪造营养/暴露系统提示 | Tampering / Information Disclosure | 模型无 DB/营养真值权限；严格 DTO；工具和事件 allowlist。 `[VERIFIED: AGENTS.md]` |
| SSE 泄露 state/messages/CoT | Information Disclosure | 只发送 safe event schema；禁用 raw LangGraph stream 转发。 `[VERIFIED: .planning/phases/02-agent/02-CONTEXT.md]` |
| 超长输入/无限候选/事件洪泛 | Denial of Service | 文本/项目/payload 上限，最多 3 候选，步骤/调用/时间/费用预算。 `[VERIFIED: .planning/phases/02-agent/02-AI-SPEC.md]` |
| 恶意 Markdown/XSS | Tampering | React 文本渲染，不使用 `dangerouslySetInnerHTML`，URL 不由模型直出。 `[VERIFIED: frontend/AGENTS.md]` |
| telemetry 关联用户或原始餐食 | Information Disclosure | 默认不采集 raw input/prompt/checkpoint；如需关联仅用 secret-scoped HMAC pseudonym。 `[ASSUMED]` |

## Sources

### Primary (HIGH confidence)

- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) — interrupt/resume、thread、节点重入和 v2 输出。
- [LangGraph streaming](https://docs.langchain.com/oss/python/langgraph/streaming) — v2 stream、subgraph namespace 和 stream modes。
- [LangGraph subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs) — per-invocation 持久化继承。
- [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/use-graph-api) — recursion limit 与错误。
- [AsyncPostgresSaver source](https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-postgres/langgraph/checkpoint/postgres/aio.py) — setup、连接生命周期和 psycopg 配置。
- [LangGraph PyPI](https://pypi.org/project/langgraph/)；[checkpoint PyPI](https://pypi.org/project/langgraph-checkpoint-postgres/) — 当前版本与发布时间。
- [DeepSeek updates](https://api-docs.deepseek.com/updates)；[Responses API](https://api-docs.deepseek.com/api/create-response/)；[thinking](https://api-docs.deepseek.com/guides/thinking_mode/)；[errors](https://api-docs.deepseek.com/quick_start/error_codes/) — 当前模型/API/结构化输出/错误语义。
- [FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/)；[lifespan](https://fastapi.tiangolo.com/advanced/events/) — 流响应和共享资源生命周期。
- [WHATWG SSE](https://html.spec.whatwg.org/multipage/server-sent-events.html)；[MDN SSE](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events) — 帧、重连和浏览器限制。
- [USDA FoodData Central API Guide](https://fdc.nal.usda.gov/api-guide/)；[downloads](https://fdc.nal.usda.gov/download-datasets/)；[Foundation docs](https://fdc.nal.usda.gov/Foundation_Foods_Documentation/) — 授权、数据版本与份量元数据。
- [TanStack QueryClient](https://tanstack.com/query/latest/docs/reference/QueryClient) — cache/invalidation/update。
- 项目文件：`AGENTS.md`、`backend/AGENTS.md`、`frontend/AGENTS.md`、`02-CONTEXT.md`、`02-AI-SPEC.md`、`REQUIREMENTS.md`、`ROADMAP.md`、`STATE.md`。

### Secondary (MEDIUM confidence)

- [eventsource-parser official repository](https://github.com/rexxars/eventsource-parser) — parser API 与版本说明；执行前仍受 package gate。
- [Phoenix OTEL setup](https://www.arize.com/docs/phoenix/tracing/how-to-tracing/setup-tracing/setup-using-phoenix-otel) — 当前 tracing helper。
- [Open Food Facts reuse conditions](https://support.openfoodfacts.org/help/en-gb/12-api-data-reuse/94-are-there-conditions-to-use-the-api) — ODbL reuse 条件。

### Tertiary (LOW confidence)

- 无未交叉核验的 WebSearch 结论；所有 `[ASSUMED]` 项集中在架构参数、领域阈值和包门禁。

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — 框架锁定，版本和 API 由官方文档/registry 页面核验；安装合法性仍需人工门禁。
- Architecture: HIGH — LangGraph/FastAPI 官方生命周期与项目既有分层共同约束；supervisor/ledger 细节为明确标注的建议。
- Nutrition domain: MEDIUM-HIGH — 来源和授权 HIGH；目录规模、家庭份量和异常阈值需领域复核。
- Pitfalls: HIGH — interrupt 重入、SSE、Provider 变更均来自官方行为与现有认证实现。
- Testing: HIGH — 项目测试合同与 AI-SPEC 明确；checkpointer 清理实现需随实际表结构确认。

**Research date:** 2026-08-28  
**Valid until:** 2026-09-04（DeepSeek、LangGraph 与 npm/PyPI 版本变化快，7 天后重验）
