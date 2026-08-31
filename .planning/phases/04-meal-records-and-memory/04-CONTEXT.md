# Phase 4: 餐食记录与长期记忆 - Context

**Gathered:** 2026-08-31
**Status:** Ready for planning

<domain>
## Phase Boundary

本阶段让登录用户将明确确认的餐食分析结果保存为 PostgreSQL 权威记录，在“记录”Tab 查看、修改和删除自己的餐食；同时以用户隔离的 Mem0 与 pgvector 管理可追溯的长期偏好和语义检索。长期记忆、历史餐食与受控营养知识可为后续分析和 Phase 5 规划提供带来源的上下文，但不能替代确定性营养计算或跨用户访问控制。

本阶段不交付趋势看板、周复盘或后台管理（Phase 6），不交付饮食规划子图（Phase 5），不把 Mem0 变成餐食业务事实源，也不展示原始分析对话、向量分数、内部 ID 或模型推理。

</domain>

<decisions>
## Implementation Decisions

### 餐食确认、记录与历史展示

- **D-01:** 只有用户点击“确认并保存”才创建权威餐食记录；报告完成或模型估算本身不得自动入库。
- **D-02:** 用户修改已保存餐食的食物、克数或备注时直接更新当前记录并保留 `updated_at`，不维护可恢复版本历史。
- **D-03:** 记录保存确认时的营养快照、目录/计算版本与安全的分析线程/运行来源引用；记录页不得暴露内部 ID 或原始对话。
- **D-04:** 默认实际用餐时间为保存时刻，用户可在保存前或详情中改为过去时间，禁止未来时间。
- **D-05:** “记录”页按日期倒序分组；每项展示用餐时间、餐食摘要、总热量和保存状态，点击进入详情。
- **D-06:** 详情页展示完整菜品、逐项及整餐营养、实际用餐时间、保存/更新时间和来源状态。历史记录永远展示确认时快照，不因目录升级静默重算。
- **D-07:** 空状态必须诚实说明尚无已保存餐食，并提供前往“分析”页的明确入口；禁止示例或假数据。

### 长期记忆的写入、出处与编辑

- **D-08:** 用户直接明确表达的目标、忌口或偏好可自动写入白名单长期记忆；模型推测出的内容必须先由用户确认。用户选择将“今天不想吃辣”此类临时表达也先按长期偏好保存。
- **D-09:** 每条记忆必须展示类别、内容、来源（用户直接表达、用户确认推测或用户手动维护）、创建时间和最近更新时间；不展示触发记忆的原始对话全文。
- **D-10:** 用户编辑记忆后，以编辑内容为准，将来源更新为“用户手动维护”，并保留创建时间及更新时间。

### 删除链与用户反馈

- **D-11:** 删除餐食或记忆后立即从页面和所有后续检索中移除；后台必须可靠完成 PostgreSQL、Mem0 与 pgvector 删除链，并支持安全重试。删除失败绝不能使内容重新可见或再次被召回。
- **D-12:** 删除餐食仅删除记录、营养快照及其来源引用；关联 Agent 线程、事件与运行记录继续遵循既有独立保留/删除规则。
- **D-13:** 删除餐食和长期记忆均需确认弹窗，并明确告知删除后立即停止使用且不可撤销。确认后立刻从列表移除并提示“已删除”，不泄露后台同步、Provider 或重试细节。

### 语义检索与冲突优先级

- **D-14:** 个性化上下文同时检索长期偏好、历史餐食和受控营养知识；三类来源必须可区分，并始终受 `user_id` 与关系型业务过滤约束。
- **D-15:** 受控营养知识只能在版本与关系型过滤边界内提供检索信息，绝不能覆盖确定性营养计算或校验结论。
- **D-16:** 当前长期偏好优先于过去餐食行为；历史仅作为背景，不能反向覆盖或自动改写记忆。
- **D-17:** 当记忆影响后续分析或规划建议时，以简短可读的形式说明依据，例如“已参考你的忌口：不吃辣”；不得展示向量分数、内部 ID 或模型推理。

### the agent's Discretion

- 确定餐食、营养快照、记忆审计、删除 outbox/重试与 pgvector 索引的具体 Schema、Alembic 拆分、事务边界和版本字段，但必须满足上述权威性、用户隔离与删除语义。
- 确定白名单的精确枚举、模型推测判定契约、记忆展示文案、分页/加载策略、召回数量和排序；必须先依据当前 Mem0 与 LangGraph/PostgreSQL 官方资料核实可行性。
- 确定测试矩阵，至少覆盖跨用户隔离、自动/确认写入、来源与时间、快照稳定性、删除链失败重试和被删除内容零召回。

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 产品、范围与安全边界

- `.planning/PROJECT.md` — PostgreSQL 权威业务数据、Mem0 白名单长期偏好、pgvector、主图/子图和健康安全边界。
- `.planning/REQUIREMENTS.md` — MEM-01..06 的正式要求，以及后续 Phase 5..7 的范围切分。
- `.planning/ROADMAP.md` — Phase 4 目标、依赖与四项成功标准。
- `.planning/STATE.md` — Phase 2 的发布例外，以及 Phase 4 必须验证用户隔离、可审计写入和删除链的已知关注项。
- `AGENTS.md` — 架构方向、Agent 工具边界、数据最小化、Alembic、测试、教学和浏览器验收规则。

### 上游 Agent 与 UI 合同

- `.planning/phases/02-agent/02-CONTEXT.md` — Checkpointer、线程所有权、SSE、保留和删除的既有契约；Phase 4 不得绕过。
- `.planning/phases/03-multimodal-meal-analysis/03-CONTEXT.md` — 已确认报告、定向修正、图片数据最小化及“Phase 3 确认不创建餐食记录”的边界。
- `docs/ui/h5-foundation.md` — 用户 H5 页面壳、安全区、语义 token、可访问性和真实浏览器验收合同。
- `frontend/AGENTS.md` — 公开 API、TanStack Query、用户可见页面测试和内置浏览器验收约束。
- `backend/AGENTS.md` — API → Service → Repository → Model、Graph/Provider/Schema 分离、Alembic 与真实 PostgreSQL 测试约束。

### 现有实现接点

- `backend/app/agent/README.md` — 现有 Agent ledger、线程所有权、保留与删除的职责边界。
- `backend/app/agent/models.py` — 现有线程、运行、事件、图片、调用和删除意图的权威模型；餐食记录不能挤入 Checkpoint。
- `backend/app/agent/repository.py` — 现有 tenant-bound repository 与 flush-only 持久化模式。
- `backend/app/agent/service.py` — 既有 Agent 事务、所有权、幂等和保留协议的应用服务边界。
- `backend/app/agent/schemas.py` — 当前安全公开 API schema；Phase 4 应新增独立、版本化的餐食/记忆契约。
- `frontend/src/App.tsx` — `/app/records` 当前诚实占位路由，应替换为真实记录入口而不破坏既有 Tab 路由。
- `frontend/src/features/agent/components/AnalyzePage.tsx` — 已有分析报告与确认/修正接点；保存餐食必须从公开 API 接线。

### 外部资料

没有冻结的 Mem0、pgvector 或 LangGraph Checkpointer 外部规范。研究阶段必须查验当前官方文档，尤其是 Mem0 的用户隔离、读取/更新/删除语义及其向量存储边界；不能把未核实的 SDK 行为写成事实。

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `backend/app/agent/`：已有用户绑定的线程、运行、事件、调用、保留和删除意图 ledger；餐食记录可安全引用分析来源但必须作为独立权威业务模型。
- `backend/app/nutrition/`：已有受控、版本化目录与确定性计算/校验服务；保存的是当时计算结果快照，不能让模型或向量召回重写它。
- `frontend/src/features/agent/`：已有报告、SSE 和 `thread_id` 恢复模式，可在确认报告后接入保存命令。
- `frontend/src/components/ui/`：既有 Card、AlertDialog、Button、Skeleton 等 H5 原语，可用于分组记录、详情、空态和不可逆删除确认。

### Established Patterns

- API 只处理 HTTP，Service 拥有事务和业务规则，Repository 只持久化；LangGraph 只能通过领域工具访问 Service，不能直接访问 ORM。
- 所有 tenant-bound 查询都必须在 SQL 中按 `user_id` 过滤；UUID 本身不是授权能力。
- Schema、ORM、Graph State 与 Provider DTO 分离并做运行时校验；数据库变更一律由 Alembic 承载。
- 用户端只调用 `/api/v1`，TanStack Query 管服务端状态；组件测试、真实 PostgreSQL/API 测试和真实浏览器验收共同构成门禁。

### Integration Points

- 新增独立的餐食记录与记忆领域模块、受限 Mem0 adapter 和 pgvector repository，并以 Alembic 创建权威表、审计与索引结构。
- 已确认的 Agent 报告经公开 API 调用领域 Service 保存；Agent 图通过工具调用同一 Service 读取安全的个性化上下文。
- `/app/records` 替换占位页，接入日期分组、详情、编辑、删除确认和真实空状态；“分析”报告接入显式确认保存。
- 后端测试必须以两个真实用户验证关系型过滤与向量检索零泄漏，并模拟外部记忆删除失败后的不可召回与最终重试。

</code_context>

<specifics>
## Specific Ideas

- 用户要求“记录”页从真实的已保存餐食开始，按日阅读，不用示例或假数据。
- 用户希望保存的历史营养可追溯、稳定：目录更新不应静默改变过去记录。
- 用户要的是可控但不繁琐的记忆：明确表达自动记，模型猜测先确认；建议说明所参考的偏好即可。

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 4-餐食记录与长期记忆*
*Context gathered: 2026-08-31*
