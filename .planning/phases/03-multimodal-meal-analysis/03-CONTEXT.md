# Phase 3: 多模态餐食分析闭环 - Context

**Gathered:** 2026-08-31
**Status:** Ready for planning

<domain>
## Phase Boundary

本阶段让已登录用户通过拍照或相册上传一张餐食图片，经过安全校验、元数据剥离和临时处理后交给 Qwen-VL 识别。结构化识别候选进入既有餐食分析图：受控目录唯一映射和足够可靠的份量线索进入确定性营养计算；模糊菜名、目录外项目或不足以计算的份量集中追问；最终页面展示逐项营养、整餐汇总、置信度/估重误差来源，并支持在同一分析线程中确认报告或定向修正。

本阶段不长期保存原图、base64 或把模型估算当作未经标记的营养事实；不保存用户确认餐食或长期偏好（Phase 4）；不扩充为大规模营养目录后台（Phase 6）；不把视觉失败伪装为视觉成功。

</domain>

<decisions>
## Implementation Decisions

### 图片入口、校验与隐私沟通

- **D-01:** 分析首页首屏同时提供“拍照”和“从相册选择”入口；不把来源选择藏在二级步骤。
- **D-02:** 上传区直接展示可展开的简短隐私承诺：图片仅用于本次分析，服务端执行安全校验和元数据剥离，完成或超时后删除，并告知会由第三方视觉模型处理；不增加额外勾选。
- **D-03:** 前端预先说明支持的格式与体积限制以减少无效上传，但 MIME、大小、像素、真实解码与危险图片拒绝仍以服务端为唯一裁决，失败必须给出可操作原因。
- **D-04:** 图片分析完成即删除原图。用户仅修正菜名或重量时继续使用已有结构化状态，不依赖原图；重新拍照或上传必须新建分析。

### 多菜识别、候选与估重

- **D-05:** 只有目录映射不唯一、识别置信度不足或份量无法计算时才打断；同一轮集中询问全部阻塞项。唯一且可信的项目直接进入确定性工具链。
- **D-06:** 模糊菜名的每项最多展示 3 个具备计算资格的受控目录候选，附做法、常见份量或来源等区分线索，并允许用户补充更准确名称。
- **D-07:** Qwen-VL 的视觉估重可以作为计算输入；最终报告必须标明“估算重量”和不确定性。菜品映射不唯一或估重低于安全阈值时仍必须集中追问，不能无条件把低置信度猜测当事实。

### 模型失败、对账与降级

- **D-08:** 超时、限流和临时网络错误仅可在图预算内自动重试一次；同一上传使用幂等标识，自动与手动重试都不得重复调用或重复计费。
- **D-09:** 当客户端无法判定 Qwen-VL 是否已接收请求或产生费用时，进入“结果状态未知”，先使用请求标识查询或对账；未确认前不得自动二次调用，只能让用户显式发起新重试。
- **D-10:** Qwen-VL 持续不可用或输出不符合结构化契约时，提供“改为文字描述这餐”的降级入口，复用既有 Phase 2 文字分析链，并明确本次图片没有被识别。
- **D-11:** 前端只展示稳定的用户级失败类别及下一步，例如图片不符合要求、服务暂时不可用或本次分析达到上限；严禁暴露 Provider 原文、堆栈、内部节点和模型思维链。

### the agent's Discretion

- 在不改变 D-02 的告知事实与 D-04 的删除语义前提下，确定具体隐私文案、支持格式、尺寸/像素上限、临时存储位置、超时策略和可访问性交互。
- 在不违反 D-05/D-07 的前提下，依据冻结评测与风险分析确定可信映射/估重阈值、候选排序、报告的置信度表达和估重误差说明。
- 确定 Provider DTO、图节点接线、幂等与对账协议、请求标识持久化、失败类别代码以及 Qwen-VL 的区域/留存/删除承诺验证方式；必须先以当期官方资料核实，不能把供应商营销说明写成事实。
- 确定报告确认与定向修正的具体控件、OpenAPI/SSE 事件和测试样本构成，但 Phase 3 的“确认”不得创建 Phase 4 的餐食记录。
- 为 QLT-01 制定冻结样本构成、识别/归一化/估重/营养报告门槛和 fail-closed 发布规则，覆盖失败与不确定案例，而不是只测试成功图片。

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 产品、阶段边界与安全合同

- `.planning/PROJECT.md` — 多模态产品边界、Qwen-VL/DeepSeek Provider 分工、图片删除、确定性营养真相与健康安全限制。
- `.planning/REQUIREMENTS.md` — VIS-01..06、NUT-06..07、UI-01 与 QLT-01 的正式要求，以及与 Phase 4..7 的能力切分。
- `.planning/ROADMAP.md` — Phase 3 目标、依赖、成功标准和不扩张到后续阶段的范围。
- `.planning/STATE.md` — Phase 2 已手动接受完成但发布证据仍 FAIL 的例外，以及 Qwen-VL 地区、留存和删除承诺必须在接入前核实的关注项。
- `AGENTS.md` — 模块化单体、受控工具、图片数据最小化、测试、教学与目录文档规则。

### 上游阶段与现有 UI 合同

- `.planning/phases/02-agent/02-CONTEXT.md` — 文字分析、受控目录映射、集中追问、定向修正、SSE、幂等、预算和失败处理的锁定行为；Phase 3 必须复用而非重建这些语义。
- `.planning/phases/02-agent/02-18-SUMMARY.md` — 上游阶段的发布例外与真实浏览器验收缺口；不得将该阶段表述为 release PASS。
- `docs/ui/h5-foundation.md` — H5 页面壳、唯一滚动区、语义 token、安全区、触控与可访问性基线。
- `frontend/AGENTS.md` — 公开 API 边界、TanStack Query、真实浏览器验收和图片上传页面约束。
- `backend/AGENTS.md` — API → Service → Repository → Model、Provider DTO/Graph State 分离、Alembic 与真实 PostgreSQL 测试约束。

### 现有实现接点

- `backend/app/agent/api.py` — 已有认证 Agent API、线程所有权与 SSE 接点；视觉端点或事件必须保持其安全边界。
- `backend/app/agent/graph.py` — 已有餐食分析图与工具调度边界；视觉输出只能作为受校验状态输入。
- `backend/app/agent/state.py` — 线程级运行状态，需扩展图片引用、识别项、份量线索和追问状态而不混入 Provider DTO。
- `backend/app/agent/service.py` — 线程快照、恢复、运行语义与幂等相关服务边界。
- `backend/app/core/config.py` — 受校验的 Provider、生产 fail-closed 与保留策略配置边界。
- `backend/app/providers/reasoning/ports.py` — 现有 Protocol、adapter、fake Provider 模式；Vision Provider 应遵循相同可替换与可测试边界。
- `frontend/src/features/agent/components/AnalyzePage.tsx` — 现有文字分析页面，Phase 3 的上传、识别追问、报告与降级路径在此接入。
- `frontend/src/features/agent/stream/useAgentEventStream.ts` — 现有结构化 SSE 消费与断线恢复模式；不得暴露逐 Token 或思维链。
- `frontend/src/features/agent/api/client.generated.ts` — 前端唯一可依赖的版本化公开 Agent API 契约。

### 外部资料

没有已冻结的外部 Qwen-VL 规范。研究阶段必须查验当前官方 Qwen-VL API、文件传输/临时 URL、数据处理地区、保留与删除承诺，以及结构化输出、超时、幂等和计费查询能力；未核验前不得作出对用户的合规承诺。

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `backend/app/agent/`：已有认证线程、LangGraph 餐食分析、SSE、运行记录、保留任务和营养工具接线，可作为视觉结果进入图的唯一业务入口。
- `backend/app/nutrition/`：受控、版本化营养目录和确定性计算/校验服务已存在；视觉模型不得直接生成最终营养数值。
- `backend/app/providers/reasoning/`：已实现 port、factory、真实 adapter 和 fake，Vision Provider 应以同样分离方式落地。
- `frontend/src/features/agent/`：已有分析页、结构化 API client 与 SSE hook，可扩展上传、阶段状态、追问及文字降级，而无需新建平行页面。
- `frontend/src/components/ui/`：已有 Button、Input、Alert、Card、Dialog、Skeleton 等 H5 原语，可直接支撑上传和失败状态。

### Established Patterns

- 路由只处理 HTTP/SSE 语义，应用服务拥有事务和业务规则，Agent 图仅通过工具调用领域服务，不能直接查询 ORM。
- Provider DTO、Pydantic Schema、ORM Model 与 LangGraph State 必须分离并在边界运行时校验；测试必须能用 Fake Provider 覆盖失败、路由和中断恢复。
- `/app/analyze` 是受保护的真实入口；前端只访问 `/api/v1`，TanStack Query 管服务端状态，SSE 断线后基于同一 `thread_id` 恢复权威快照。
- 用户可见页面改动必须补齐 Vitest/Testing Library、真实 PostgreSQL/API 与 Playwright，并用 Codex 内置浏览器走真实页面和公开 API 验收。

### Integration Points

- 后端需以 Alembic 承载临时图片处理所需的最小可审计元数据、可删除引用、Provider 请求标识和结果状态，数据库不得保存原图/base64。
- 新 Vision Provider 通过受校验工厂接入，输出先转换为独立 schema，再写入 Agent State，之后由既有目录搜索、计算与校验工具处理。
- Agent API/SSE 需要暴露安全的上传进度、等待补充、已降级、失败和完成事件，并继承现有 `thread_id` 所有权和恢复语义。
- `AnalyzePage` 需要在既有文字流中增加拍照/相册入口、隐私提示、图片错误、候选/份量追问、估重标识、结果确认/纠正和文字降级。

</code_context>

<specifics>
## Specific Ideas

- 用户希望拍照和相册上传都在首屏可见。
- 图片可以用于视觉估重，但估重必须在报告中诚实标注不确定性；无法可靠计算时优先一次性集中追问。
- 失败时应当给用户实际可走的路径：一次受控自动重试、状态未知先对账、无法视觉识别就切换文字分析。

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 3-多模态餐食分析闭环*
*Context gathered: 2026-08-31*
