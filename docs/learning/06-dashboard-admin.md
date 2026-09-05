# Phase 06：用户看板与后台管理教学

## 这阶段解决什么问题

Phase 6 不是“再加几个统计卡片”。它把**已确认餐食快照**、**受控周复盘**和**可审计后台命令**连成一条可追溯链。用户端只读事实与安全投影；后台只通过公开 API 发出有理由、可审计的命令；数据库仍是权限、目录版本和历史快照的权威。

入口代码：[`backend/app/dashboard/api.py`](../../backend/app/dashboard/api.py)、[`backend/app/admin/api.py`](../../backend/app/admin/api.py)。端到端实际浏览器证据、自动化门禁与仍待复验边界：[`docs/verification/phase-06-browser-acceptance.md`](../verification/phase-06-browser-acceptance.md)。

## 1. 保存时固定时区，统计时确认当前口径

餐食确认保存时，客户端提交 IANA `time_zone`；Records Service 校验它，并把 `consumed_at` 投影为持久化的 `consumed_local_date`。用户确认的统计时区只是一种当前统计口径，**不是**“恢复用户当时所在地点”。因此 overview、趋势和 history 都按保存的 local date 聚合，之后浏览器时区变化不会改写历史统计。

链路：`frontend/src/features/records/api/client.ts` → [`backend/app/records/api.py`](../../backend/app/records/api.py) → [`backend/app/records/service.py`](../../backend/app/records/service.py) → `MealRecord`。迁移顺序从 Phase 5 的 `0012` 接到 `0013_dashboard_time_attribution.py`，后续 Phase 6 迁移连续到 `0019`（runtime config）；只能用 Alembic head，不允许手改表。

验证：[`backend/tests/integration/test_record_local_time_attribution.py`](../../backend/tests/integration/test_record_local_time_attribution.py)、[`backend/tests/records/test_record_service.py`](../../backend/tests/records/test_record_service.py)。

### 看板的统计时区为什么要再确认一次

RecordsPage 首次打开时，浏览器只能把 IANA 名称作为 **records-owned command** 提交给 [`backend/app/records/api.py`](../../backend/app/records/api.py) 的 `dashboard-time-zone-confirmations`。Records 持久化一次确认的 preference；[`backend/app/dashboard/repository.py`](../../backend/app/dashboard/repository.py) 仅通过 dashboard consumer-owned、tenant-scoped 的只读 `DashboardTimezoneReadPort` 为当前用户读取它，绝不猜测 UTC 默认值，也没有写入 preference 的能力。随后 [`backend/app/dashboard/service.py`](../../backend/app/dashboard/service.py) 用 `ZoneInfo` 复验该名称，再把注入的 aware UTC instant 转为用户本地 today/Monday；[`backend/app/dashboard/api.py`](../../backend/app/dashboard/api.py) 只把缺失/损坏 preference 映射为安全的 409。overview 和无 `week_start` 的 weekly-review 都由该 preference 选当前周；显式 `week_start` 只能访问已结束的本地 Monday 周，当前周、非 Monday 和未来值均为 422。

前端链路是 [`frontend/src/features/records/components/RecordsPage.tsx`](../../frontend/src/features/records/components/RecordsPage.tsx) → [`frontend/src/features/records/api/client.ts`](../../frontend/src/features/records/api/client.ts) → records confirmation → dashboard public read。`RecordsPage` 只有 confirmation 成功才启用 overview/history/weekly-review；当前 overview 与默认 weekly-review 不提交浏览器派生的 `week_start` 或 `time_zone`。D-04 的原因很简单：客户端时区是可变输入，若让它随每次 dashboard read 充当权威，同一用户可得到互相矛盾的统计窗口和缓存；读模型必须只信后端已验证、按用户隔离的 preference。

确定性测试分别覆盖同一 UTC instant 下 Shanghai 与 Los Angeles 的本地日/周、缺失或损坏 preference 在 aggregate、facts、cache 和 Provider 前 fail-closed 409、无参数 current 与仅已结束周的 GET/refresh 边界，以及绝对路径 IANA 输入的 400、无写入和无异常详情。对应证据在 [`backend/tests/dashboard`](../../backend/tests/dashboard)、[`backend/tests/unit/test_dashboard_api.py`](../../backend/tests/unit/test_dashboard_api.py)、[`backend/tests/unit/test_weekly_review_api.py`](../../backend/tests/unit/test_weekly_review_api.py)、[`backend/tests/unit/test_meal_record_api.py`](../../backend/tests/unit/test_meal_record_api.py) 与 [`frontend/src/features/records/components/RecordsPage.test.tsx`](../../frontend/src/features/records/components/RecordsPage.test.tsx)。这些是日历数学与输入边界证据，不是营养或医疗准确性指标。

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

# guarded 全栈：每个 runner 自己管理测试库、FastAPI、Vite 与 Mailpit
cd ../frontend
E2E_FRONTEND_PORT=5182 E2E_BACKEND_PORT=8002 E2E_RECORDS_ADMIN_FRONTEND_PORT=5185 \
  npm run test:e2e -- --grep 'records-dashboard|真实登录后的记录页显示低覆盖周复盘'

cd ../admin-frontend
E2E_ADMIN_BACKEND_PORT=8003 E2E_ADMIN_USER_FRONTEND_PORT=5183 E2E_ADMIN_FRONTEND_PORT=5184 \
  npm run test:e2e -- --grep admin-management
```

Records E2E 不是 mock：`records-dashboard.spec.ts` 在 Shanghai 与 Los Angeles Chromium contexts 中先观察公开 confirmation，再验证 dashboard/review 读取不带 `time_zone` authority；`records-weekly-review.spec.ts` 在同一真实前置后只断言低覆盖闭合响应和安全 DOM。`admin-management.spec.ts` 是独立后台的 guarded runner。它们都不能替代内置浏览器；本轮真实浏览器的普通用户确认范围是 analyze → save → Records 的四个 Tab 与低覆盖安全文案，具体路径及未复验项目见验收记录。浏览器和 E2E 都不覆盖所有跨日/history cursor 组合、全部周复盘 terminal 状态、管理员 overview/disable 或会话失效；这些不能被夸大为已完成。

## 7. 营养目录表格与 CSV 交换（独立快速任务）

目录首页现在把查找和维护分开：上方查询条件提交后进入 TanStack Query key，FastAPI 验证筛选及页码，Service 检查当前管理员角色，Repository 使用相同 predicate 得到列表和总数。表格列统一按每 100g 展示。这里是可变的管理列表，用页码支持跳页和总数；按创建时间、UUID 排序使编辑不会改变顺序，但新增记录后分页可能变化，不能将它当成一致性快照或替代 dashboard 的签名 cursor。

新增和编辑在侧边表单里复用草稿预览协议，仍由服务器计算变更差异。保存后失效目录 Query，使表格读取真实已提交状态。发布资格属于既有独立审核/发布协议，导入不会绕过它。

CSV 请求链为：本地选择文件 → `import-preview` 服务端解析/逐字段校验 → 展示数量、前五行和错误行号 → 填写原因并确认 → `import` 重新校验 → 同一事务逐行创建草稿、revision 和审计 → 一次提交。不能循环调用每条都会提交的单条新增方法，否则第 N 行出错会留下前 N−1 行的部分导入。当前批量路径直接复用服务内审计原语，异常统一回滚；真实 PostgreSQL 测试注入第二行错误证明第一行及审计也被回滚。

批量幂等由管理员与请求键派生批次键，并为各行派生稳定命令键，保存在既有草稿命令账本。事务级 advisory lock 防止同一批次并发写入。请求指纹包含文件、原因与确认状态；同键不同内容拒绝，同键相同内容返回同一组草稿 ID。前端对网络失败保留此键，避免用户点击重试时重复新增。重新选择文件属于新批次，界面明确说明不会覆盖现有目录。

文件限制为 UTF-8 CSV、1 MB、500 条；表头与顺序必须匹配下载模板。多个别名以 `|` 分隔，导出复用同一格式。导出只包含公开目录字段，遵循查询条件而非当前分页，超过 10000 条要求缩小范围；带 BOM 方便 Excel 识别中文，文本单元格以公式符号开头时添加文本前缀，避免电子表格执行输入内容。没有将下载请求的令牌放进 URL。

验证入口：`backend/tests/admin/test_catalog_csv.py`（校验、权限、幂等）、`backend/tests/integration/test_catalog_draft_repository.py`（SQL 筛选/分页和真实回滚）、`backend/tests/unit/test_admin_catalog_api.py`（HTTP）、`admin-frontend/src/features/catalog/CatalogListPage.test.tsx`（表格/表单/导入交互）及 `admin-management.spec.ts`（真实公开跨栈）。

## 常见错误

- 在前端按浏览器时区重算历史日：会让同一条确认记录在不同设备改变统计归属。
- 用 offset 翻页或把 cursor JSON 直接交给浏览器：前者在插入后漂移，后者可被篡改并泄露查询形状。
- 把 Profile、原始餐食或 Agent State 送进周复盘 Provider：这是隐私与事实越界，不是“更个性化”。
- 让 SSE 透传模型文本：会把内部技术信息变成用户界面和安全面。
- 仅在后台菜单隐藏功能：普通用户仍可直接请求 API；必须由后端 DB RBAC 拒绝。
- 让客户端拼 diff 或发布历史可修改对象：这会破坏并发基线、审计与历史快照的证据链。
- 将 Playwright、浏览器观察、Vitest、HTTPX、真实 PostgreSQL 或冻结 eval 互相冒充：这是另一种假绿。各层只能声明自己实际覆盖的边界。
