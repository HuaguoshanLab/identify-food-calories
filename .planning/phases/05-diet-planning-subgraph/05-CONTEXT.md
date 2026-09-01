# Phase 5: 饮食规划子图 - Context

**Gathered:** 2026-09-01
**Status:** Ready for planning

<domain>
## Phase Boundary

本阶段交付一个由主图路由进入的饮食规划子图。登录用户在“计划”页提交或复核身体资料、目标、忌口和口味偏好；系统先用确定性工具计算每日能量与宏量营养约束，再从受控菜谱生成并校验一日三餐。用户可用自然语言调整餐单，图在同一 `thread_id` 上保留约束、更新允许自动记忆的反馈，并在有界次数内恢复规划。

本阶段还把身体资料与目标的查看、编辑、删除入口加入“我的 → 个人资料”。忌口与口味偏好仍由既有“记忆”页统一管理。它不交付完整食谱、购物清单、趋势看板、周复盘、后台菜谱维护或医疗营养服务。

</domain>

<decisions>
## Implementation Decisions

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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 产品、范围与安全合同

- `.planning/PROJECT.md` — 产品目标、主图/两个子图、确定性营养真相、数据最小化及普通饮食建议边界。
- `.planning/REQUIREMENTS.md` — PLN-01..06 的正式要求，以及与 UI-02..03、ADM、评测阶段的范围切分。
- `.planning/ROADMAP.md` — Phase 5 目标、依赖、五项成功标准与 Phase 6 边界。
- `.planning/STATE.md` — 当前阶段位置和已完成的上游能力；其进度文本有历史偏差，不能取代 ROADMAP 的阶段完成事实。
- `AGENTS.md` — 模块化单体、Agent 只能通过工具调用领域服务、Alembic、健康安全、测试、文档与浏览器验收规则。

### 上游餐食、记忆与 Agent 合同

- `.planning/phases/02-agent/02-CONTEXT.md` — 主图路由、受控目录、集中追问、SSE、Checkpointer、幂等、预算和安全失败语义；规划子图必须复用而非绕过。
- `.planning/phases/03-multimodal-meal-analysis/03-CONTEXT.md` — 报告、确定性营养、用户级失败表达、线程恢复与非医疗提示的既有语义。
- `.planning/phases/04-meal-records-and-memory/04-CONTEXT.md` — PostgreSQL 权威记录、长期偏好白名单、用户隔离、来源审计、删除链，以及偏好优先于历史行为的冲突规则。
- `backend/AGENTS.md` — API → Service → Repository → Model 依赖方向、Graph/Schema/Provider DTO 分离和真实 PostgreSQL 测试边界。
- `frontend/AGENTS.md` — 仅使用公开 `/api/v1`、TanStack Query、真实页面验收和用户端安全约束。
- `docs/ui/h5-foundation.md` — H5 页面壳、唯一滚动区、Tab、安全区、语义 token 与可访问性合同。

### 现有实现接点

- `backend/app/agent/graph.py` — 主图已将 `diet_planning` 路由显式预留为未交付能力；Phase 5 必须替换该拒绝分支并保留有界执行语义。
- `backend/app/agent/state.py` — 当前版本化、可校验的线程 State 和预算模型；规划 State 必须独立于 Provider DTO 和 ORM。
- `backend/app/agent/service.py` — 线程所有权、运行账本、Checkpoint 读取/写入和 resume 生命周期；规划反馈必须使用同一权威路径。
- `backend/app/agent/tools.py` — 图只能看到的窄工具端口；规划工具应扩展此边界，不能令图直接查询 Repository 或 ORM。
- `backend/app/nutrition/service.py` — 受控目录、确定性营养计算和验证模式；规划的目标计算/餐单校验应采用同类确定性服务。
- `backend/app/memory/service.py` — 长期偏好白名单、来源、用户隔离和删除/重试语义；自动反馈写入必须遵守该合同。
- `backend/app/retrieval/service.py` — 偏好优先于历史与受控知识的三来源检索顺序。
- `frontend/src/App.tsx` — `/app/plans` 仍是占位页面；Phase 5 在此接入真实计划页和“我的”个人资料入口。
- `frontend/src/routePaths.ts` — 已预留 `/app/plans` 路径；个人资料的路由扩展必须保持集中路由常量。
- `frontend/src/features/README.md` — `features/plans/` 是计划功能的唯一预留位置，不得继续扩张通用 Placeholder 页面。
- `frontend/src/features/memory/README.md` — 忌口和口味偏好的既有管理边界，个人资料页不得复制其编辑职责。
- `frontend/src/features/agent/stream/useAgentEventStream.ts` — 结构化 SSE 消费和断线恢复模式；计划进度仅发送安全业务事件。

### 外部资料

没有已冻结的目标计算公式、宏量推荐或受控菜谱外部规范。研究阶段必须以当期权威/官方资料核实公式适用范围、成人普通人群安全限制、引用与授权；不得把模型输出或未核实的网络营养建议当作数值真相。

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `backend/app/agent/`：已有认证线程、运行账本、LangGraph 调用门面、Checkpointer 和稳定 SSE 事件语义；规划子图应接入此唯一 Agent 入口。
- `backend/app/agent/tools.py`：`NutritionToolAdapter` 已封装目录查询、营养计算、个人上下文检索和偏好捕获；可扩展为规划工具端口。
- `backend/app/nutrition/`：已有受控、版本化目录及确定性计算/校验 Service，能作为目标与餐单校验领域模式。
- `backend/app/memory/` 与 `backend/app/retrieval/`：已有用户隔离、偏好来源、可删除记忆和“偏好优先历史”的召回能力。
- `frontend/src/components/ui/`：既有 Card、Alert、Dialog、Skeleton、Button、Input 等 H5 原语可用于三餐卡片、状态、个人资料与删除确认。
- `frontend/src/features/README.md`：已为 `features/plans/` 预留唯一功能落点；无需制造平行页面架构。

### Established Patterns

- API 只翻译 HTTP/SSE；Service 负责业务规则与事务；Repository 只持久化；Agent 图只调用窄工具端口。
- Schema、ORM Model、LangGraph State 和 Provider DTO 分离且在边界运行时校验；任何数据库 Schema 变更都必须通过 Alembic。
- 所有用户资源在 SQL 中按 `user_id` 过滤；UUID 不是授权能力；敏感健康资料同样必须受此隔离和删除链约束。
- 用户端只访问版本化公开 API，TanStack Query 管服务端状态；用户可见改动需补组件测试、真实 PostgreSQL/API、Playwright 和内置浏览器真实路径验收。

### Integration Points

- 将现有 `diet_planning_not_available` 接线替换为真实规划子图，同时保留主图闭合路由、线程所有权、Checkpoint 和预算机制。
- 新增独立的规划资料、目标计算、受控菜谱和餐单校验领域模块；Graph 只能通过扩展后的工具 adapter 调用这些 Service。
- 在 `/app/plans` 用 `features/plans/` 的真实页面替换占位，使用三餐卡片、目标区间状态和安全业务进度。
- 扩展“我的”路由并新增个人资料公开 API；记忆页继续是忌口和口味偏好的唯一编辑入口。
- 以 Fake Provider 测试子图路由、interrupt/resume、自动偏好捕获、三次重排终止和高风险拒绝；以真实 PostgreSQL 验证资料/计划的用户隔离和删除后零读取。

</code_context>

<specifics>
## Specific Ideas

- 用户希望餐单能够直接执行：三餐结构清晰、每道菜有受控份量和简短标签，而非抽象的营养数字或复杂食谱。
- 用户接受在无法严格匹配时自动放宽热量或宏量目标，但必须把偏离透明地告诉用户。
- 用户希望身体资料和目标集中在“我的 → 个人资料”，同时避免与“记忆”页的偏好编辑重复。

</specifics>

<deferred>
## Deferred Ideas

- 完整配方、烹饪步骤和购物清单 — 独立能力，不属于 Phase 5。
- 摄入趋势、周复盘和图表看板 — Phase 6。
- 管理员受控菜谱/营养目录维护界面 — Phase 6。

</deferred>

---

*Phase: 5-饮食规划子图*
*Context gathered: 2026-09-01*
