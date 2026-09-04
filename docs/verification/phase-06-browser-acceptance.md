# Phase 06 浏览器验收记录

**执行日期：** 2026-09-04（Asia/Shanghai）  
**原则：** 只允许真实产品页面与公开 `/api/v1` API；未使用数据库直写、seed、伪造 token、内部函数、真实模型或截图替代验收。测试账户仅按角色描述，本文不记录任何凭据或个人数据。

## 已完成的自动化门禁

| 门禁 | 命令 | 结果 | 说明 |
| --- | --- | --- | --- |
| 冻结周复盘评测 | `cd backend && uv run pytest tests/evals/test_weekly_review_eval.py -q` | PASS，14 passed | 覆盖低覆盖零调用、cache hit 零调用、并发复用、版本/facts miss 与未知结果不重放的冻结目录。 |
| 已发布目录→保存纵向 PostgreSQL 回归 | `APP_ENV=test ... uv run pytest tests/integration/test_meal_records.py tests/records/test_record_service.py tests/unit/test_meal_record_api.py -q` | PASS，12 passed | 通过受审计的测试 RuntimeConfig 准入，覆盖 completed_validated 报告→保存→更新→隔离→删除；未访问验收库。 |
| H5 records DTO 回归 | `cd frontend && npm test -- --run src/features/records/api/dashboard.test.ts src/features/records/api/client.test.ts src/features/records/components/HistoryMealList.test.tsx` | PASS，4 passed | 覆盖浏览器 IANA 时区、保存响应本地日期字段、FastAPI history 时间戳及末页省略 cursor。 |

## 未通过的自动化门禁（不得视为通过）

| 门禁 | 实际结果 | 阻塞原因 |
| --- | --- | --- |
| H5 Playwright：`records-dashboard`、安全 SSE、周复盘 | BLOCKED | `frontend/tests/e2e/records-dashboard.spec.ts` 缺失；已有安全 SSE/周复盘 spec 的隔离运行环境没有可通过公开路径准备的 RuntimeConfig。不得通过 seed、直接数据库写入或伪造身份补齐。 |
| 独立后台 Playwright：`admin-management` | BLOCKED | `admin-frontend/` 尚无 Playwright 配置和 `admin-management.spec.ts`；当前命令会把 Vitest 配置误作 runner 并在 `src/test/setup.ts` 失败。 |

## 已由 Codex 内置浏览器确认的公开页面

| 路径 | 角色 | 可观察结果 | 结论 |
| --- | --- | --- | --- |
| `http://127.0.0.1:5178/` | 未登录访客 | 首页可访问。 | 仅证明用户端公开入口可达。 |
| `http://127.0.0.1:5178/login` | 未登录访客 | 登录页面可访问并显示正常。未输入或提交任何表单。 | 仅证明公开登录 UI 可达；不构成认证成功验证。 |
| `http://127.0.0.1:5178/app/analyze` | 已建立的普通用户会话 | 用户在公开页面提交“白米饭 100 克”；受控目录匹配后显示完整 130 kcal 报告与“确认并保存”。 | 已验证真实 H5 分析、受控目录选择与可保存报告；未使用报告伪造或内部调用。 |
| `http://127.0.0.1:5178/app/analyze` → 保存 | 已建立的普通用户会话 | 点击“确认并保存”成功，随后可打开记录详情；详情显示 `admin-publication-v1` 与持久化本地时间归属。 | 已验证完整分析→确认→公开保存→详情路径。 |
| `http://127.0.0.1:5178/app/records` | 已建立的普通用户会话 | 今日摘要为 130 kcal/1 餐；趋势在 9 月 4 日为 130/1；history 显示一条“10:16 · 已保存 130 kcal”；周复盘显示 1 天/1 餐/130 kcal。 | 已验证保存结果进入 overview、trend、history 与低覆盖周复盘。 |
| `http://127.0.0.1:5179/admin/login?returnTo=/admin/overview` | 未登录访客 | 独立后台登录页可达，显示管理员邮箱/密码表单。未输入或提交。 | 仅证明独立后台公开登录入口可达；不构成管理员认证、RBAC 或后台数据路径验证。 |
| `http://127.0.0.1:5179/admin/catalog` → `/admin/catalog/:draftId/lifecycle` | 已认证管理员 | 通过实际表单创建 authorized “白米饭”草稿（aliases 为 `baimifan`、`白饭`），从保存草稿的“审核与发布目录”链接进入 lifecycle，完成审核与发布，活动版本为 v1。 | 已验证独立后台的草稿→审核→发布公开 UI 链；该测试菜品由用户明确授权创建。 |
| `http://127.0.0.1:5179/admin/runs` | 已认证管理员，同一 SPA 会话 | 通过菜单显示服务端指标、终态列表和白名单详情。一条 completed 测试运行显示 graph `meal-agent-graph.v1`、`2175 ms`、1 graph step / 1 model call / 2 tools、估算费用 `$0.000112`；详情未显示餐食原文、密钥或 Provider 原文。 | 已验证 DB-RBAC 后的 runs 指标、列表和最小详情。首次无终态运行时的“暂时无法读取运行诊断”不再归类为系统失败；有终态运行后相同公开路径正常显示。 |
| `http://127.0.0.1:5179/admin/audit` | 已认证管理员，同一 SPA 会话 | 显示本次管理员 bootstrap 与 `runtime_config.configure` 审计条目。 | 已验证受审计管理员操作在公开 audit UI 中可见。 |

## 未完成项（不得视为通过）

| 验收路径 | 当前阻塞 | 仍需的真实环境前置条件 |
| --- | --- | --- |
| 注册 → 邮箱验证 → 登录 | 本轮复用了已存在、用户授权的普通用户会话；没有重新执行注册/邮箱验证。 | 在隔离环境提供可重复的真实邮箱/Mailpit 验收链。 |
| 近午夜补记与 history cursor 翻页顺序 | 已验证单条保存后的 history 首屏；未创建额外历史记录来测试跨日和 cursor 翻页。 | 在隔离真实环境提供可经页面创建的多条测试记录。 |
| 周复盘 success、safety abstain、retryable 状态 | 真实用户记录与可用运行配置不可用；不能使用 Fake Provider 伪造 UI 结果。 | 提供预置但非本任务创建的可登录验收数据和正常 API。 |
| `/admin/overview`、UTC filter runs 深链接、runtime config disable | 已验证 catalog lifecycle、runs 最小详情与 audit；未验证 overview、filter 深链或 disable。 | 在隔离管理员环境逐项经 SPA 页面验证。 |
| catalog 失格与历史 snapshot 稳定 | 已验证草稿、审核和发布；未提交失格命令，不能声明发布历史稳定性已实测。 | 由用户明确授权后，在隔离目录数据上从 lifecycle 页面执行失格并复验。 |
| 普通用户后台拒绝与过期会话拒绝 | 没有独立普通用户后台会话；完整页重载清除管理员内存 token 是预期设计，但没有做完整拒绝矩阵。 | 在隔离真实会话执行普通用户访问与会话过期路径。 |

## 已知环境事实

- 角色提升没有公开产品 API；项目仅提供受审计运维 CLI。用户在当前验收中明确授权后，运维人员通过该 CLI 执行首位管理员 bootstrap；审计记录为 `330231c1-afb1-42fe-8bf3-cd5b5670d5ed`。未使用数据库直写或伪造 token。
- 经同一位已授权管理员的 `AdminService.configure_runtime` 业务路径创建非密钥 RuntimeConfig：版本 `v1`，已启用，单次调用上限 `$0.03`、周期上限 `$3.00`，配置 ID `5ce0ad54-76f7-48c4-9a35-bdf843a5a15e`。该命令写入了 `runtime_config.configure` 审计事件；不包含 Provider 密钥或端点。
- Codex 内置浏览器可确认用户端公开入口，但在本执行上下文中未暴露可用浏览器会话；上述两条公开页面观察由主验收任务的同一 Codex 内置浏览器完成。
- Admin access token 只存在运行时内存。直接完整页重载 `/admin/runs` 会清空这份内存状态并由 route guard 返回登录页；后续受保护路径必须在同一次登录后的 SPA 菜单导航中验证。
- Playwright 不能替代本记录：它仍需在 API、RuntimeConfig 与角色前置条件满足后重跑。

## 复验清单

1. 在内置浏览器用普通用户真实登录；不要复制或保存 token。
2. 通过实际页面补记跨日餐食并翻页 history，记录 cursor 顺序与统计口径。
3. 在独立后台用真实管理员登录；验证 overview、UTC filter 的 runs 深链接、catalog 失格与历史 snapshot、runtime config disable 与 audit。
4. 用普通用户访问后台确认固定拒绝；经用户明确授权后让管理员会话失效，确认固定重新登录提示与缓存清空表现。
5. 将每一项实测 URL、角色、结果和日期补入本文；只有所有未完成项消失后，才可以声称 Phase 06 浏览器验收完成。
