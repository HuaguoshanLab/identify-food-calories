# Phase 2: 可追问的 Agent 核心 - Context

**Gathered:** 2026-08-28
**Status:** Ready for planning

<domain>
## Phase Boundary

本阶段把现有 `/app/analyze` 诚实占位页替换为登录用户可实际使用的文字餐食分析入口，并建立后端 LangGraph 主图、餐食分析子图、可替换文本模型 Provider、PostgreSQL Checkpointer、确定性营养目录/计算/校验工具、SSE 业务事件以及有界失败恢复。用户可以用自然语言描述一餐；系统在信息不足或目录匹配不唯一时中断追问，使用同一 `thread_id` 恢复，并输出可追溯的逐项营养结果与整餐汇总。

本阶段只处理文字输入。图片上传与 Qwen-VL 属于 Phase 3；餐食确认保存与长期记忆属于 Phase 4；真实饮食规划子图属于 Phase 5；营养目录后台维护属于 Phase 6。Phase 2 可以预留后续路由和数据边界，但不得伪造尚未交付的能力。

</domain>

<decisions>
## Implementation Decisions

### 文字餐食解析与追问节奏

- **D-01:** 用户可使用克数或营养目录中的受控常见份量描述食物，例如“一碗”“半个”“一份”。只有目录存在明确、版本化的换算关系时才能直接换算；否则追问克数、大小或其他必要信息。
- **D-02:** Agent 先展示已理解的整餐项目清单，再在单轮中集中询问所有阻塞计算的缺失字段，不为每个字段或每道菜机械地产生一轮对话。
- **D-03:** 用户可用自然语言定向修正，例如“米饭改成半碗”或“第二项不是鸡肉，是鱼”。系统保留其他已确认信息，只让受影响项目重新查询、计算和校验。
- **D-04:** 当输入完整、目录匹配唯一且没有阻塞校验问题时，Agent 直接调用确定性工具计算，不增加固定的“计算前确认”步骤。

### 模糊菜名与目录外食物

- **D-05:** 目录查询出现歧义时，最多展示 3 个具备计算资格的候选，并提供能帮助区分的做法、常见份量或来源信息；图中断并等待用户选择，禁止自动采用相似度最高项。
- **D-06:** 只有目录明确登记且唯一的受控别名，以及大小写、空白等无语义规范化，可以自动映射到标准食物。拼写相似、方言猜测和模型推断只能形成候选，不能自动确定。
- **D-07:** Phase 2 建立小型、真实、版本化且可追溯的 MVP 营养种子目录，优先覆盖演示和冻结测试需要的常见主食、肉蛋奶、蔬果及少量常见菜；不把本阶段扩张为大规模中国菜数据库建设。
- **D-08:** 用户不需要预先提供营养数据。研究阶段负责确认适合的合法数据源、授权和引用方式；每条公开可计算记录必须满足 NUT-01/NUT-02 的来源、授权、版本和资格约束。
- **D-09:** 目录外食物不允许模型估算营养值。用户可以改名、选择有效候选或排除该项；其他已知项目仍可计算，但逐项结果和整餐汇总必须明确列出未计入项目，不能把部分结果伪装成完整整餐结果。

### 文本分析结果与会话收口

- **D-10:** 最终结果同时展示逐项明细和整餐汇总。每项至少包含标准菜名、输入份量/换算克数、热量、蛋白质、脂肪和碳水；汇总区同时展示未计入项目与非阻塞校验提示。
- **D-11:** 展示层把热量舍入为整数 kcal，把蛋白质、脂肪和碳水展示为 1 位小数；确定性计算和校验内部保留足够精度，禁止用展示舍入值反向参与累计计算。
- **D-12:** 校验异常按严重度确定性分流：可修正异常先重新核算；缺失信息触发追问；负数、严重营养密度异常、总量不一致等硬错误阻止最终报告；非阻塞误差提示可以随可信结果展示。模型不能覆盖工具校验结论。
- **D-13:** 报告生成后本轮运行标记为完成，不增加没有保存语义的确认步骤。用户仍可在同一线程中定向修正并触发受影响部分重算；分析另一餐必须创建新线程。确认并保存餐食留到 Phase 4。

### SSE、失败反馈与断线恢复

- **D-14:** SSE 发送稳定、版本化的业务阶段事件，例如理解输入、等待补充、查询目录、计算营养、校验结果、完成和失败；事件只携带安全摘要与结构化数据，不逐 Token 暴露模型中间文本，更不能输出思维链。
- **D-15:** 页面刷新、短暂断网或 SSE 连接断开后，前端使用同一 `thread_id` 自动重新获取权威线程快照并继续接收事件。已完成节点、模型调用和工具调用不得重跑或重复计费。
- **D-16:** 只有超时、限流和临时网络错误等瞬时故障可以在总体循环、调用、时间和费用预算内自动重试一次。参数错误、目录无结果和确定性校验失败不得盲目重试；自动重试仍失败时保留 Checkpoint，并提供用户触发的重试入口。
- **D-17:** 达到最大循环、最大工具调用、超时或费用上限时，运行进入明确、可测试的终止状态。前端显示安全且稳定的失败类别，如需要更多信息、目录无可用数据、服务暂时不可用或达到运行上限，并按情况提供补充信息或重试入口；禁止返回堆栈、Provider 原文或内部节点细节。

### 数据保留

- **D-18:** 采用分层保留：Checkpoint 与 SSE 事件在最后活动 7 天后清理；不含餐食原文的最小运行审计元数据保留 30 天；用户主动删除 Agent 会话后 24 小时内完成 Checkpoint、事件与运行记录的级联清理。生产配置必须显式承载这些期限，不能使用无限保留或静默回退。

### the agent's Discretion

- 在不削弱 D-07/D-08 的前提下，由研究与规划确定 MVP 种子目录的具体条目数量、合法数据源、导入格式和版本标识。
- 由研究与规划确定 LangGraph State 字段、节点拆分、条件边、事件 Schema、幂等键、Checkpoint 表结构和具体预算数值，但必须实现上述用户行为及 AGT-02/AGT-05/AGT-07 的可追溯约束。
- 在稳定事件类别和错误语义不变的前提下，可以调整用户可见阶段文案、候选说明文案、重连退避和非阻塞提示样式。
- 可以决定 Phase 2 冻结测试样本的具体组成，但必须覆盖多菜输入、常见份量、集中追问、模糊候选、目录外部分结果、定向修正、interrupt/resume、断线恢复、幂等重放和全部终止条件。

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product, requirements, and phase boundary

- `.planning/PROJECT.md` — 产品定位、模型分工、一个主图/两个子图、确定性工具真相边界、健康安全限制和教学契约。
- `.planning/REQUIREMENTS.md` — Phase 2 的 AGT-01..07、NUT-01..05、ARC-05..06 与 QLT-02 正式要求及后续阶段边界。
- `.planning/ROADMAP.md` — Phase 2 目标、依赖、成功条件以及与 Phase 3..7 的能力切分。
- `.planning/STATE.md` — 当前里程碑位置、已完成基础设施和跨阶段决策。
- `AGENTS.md` — 仓库级架构、安全、目录文档、测试、教学与真实浏览器验收规则。

### Prior-phase contracts

- `.planning/phases/01-engineering-auth-foundation/01-CONTEXT.md` — 认证、用户身份、Provider 分离、模块化单体和 Agent 预留边界。
- `.planning/phases/01.1-h5-ui/01.1-CONTEXT.md` — `/app/analyze` 占位入口、Phase 2 切换默认入口、真实 API 接线和不得伪造后端能力的锁定决策。
- `docs/ui/h5-foundation.md` — 移动端 H5 页面壳、四 Tab、语义 token、可访问性和浏览器验收合同。

### Existing implementation constraints

- `backend/AGENTS.md` — API → Service → Repository → Model 依赖、LangGraph State/Provider DTO 分离、真实 PostgreSQL 测试和 Alembic 要求。
- `backend/README.md` — 后端启动、测试和模块索引约束；Phase 2 新模块加入后必须同步更新。
- `frontend/AGENTS.md` — H5 路由、TanStack Query、组件和浏览器验证约束。
- `frontend/README.md` — 前端启动、测试和目录边界；Agent 页面必须只访问公开 `/api/v1` 契约。

没有用户提供的外部规范或 ADR。营养数据源、LangGraph/PostgreSQL Checkpointer 与 SSE 实现细节必须在 Phase 2 research 中依据当前官方资料核实，不能把未验证的外部文档结论写成既定事实。

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `backend/app/main.py` 已提供 FastAPI 应用工厂、版本化 `/api/v1` 路由挂载、CORS 和稳定错误外壳；Phase 2 的 Agent router 应通过同一入口注册并保持错误响应不泄露 Provider/数据库细节。
- `backend/app/auth/api.py` 已建立 Bearer 认证、请求级 Service 组合和从 PostgreSQL 重新确认用户/会话的模式；Agent API 必须复用或抽取这一权威身份边界，并把认证用户绑定到 `thread_id` 所有权。
- `backend/app/core/config.py` 已提供 Pydantic Settings 与生产环境 fail-closed 校验；Provider、图预算、Checkpoint 和事件配置应进入同一受校验边界，密钥仍只来自服务端环境变量。
- `backend/app/notifications/ports.py` 展示了 Protocol port + adapter + fake 的现有 Provider 模式，可作为 `ReasoningModelProvider` 和营养领域端口的结构参考。
- `frontend/src/App.tsx` 已包含受保护的 `/app/analyze` 占位路由和统一 `AppShell`；Phase 2 在该位置接入真实文字分析页面，并在能力完成后把 `/app` 默认入口从 `/app/me` 调整为 `/app/analyze`。

### Established Patterns

- 后端路由只翻译 HTTP，应用 Service 拥有业务规则和事务，Repository 只负责持久化；Agent 编排层只能通过工具调用领域 Service，不能直接查询 SQLAlchemy Model。
- Schema、ORM Model、Provider DTO 与 LangGraph State 必须分离并分别执行运行时校验。
- Service 测试使用 fake repository/provider；Repository、migration 和 Checkpointer 使用隔离的真实 PostgreSQL；Agent 图使用 Fake Provider 验证路由、interrupt/resume、幂等与循环终止。
- 前端使用 React Router 管理真实路径、TanStack Query 管理服务端状态，并只调用公开 FastAPI `/api/v1` 契约；MSW 不能替代真实跨栈和内置浏览器验收。
- 所有新增目录必须同时维护职责、允许依赖和文件索引 README，并同步更新直接父级 README 索引。

### Integration Points

- 新增 Agent、营养目录、Provider、运行记录与 Checkpoint 相关模块，并通过 Alembic migration 承载权威数据和 AGT-07 运行元数据。
- 在 `backend/app/main.py` 注册认证保护的 Agent/SSE API；API 必须验证 `thread_id` 属于当前登录用户。
- 将 LangGraph 工具适配器连接到营养 Application/Service，而不是直接连接数据库 Repository。
- 用真实分析页面替换 `frontend/src/App.tsx` 的 `PlaceholderTabPage title="分析"`，并接入结构化 SSE 事件、线程快照恢复、追问表单和结果展示。
- 扩展 `backend/tests/`、`frontend/tests/` 与真实浏览器路径，覆盖公开 API、断线恢复和用户可见状态，不通过直接写数据库或伪造 token 验收。

</code_context>

<specifics>
## Specific Ideas

- 用户明确说明当前没有现成营养数据库；Phase 2 必须自行建立小型、合法、可追溯的种子目录，而不是要求用户手工准备数据。
- 典型自然语言份量包括“一碗米饭”“半个苹果”“一份番茄炒蛋”；只有受控目录存在确定性换算时才能直接计算。
- 典型定向修正包括“米饭改成半碗”和“第二项不是鸡肉，是鱼”；修正后应保留其他项目并只重算受影响部分。
- 模糊候选和部分结果都必须诚实表达：目录没有的数据就明确没有，不能用模型估算把结果补齐。

</specifics>

<deferred>
## Deferred Ideas

- 图片上传、安全处理与 Qwen-VL 多菜识别 — Phase 3。
- 用户确认并保存餐食、历史记录、长期偏好与 Mem0 — Phase 4。
- 真实饮食规划子图与用户反馈后的餐单调整 — Phase 5。
- 大规模营养目录扩充和管理员维护界面 — Phase 6。

</deferred>

---

*Phase: 2-可追问的 Agent 核心*
*Context gathered: 2026-08-28*
