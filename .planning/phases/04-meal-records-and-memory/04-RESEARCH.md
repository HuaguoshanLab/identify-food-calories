# Phase 4: 餐食记录与长期记忆 — 实施研究

**Date:** 2026-08-31
**Scope:** MEM-01..06；只研究 Phase 4，不提前实现规划看板或 Phase 5 餐单。

## 结论

1. **PostgreSQL 必须同时承担餐食权威数据与记忆审计账本。** Mem0 只能做白名单偏好的语义服务/索引，不能成为权限、审计、删除状态或用户列表的唯一事实来源。
2. **Mem0 的 `memory_id` 不是授权凭据。** Mem0 当前 API 对搜索和列表要求传 `user_id` filter，但单条 `get/update/delete(memory_id)` 是按记忆 ID 操作；应用必须先以 `(memory_id, user_id, status=active)` 查本地账本，再调用 adapter。
3. **删除需要 transactional outbox。** 用户确认后先在同一 PostgreSQL 事务中把餐食/记忆标记为不可见、写删除任务；所有读取和召回只接受 active 数据。后台再删除 Mem0 与 pgvector，失败可重试，但任何失败都不能使已删内容再被读到或召回。
4. **pgvector 不可替代关系型过滤。** pgvector 官方说明近似 HNSW 在过滤后可能返回不足结果；Phase 4 的个人数据规模宜优先 `WHERE user_id = :user_id` 的精确检索，或将 tenant 数据分区。绝不能先向量检索、再在应用层过滤用户。
5. **确认保存是新的领域命令，而不是给 Agent Thread 加字段。** `AgentThread` 保留会话/短期状态；餐食记录与其不可变营养快照需要独立模型、Repository、Service、API schema 和 Alembic migration。

## 当前代码与缺口

| 现状 | 证据 | Phase 4 含义 |
| --- | --- | --- |
| 已有 PostgreSQL LangGraph checkpointer 依赖 | `backend/pyproject.toml` 固定 `langgraph-checkpoint-postgres==3.1.2` | 不更换机制；增加真实 Postgres 集成测试证明线程状态跨进程可恢复。 |
| Agent ledger 已隔离用户并保留来源 | `backend/app/agent/models.py` 的 `AgentThread`、`AgentRun`、`AgentEvent` 都有 `user_id`；`repository.py` 的查询均按用户过滤 | 餐食保存只接受已完成、归属当前用户的 Agent 线程，保存来源 UUID 但不把 UUID 当权限。 |
| 现有删除 Worker 有 24 小时 SLA | `backend/app/agent/retention.py`、`AgentDeletionIntent`、`Settings.retention_deletion_sla_hours` | 复用 lifecycle/lease 模式；餐食和记忆删除建立独立、可重试的 outbox，不混淆 Agent 线程清理。 |
| `AnalyzePage` 已展示 completed report 和定向修正 | `frontend/src/features/agent/components/AnalyzePage.tsx` | 在完整报告卡追加“确认并保存”；仅成功响应后显示已保存状态，不能把本地点击假装持久化。 |
| `/app/records` 仍是占位页 | `frontend/src/App.tsx` | 替换为真实、日期分组的记录页与详情路由；不能借 Phase 6 趋势图扩张范围。 |
| 尚未引入 Mem0 或 embedding Provider | `backend/pyproject.toml`、`backend/app/core/config.py` | 新依赖/配置必须固定版本、通过受校验 factory/port 注入，并提供 fake；不得把模型密钥或原始对话交给 adapter。 |

## 推荐领域边界

### 1. 权威餐食记录

建议新增独立 `meal_records` 与 `meal_record_items`：

- `meal_records`：`id`、`user_id`、`agent_thread_id`/`agent_run_id`、`consumed_at`、`created_at`、`updated_at`、`deleted_at`、`nutrition_catalog_version`、`calculation_version`、总营养快照与来源状态。
- `meal_record_items`：保存确认时的显示名称、受控 food reference、克数、逐项营养、估算标记与次序；不在读取时根据最新目录回算。
- 保存 Service 在同一事务中验证：thread 属于用户、状态已完成、报告完整且版本化、该报告尚未被本命令重复保存；以 command/idempotency key 防止双击造成两条记录。
- 更新只允许用户自己的 active record；修改后重新生成受影响项目和总量的确定性快照，更新 `updated_at`，不创建版本历史。

### 2. 长期记忆账本与 Mem0 adapter

建议新增本地 `preference_memories`（或等价模块）作为**审计/授权账本**，并以 `external_memory_id` 关联 Mem0：

- 只允许 `goal`、`avoidance`、`stable_preference` 三个白名单类别。应用在调用 Mem0 前构造最小、规范化的陈述，禁止上传整段聊天、原图、base64、运行日志或模型思维链。
- 保存 `user_id`、类别、规范化文本、source kind、created/updated/deleted 时间、Mem0 memory ID、adapter/version、操作状态与安全摘要。列表/编辑/删除全都先按 `user_id` 读取这张表。
- “用户直接表达”可以自动入账；“模型推测”先创建 pending proposal 或在状态内暂停，只有确认才生成 active memory。实现必须能审计这两个来源，不能把推测伪装成用户事实。
- 用户编辑时先更新本地 canonical text 与来源为 `user_maintained`，再通过 outbox 更新 Mem0；检索只使用本地 active 账本允许的外部 ID/内容。

### 3. 检索模型

三类来源分开查询、分开标注，再由领域 Service 组合成安全 DTO：

- **长期偏好：**Mem0 `search(query, filters={"user_id": stable_user_key})`；结果必须和本地 active ledger join/校验，拒绝没有本地归属或已删条目。
- **历史餐食：**以 PostgreSQL/pgvector 的 `user_id`、`deleted_at IS NULL`、业务类别和记录状态在 SQL 中强制过滤；小数据量使用精确搜索优先，避免 HNSW filter recall 陷阱。
- **受控营养知识：**单独的 catalog-scoped embedding 表，使用 `food_id`、目录版本、publication/eligibility 状态过滤；结果是说明性知识，不能写回用户记忆或替代 nutrition Service 计算。
- 返回项带 `source_type`、`source_id`（服务端内部）、人类可读来源/时间。面向前端/Agent 的 DTO 只传需要的短依据，如“已参考你的忌口：不吃辣”。

### 4. 删除链

删除命令的顺序必须是：

1. 所有权校验；
2. 单一 PostgreSQL 事务内标记删除/软删除，删除或停用本地 embedding，创建外部删除 outbox；
3. commit 后立即将条目从列表、详情和所有 retrieval queries 排除；
4. worker 以租约领取任务，调用 Mem0 delete 与剩余 pgvector 清理；成功记录完成，暂态失败指数退避重试；
5. 监测积压/终态失败，但 API 只给用户“已删除”安全反馈。

餐食删除只删除餐食快照与来源引用，不联动删除 Agent Thread；这是已锁定的产品规则。

## API 与前端建议

- 采用版本化 `/api/v1` REST：餐食确认保存、记录列表、单条详情/更新/删除，以及记忆列表、更新/删除。分页/排序以稳定 `consumed_at DESC, id DESC` 为准；查询参数和响应均为独立 Pydantic schema。
- 餐食确认命令接受线程/运行引用和 idempotency key，但 Service 从权威 completed report 构造快照；客户端不得提交任意营养总数。
- `AnalyzePage` 完成报告后显示显式保存动作；保存成功才变为“已保存”，并阻止相同结果重复保存。
- `RecordsPage` 做日期倒序分组、真实空态、详情、用餐时间编辑与不可逆删除确认。更新/删除 mutation 后精准失效 list/detail query；无需做趋势图。
- 记忆管理可以位于现有“我的”详情层或本阶段新增受保护路径；由 UI-SPEC 决定具体入口、焦点、loading/error/empty state，不能在没有合同下凭感觉搭页面。

## 测试与安全门禁

1. **Service（fake repository + fake memory adapter）：**确认保存幂等；用户不能读取/改/删其他人的餐食或记忆；白名单拒绝；直接表达与推测确认来源正确；编辑后来源变为 `user_maintained`。
2. **真实 PostgreSQL/Alembic：**从空库迁移，快照不随 catalog 更新改变；两个用户在 SQL/pgvector 检索中零交叉；删除在数据库事务提交后立即不可见；outbox 暂态失败重试后最终完成。
3. **Agent/Checkpointer：**用 Fake Provider 验证同一 `thread_id` 的 checkpoint resume；通过真实 PostgreSQL checkpointer setup/reopen 验证持久化，不以内存 fake 冒充。
4. **HTTPX 契约：**所有 endpoint 均 Bearer-protected，跨用户返回统一 404/403 策略；无原始图片、完整对话、外部 provider payload、embedding、内部 ID 或思维链泄露。
5. **前端与浏览器：**Vitest 覆盖保存、日期分组、空态、编辑和删除确认；Playwright + Codex 内置浏览器从真实登录用户走“分析 → 确认保存 → 记录详情 → 删除”，并验证删除后刷新/重新访问不可见。

## 外部资料（已核验，2026-08-31）

- [Mem0 Quickstart](https://docs.mem0.ai/platform/quickstart) — `add(..., user_id=...)` 与 `search(..., filters={"user_id": ...})` 的当前基本合同。
- [Mem0 v3 migration](https://docs.mem0.ai/migration/platform-v2-to-v3) — v3 将 search/get-all 的实体 ID 放入 filters，且默认检索参数已变化；adapter 必须固定并测试所选 SDK/API 版本。
- [Mem0 async client](https://docs.mem0.ai/platform/features/async-client) — `get_all`/批量删除必须带实体 filter，是本地授权校验之外的第二道保护，不是替代品。
- [pgvector README](https://github.com/pgvector/pgvector) — HNSW/IVFFlat 的过滤、iterative scan、multi-tenancy 与精确检索说明；近似索引过滤后可能不足召回。
- [LangGraph Postgres checkpointer reference](https://langchain-ai.github.io/langgraph/reference/checkpoints/) — `PostgresSaver` 与 `setup()`/持久化 schema 的当前使用边界。

## 计划风险

- Mem0 SDK/API 正在演进，尤其 v3 检索 filter 位置与默认 threshold/rerank；依赖必须精确锁定并由 adapter 封装，禁止业务代码散落 SDK 调用。
- 让“今天不想吃辣”自动成为长期偏好是用户锁定的行为，但会污染未来建议；必须清楚展示来源与删除入口，且不得将其升格为医疗/过敏事实。
- 近似向量索引在 tenant filter 下可能欠召回；Phase 4 不应为了虚假的性能过早使用共享 HNSW。先用严格 SQL 过滤与精确检索，规模证据出现后再调优。

## 规划输入

建议至少拆成四个可验证切片：

1. 权威餐食记录、快照、Alembic、Service/API 与确认保存；
2. 记忆账本、Mem0 port/fake/adapter、审计/outbox 与删除重试；
3. pgvector 三来源检索、用户隔离与 Agent 工具接线；
4. H5 记录/详情/保存/记忆管理 UI、真实浏览器路径、教学文档与安全回归。
