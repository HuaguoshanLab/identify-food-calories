# Phase 6: 用户看板与后台管理 - Context

**Gathered:** 2026-09-02
**Status:** Ready for planning

<domain>
## Phase Boundary

本阶段将用户端现有“记录”Tab 升级为摄入看板：今日摘要、本周趋势、周复盘和按日期分组的历史餐食。它必须继续使用既有四 Tab H5 壳，不能增加看板/复盘 Tab。

本阶段还创建与 `frontend/`、`backend/` 同级、独立构建部署的 `admin-frontend/` React 项目。后台通过受数据库实时角色校验的 `/api/v1/admin/*` 管理营养目录版本、模型配置、Agent 运行审计和管理员操作审计；用户 H5 不包含任何后台路由或导航。

范围不包含医疗诊断或治疗、通用目标的伪造、展示原图/用户原文/密钥/完整 Graph State/模型思维链，亦不包含新的用户角色、复杂多级审批流、完整食谱或购物清单。

</domain>

<decisions>
## Implementation Decisions

> **规划追踪状态（2026-09-02）：** 用户选择将以下讨论决策标记为
> `[informational]`，不再作为 GSD 决策覆盖门禁的独立阻断项。它们保留为
> 历史与实现参考；已生成的 PLAN、AI-SPEC、UI-SPEC、REQUIREMENTS 和架构约束
> 仍是 Phase 6 的可执行合同。

### 用户看板与时间口径

- [informational] **D-01:** `/app/records` 的首屏固定为“今日摄入摘要 → 本周趋势 → 按日期分组的历史餐食”；不新增底部 Tab 或独立用户端看板项目。
- [informational] **D-02:** 今日摘要展示总热量、蛋白质/脂肪/碳水相对个人目标区间的状态，以及当天已保存餐食数量；不得伪装为医学精度。
- [informational] **D-03:** 若用户没有完整个人资料或未生成饮食计划，只展示已确认的实际摄入，不显示或猜测目标对比。
- [informational] **D-04:** 所有趋势与周统计按用户实际用餐时间、用户本地自然日和自然周归档；补记的餐食必须回填到原用餐日期。

### 周复盘与受限模型建议

- [informational] **D-05:** 周复盘默认展示本周（周一至今天），允许查看已结束的过去完整周。
- [informational] **D-06:** 复盘先给基于已保存餐食的客观汇总与可见模式，再给 1–3 条普通饮食参考建议；必须明确它仅根据已记录数据生成，且不构成医疗建议。
- [informational] **D-07:** 复盘永远展示数据覆盖范围（已记录天数和餐数）。记录不足时只能给已有汇总，禁止输出趋势判断或建议。
- [informational] **D-08:** 建议可由模型生成个性化自然语言，但模型只能接收后端已经计算、可追溯的聚合事实及安全约束；输出必须运行时校验，不得自行生成权威营养数字、医疗结论或思维链。

### 营养目录版本治理

- [informational] **D-09:** 管理员对菜品、别名、每 100g 标准营养、来源和授权状态的改动必须经历“草稿 → 审核 → 发布新不可变版本”；新分析和新餐单只使用已发布的合格版本，历史餐食继续使用确认时快照。
- [informational] **D-10:** v1 的任意管理员均可创建、审核和发布目录版本；每一步必须记录操作者、时间、必填原因和字段级前后差异，不新增目录审核员角色或双人审批门槛。
- [informational] **D-11:** 已发布条目的授权撤销或关键营养数据失格后，必须立即禁止它进入后续分析和新餐单；不允许重算、覆盖或删除既有已确认的餐食快照。
- [informational] **D-12:** 发布前必须展示菜名/别名、每 100g 营养、来源链接、授权状态的字段级差异和受影响菜品数量；发布原因必填。后台主界面不以原始 JSON diff 代替人类可读预览。

### 运行审计与模型配置

- [informational] **D-13:** Agent 运行审计默认展示近 24 小时总运行数、失败率、P50/P95 延迟和总估算费用，并提供可筛选的单次运行列表。
- [informational] **D-14:** 运行列表可按时间范围、运行状态、图版本、Provider/模型版本、失败节点和失败码筛选。运行详情只显示工具名称、耗时、费用、调用计数和安全摘要；禁止显示用户邮箱、原文、原图、完整 State 或模型思维链。
- [informational] **D-15:** 停用 Provider 时立即阻止新的模型调用和新运行；已经发出的调用依既有超时完成并完整记账，随后向用户返回安全、可重试的失败结果。不得硬中断为无法解释的半截状态。
- [informational] **D-16:** 模型版本、单次费用上限和周期费用上限由管理员填写原因并确认后，立即形成可追溯的配置版本，只影响其后启动的新运行；正在执行的运行按启动时配置快照完成。密钥永不读出、存入后台可见状态或回显。

### 已继承且不可突破的边界

- [informational] **D-17:** 用户 H5 保持“分析、记录、计划、我的”四 Tab；后台必须是独立 `admin-frontend/`，后端 `/api/v1/admin/*` 的数据库权威 RBAC 是最终授权真相，前端隐藏菜单不能代替它。
- [informational] **D-18:** 所有用户可见流式进度和后台运行摘要只使用安全的业务阶段/摘要，不暴露 Provider 原文、内部节点细节以外的敏感状态、原图、密钥或完整模型推理。

### the agent's Discretion

- 确定本地时区来源、周起始日计算、趋势图具体类型、聚合 API 的分页和缓存策略，以及数据不足阈值；必须保持 D-01..D-07 的事实边界。
- 依据当前 Provider 与 Pydantic 官方资料，确定周复盘模型的结构化 DTO、提示词版本、允许建议类别、拒绝/降级策略、成本预算和输出校验；模型只能表达经批准的聚合事实。
- 确定目录草稿、版本、发布和失格的精确数据库 Schema、Alembic 拆分、幂等键、事务边界与并发控制；必须保留过去记录的快照稳定性和完整审计差异。
- 确定 `admin-frontend/` 的目录组织、独立 Vite 配置、路由守卫、TanStack Query 契约生成/验证和视觉组件细节，但不得复制用户 H5 或绕过公开 API。
- 确定运行指标的精确聚合窗口、P50/P95 算法、成本保留精度、运行详情分页和配置热加载策略；必须符合 D-13..D-16 及现有运行账本的安全数据最小化。

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 产品、范围与安全合同

- `.planning/PROJECT.md` — 独立 `admin-frontend/`、PostgreSQL 权威数据、确定性营养真相、数据最小化和健康安全边界。
- `.planning/REQUIREMENTS.md` — UI-02..03、ADM-01..05、ARC-08、EDU-02..03 的正式要求与边界。
- `.planning/ROADMAP.md` — Phase 6 目标、依赖和五项成功标准；Phase 7 的范围切分。
- `.planning/STATE.md` — 已完成的上游阶段与现有状态信息；当进度文本与 ROADMAP 冲突时以 ROADMAP 为准。
- `AGENTS.md` — 模块化单体、RBAC、审计、数据最小化、Alembic、测试、教学和真实浏览器验收总约束。

### 上游用户、Agent 与数据合同

- `.planning/phases/03-multimodal-meal-analysis/03-CONTEXT.md` — 多模态失败表达、数据最小化和不展示 Provider/思维链的既有语义。
- `.planning/phases/04-meal-records-and-memory/04-CONTEXT.md` — 餐食确认、稳定营养快照、实际用餐时间、历史展示、删除链和用户隔离合同。
- `.planning/phases/05-diet-planning-subgraph/05-CONTEXT.md` — 个人资料/目标来源、受控菜谱、规划运行账本、安全业务状态、普通饮食建议和健康拒绝边界。
- `docs/ui/h5-foundation.md` — 用户 H5 页面壳、唯一滚动区、四 Tab、安全区、语义 token、可访问性和浏览器验收合同。
- `frontend/AGENTS.md` — 用户端 API、TanStack Query、H5 约束、测试和真实浏览器验收要求。
- `backend/AGENTS.md` — API → Service → Repository → Model、Graph/Schema/Provider DTO 分离、Alembic 与真实 PostgreSQL 测试边界。

### 已有实现接点

- `frontend/src/App.tsx` — 现有用户端路由；Phase 6 只能升级 `/app/records`，不得注册后台路由。
- `frontend/src/layouts/BottomNavigation.tsx` — 四 Tab 的固定路由导航，不能追加“看板”或“复盘”。
- `frontend/src/features/records/components/RecordsPage.tsx` — 看板、周复盘和历史记录的用户端接入位置。
- `frontend/src/features/records/api/client.ts` — 用户餐食记录公开 API 边界；看板数据应扩展此 feature 的明确 API 边界。
- `frontend/src/features/plans/components/PlanPage.tsx` — 个人目标、普通饮食提示和安全流式状态的既有用户端语义。
- `backend/app/records/models.py` — 已确认餐食、营养快照和实际用餐时间的权威事实来源。
- `backend/app/records/service.py` — 用户隔离、记录修改与删除链的领域服务边界。
- `backend/app/agent/models.py` — 运行、事件、调用、延迟、费用、失败码和安全摘要的现有 ledger；后台审计必须复用其最小化数据，不得收集原文。
- `backend/app/agent/service.py` — Agent 线程所有权、运行生命周期、Checkpoint、成本和超时的唯一应用服务路径。
- `backend/app/admin/api.py` — 现有 `/api/v1/admin/probe` 的数据库权威 RBAC 模式；Phase 6 后台端点必须延续而非只做前端守卫。
- `backend/app/admin/service.py` — 当前管理员权限和角色变更审计的事务边界。
- `backend/app/nutrition/models.py` — 目录、版本、来源、别名、份量和合格性的数据模型接点。
- `backend/app/nutrition/service.py` — 受控、版本化营养目录和确定性计算服务；目录管理不得让模型成为营养真相来源。
- `backend/app/planning/models.py` — 受控菜谱对目录版本、合格性和授权审核的依赖；目录失格必须阻断后续餐单。

### 外部资料

没有冻结的图表、分位数计算、运行配置热加载或模型周复盘输出规范。研究阶段必须使用当前官方资料核实前端图表库、FastAPI/Pydantic、模型 Provider 配置与结构化输出、成本记录和配置更新语义；不得把未经核实的 SDK 行为写成事实。

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `frontend/src/features/records/`：已有真实餐食记录 API、日期分组、详情和编辑页面；看板应扩展该 feature，而不是另建平行用户数据页。
- `frontend/src/components/ui/`：已有 `Card`、`Alert`、`AlertDialog`、`Badge`、`Skeleton`、`Button` 等 H5 原语，可用于摘要、空态、复盘和不可逆后台操作确认。
- `frontend/src/features/plans/`：已有目标区间、普通饮食提示、TanStack Query、Zod 和安全业务阶段表达，可复用其交互模式但不跨 feature 直接导入私有组件。
- `backend/app/agent/models.py`：已持久化 `AgentRun`、`AgentEvent`、`AgentInvocation` 的版本、状态、失败码、耗时、费用与安全摘要，是运行审计的最小数据基础。
- `backend/app/admin/`：已有基于认证会话和 PostgreSQL 实时角色的 `/api/v1/admin/probe`，以及原子管理员审计模式。
- `backend/app/nutrition/` 与 `backend/app/planning/`：已有受控、版本化目录、来源/授权以及受控菜谱版本依赖，是目录治理和失格阻断的基础。

### Established Patterns

- API 只翻译 HTTP，Service 拥有业务规则和事务，Repository 只持久化；任何数据库变更必须使用 Alembic。
- Schema、ORM Model、Graph State 与 Provider DTO 分离并在边界运行时校验；模型不能替代确定性营养和聚合事实。
- 所有用户资源以 SQL `user_id` 过滤；UUID 不是授权能力；管理员权限必须从 PostgreSQL 当前角色重新读取。
- 用户端只调用 `/api/v1`，TanStack Query 管服务端状态；所有用户可见改动均需组件测试、真实 PostgreSQL/API、Playwright 和一次内置浏览器真实路径验收。

### Integration Points

- 在 `frontend/src/features/records/` 以公开统计 API 扩展 `RecordsPage`，连接实际用餐时间、稳定营养快照和个人目标；`App.tsx` 与 `BottomNavigation.tsx` 不新增 H5 Tab。
- 增加独立的聚合/周复盘领域服务。模型周复盘只能通过经校验的窄 Provider 端口读取确定性聚合，而不能查询 ORM 或 Agent 原文。
- 将 `backend/app/admin/` 从 probe 扩展为受 RBAC 和审计保护的目录、运行和模型配置 API；每个管理动作经 Service 写入前后差异和理由。
- 新建同级 `admin-frontend/`，独立构建、独立路由和认证恢复；它只能使用公开 admin API，不能导入用户 H5 页面或服务端代码。
- 目录发布/失格要与 `nutrition` 和 `planning` 的合格性筛选协作，使后续分析和餐单 fail closed，同时保留历史记录快照。

</code_context>

<specifics>
## Specific Ideas

- 用户明确确认“记录”Tab 是用户看板和周复盘的唯一入口；不增加底部导航项目。
- 管理员后台主导航预期包含概览、营养目录、Agent 运行审计、模型配置和操作审计。
- 周复盘希望提供受限的模型个性化建议，而不是纯确定性模板，但必须严格限制输入事实、输出范围和安全校验。

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 6-用户看板与后台管理*
*Context gathered: 2026-09-02*
