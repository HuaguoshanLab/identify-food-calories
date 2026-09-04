# Phase 06：用户看板与后台管理教学

## 这阶段解决什么问题

Phase 6 不是“再加几个统计卡片”。它把**已确认餐食快照**、**受控周复盘**和**可审计后台命令**连成一条可追溯链。用户端只读事实与安全投影；后台只通过公开 API 发出有理由、可审计的命令；数据库仍是权限、目录版本和历史快照的权威。

入口代码：[`backend/app/dashboard/api.py`](../../backend/app/dashboard/api.py)、[`backend/app/admin/api.py`](../../backend/app/admin/api.py)。端到端实际浏览器证据与缺口：[`docs/verification/phase-06-browser-acceptance.md`](../verification/phase-06-browser-acceptance.md)。

## 1. 保存时固定时区，查询时不猜历史地点

餐食确认保存时，客户端提交 IANA `time_zone`；Records Service 校验它，并把 `consumed_at` 投影为持久化的 `consumed_local_date`。用户确认的统计时区只是一种当前统计口径，**不是**“恢复用户当时所在地点”。因此 overview、趋势和 history 都按保存的 local date 聚合，之后浏览器时区变化不会改写历史统计。

链路：`frontend/src/features/records/api/client.ts` → [`backend/app/records/api.py`](../../backend/app/records/api.py) → [`backend/app/records/service.py`](../../backend/app/records/service.py) → `MealRecord`。迁移顺序从 Phase 5 的 `0012` 接到 `0013_dashboard_time_attribution.py`，后续 Phase 6 迁移连续到 `0019`（runtime config）；只能用 Alembic head，不允许手改表。

验证：[`backend/tests/integration/test_record_local_time_attribution.py`](../../backend/tests/integration/test_record_local_time_attribution.py)、[`backend/tests/records/test_record_service.py`](../../backend/tests/records/test_record_service.py)。

## 2. SQL 聚合、history cursor 与 completion projection

`DashboardRepository` 只在 SQL 中读取当前用户、未删除且有 `consumed_local_date` 的餐食快照，按本地日做能量/餐次聚合。history 不用 offset：插入新记录会让 offset 页漂移。它把 local date、时间和 UUID 组成 keyset 位置，由 `DashboardService` 用应用密钥签名；篡改 cursor 会在到 SQL 前失败。

目标区间也不能从规划资料猜测。dashboard 只经 `ports.py` 读取**未撤销且 validated 的 planning completion projection**；损坏或不合格 projection 被省略，已确认的餐食总量仍可正常显示。这将“是否有目标”变成可审计事实，而不是 UI 推断。

关键源码与测试：[`backend/app/dashboard/repository.py`](../../backend/app/dashboard/repository.py)、[`backend/app/dashboard/service.py`](../../backend/app/dashboard/service.py)、[`backend/tests/dashboard/test_dashboard_service.py`](../../backend/tests/dashboard/test_dashboard_service.py)、[`backend/tests/integration/test_dashboard_overview_projection.py`](../../backend/tests/integration/test_dashboard_overview_projection.py)。

## 3. completion projection、facts-first cache 与周复盘 graph

周复盘先从看板聚合得到去标识、确定性的 facts（日期范围、餐数、能量等），再决定是否可调用 Provider。覆盖不足直接返回闭合安全状态，Provider 零调用。覆盖合格时，cache key 包含 facts digest、graph 版本、prompt/规则版本及 runtime config 版本；数据库 advisory lock 与 `SELECT FOR UPDATE` 防止并发重复计费。

`weekly_review_graph.py` 是事实优先边界：它不拿 `PlanningProfile`、餐食原文、图片、邮箱、Agent State 或 Provider 原文。输出先经严格 DTO，再经独立语义阀校验 facts 支持性、分类范围、医疗/强制语言与调用上限。未知 Provider 结果不重放；schema 或安全错误最多一次明确修正重试。缓存只持久化最小安全摘要与版本元数据。

关键源码与测试：[`backend/app/dashboard/weekly_review_dto.py`](../../backend/app/dashboard/weekly_review_dto.py)、[`backend/app/dashboard/weekly_review_graph.py`](../../backend/app/dashboard/weekly_review_graph.py)、[`backend/tests/dashboard/test_weekly_review_cache_service.py`](../../backend/tests/dashboard/test_weekly_review_cache_service.py)、[`backend/tests/evals/test_weekly_review_eval.py`](../../backend/tests/evals/test_weekly_review_eval.py)。

## 4. SSE 是安全阶段，不是 Graph 调试通道

Agent 的公开 SSE 只发送 schema version、allowlist stage 和安全文案。浏览器不会直接渲染服务端传回的自由文本；`SafeProgressStages` 与 stream hook 只映射本地允许的阶段。未知/附加字段消费序号后进入一次通用可重试状态，避免泄露 ledger、Provider 输出、Graph State、费用或完整思维链，也避免无限重连。

源码/测试：[`backend/app/agent/api.py`](../../backend/app/agent/api.py)、[`frontend/src/features/agent/components/SafeProgressStages.tsx`](../../frontend/src/features/agent/components/SafeProgressStages.tsx)、[`backend/tests/agent/test_safe_stream_stage_mapping.py`](../../backend/tests/agent/test_safe_stream_stage_mapping.py)、[`frontend/src/features/agent/stream/useAgentEventStream.test.ts`](../../frontend/src/features/agent/stream/useAgentEventStream.test.ts)。

## 5. 管理员授权、不可变目录与运行快照

后台 route guard 只是体验层。每个 `/api/v1/admin/*` 请求在 `AdminService` 中从 PostgreSQL 重新读取 active role；JWT role claim 和页面菜单都不是授权真相。首位管理员只能通过受审计 CLI bootstrap，之后提升必须由现有管理员提供 reason；角色变化和 audit 同事务提交。

目录编辑遵循“草稿 → review → immutable publication → eligibility history”。预览、字段 diff、影响范围和 `If-Match` 基线全由服务端计算，客户端 raw JSON 或本地回显不是可信 diff。每条命令需 idempotency key 和非空理由，publication 使用 per-draft advisory lock；失格只阻止未来分析/新餐单，不改写已确认的历史餐食快照。

runtime config 只存非密钥字段（model alias、启停、费用上限和理由），用 optimistic version 与 append-only audit 建立不可变快照。新运行绑定启动时版本；变更不重写正在运行的任务。源码/测试：[`backend/app/admin/service.py`](../../backend/app/admin/service.py)、[`backend/app/admin/repository.py`](../../backend/app/admin/repository.py)、[`backend/tests/admin/test_runtime_config_service.py`](../../backend/tests/admin/test_runtime_config_service.py)、[`backend/tests/admin/test_catalog_lifecycle_service.py`](../../backend/tests/admin/test_catalog_lifecycle_service.py)、[`backend/tests/integration/test_catalog_publish_eligibility.py`](../../backend/tests/integration/test_catalog_publish_eligibility.py)。

## 6. 如何验证

```bash
# 后端 fake repository、graph 与 API 合约
cd backend
uv run pytest tests/dashboard tests/admin tests/unit/test_dashboard_api.py tests/unit/test_admin_rbac_api.py -q
uv run pytest tests/evals/test_weekly_review_eval.py -q

# 真实 PostgreSQL（测试 wrapper 保证不触碰开发库）
uv run python tests/run_pg.py --env-file .env.test.example -- \
  uv run pytest tests/integration/test_dashboard_repository.py tests/integration/test_dashboard_overview_projection.py tests/integration/test_catalog_publish_eligibility.py -q

# 用户端与后台严格 DTO / 组件行为
cd ../frontend && npm test -- --run src/features/records/api/dashboard.test.ts src/features/records/api/client.test.ts
cd ../admin-frontend && npm test -- --run src/features/catalog/CatalogLifecyclePage.test.tsx src/features/runs/RunsPage.test.tsx src/features/audit/AuditPage.test.tsx
```

真实浏览器已验证：普通用户“白米饭 100 克”分析为 130 kcal 后确认保存，records 显示今日/趋势/history/低覆盖周复盘；管理员在独立 SPA 完成 authorized 草稿→审核→发布，并查看 runs 最小详情与 audit。没有把这些事实夸大为完整 Phase 6 页面验收：records/admin 的 Playwright assets 仍缺失，overview、失格、runtime disable、拒绝矩阵与其他周复盘状态尚需隔离环境验证。

## 常见错误

- 在前端按浏览器时区重算历史日：会让同一条确认记录在不同设备改变统计归属。
- 用 offset 翻页或把 cursor JSON 直接交给浏览器：前者在插入后漂移，后者可被篡改并泄露查询形状。
- 把 Profile、原始餐食或 Agent State 送进周复盘 Provider：这是隐私与事实越界，不是“更个性化”。
- 让 SSE 透传模型文本：会把内部技术信息变成用户界面和安全面。
- 仅在后台菜单隐藏功能：普通用户仍可直接请求 API；必须由后端 DB RBAC 拒绝。
- 让客户端拼 diff 或发布历史可修改对象：这会破坏并发基线、审计与历史快照的证据链。
- 将缺少的 Playwright spec 写为通过：这是假绿。浏览器观察、Vitest、HTTPX、真实 PostgreSQL 和冻结 eval 是不同层级的证据。
