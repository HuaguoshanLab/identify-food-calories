---
phase: 06-user-dashboard-admin
plan: 19
subsystem: admin-frontend
tags: [react, typescript, zod, vitest, msw, rbac, accessibility]
requires:
  - phase: 06-17
    provides: 内存 access token、Query cache 清理与 admin probe guard
  - phase: 06-18
    provides: DB-RBAC 保护的最小 metrics/list/detail run API
  - phase: 06-11
    provides: 最小化的通用管理员 audit API
provides:
  - 严格 Zod runs metrics/list/detail 与 audit cursor DTO 客户端
  - 守卫下的 catalog、runs、runtime config、audit 独立后台路由
  - 只读、最小化、键盘可用的 runs 诊断和服务端 audit 表格
affects: [06-20, 06-22, admin-frontend, browser-verification]
tech-stack:
  added: []
  patterns: [feature-owned-zod-api, shared-run-utc-filter, opaque-cursor-pagination, dom-field-allowlist]
key-files:
  created:
    - admin-frontend/src/features/runs/api.ts
    - admin-frontend/src/features/runs/RunsPage.tsx
    - admin-frontend/src/features/runs/RunDetailDrawer.tsx
    - admin-frontend/src/features/audit/api.ts
    - admin-frontend/src/features/audit/AuditPage.tsx
  modified:
    - admin-frontend/src/App.tsx
    - admin-frontend/src/features/README.md
    - admin-frontend/src/features/audit/README.md
key-decisions:
  - "runs metrics 与列表始终用同一 serialised UTC allowlist filter object，筛选变化清除签名 cursor。"
  - "audit 页面仅把后端 audit DTO 的固定 scalar diff 字段送入 DOM；command key 和未知字段不渲染。"
  - "401/403 立即清空当前页面投影并委托 AdminAuthProvider 清理内存会话与 Query cache。"
patterns-established:
  - "只读后台 feature：API 层严格 Zod 响应解析，页面只接收 API 层类型并安全失败。"
  - "长表位于自身横向滚动容器，窄屏详情使用键盘 Escape 可关闭的抽屉。"
requirements-completed: [ADM-01, ADM-03, ADM-05, ARC-08]
duration: 10min
completed: 2026-09-03
---

# Phase 06 Plan 19: 后台 Runs/Audit UI Summary

**管理后台现在可在不持久化令牌、不泄露 ledger 原文的前提下，按受限 UTC 筛选读取运行指标、最小详情及完整服务器审计时间线。**

## Performance

- **Duration:** 10 min
- **Started:** 2026-09-03T12:13:00Z
- **Completed:** 2026-09-03T12:23:14Z
- **Tasks:** 2/2
- **Files modified:** 13

## Accomplishments

- Runs feature 为 metrics、keyset list 与 detail 定义独立严格 Zod DTO；列表与指标共用同一默认 24 小时 UTC 范围及筛选对象，翻页只发送服务端 opaque cursor。
- RunsPage 使用四卡指标、语义表格、局部横向滚动与可关闭抽屉；抽屉仅映射状态、版本、计数、耗时、费用、失败码、节点及安全摘要。
- Audit feature 只请求 `GET /api/v1/admin/audit`，支持 actor/time/action/object/reason allowlist filters 与 opaque cursor；表格只显示服务端 actor/time/action/object/reason、已过滤的 scalar 字段差异和关联版本。
- App 已登记 guarded `/admin/catalog`、`/admin/runs`、`/admin/model-configs`、`/admin/audit` 路由；每个 feature 自己持有 HTTP/Zod 边界，不持久化 token 或跨 feature 复用目录数据。

## Task Commits

1. **Task 1: 写 runs/audit 页面和 audit cursor client RED 测试** — `981244f` (`test`)
2. **Task 2: 实现 runs/audit clients、页面和路由** — `09c5603` (`feat`)

## Files Created/Modified

- `admin-frontend/src/features/runs/{api.ts,RunsPage.tsx,RunDetailDrawer.tsx}` — 运行 API、响应式诊断页和最小详情抽屉。
- `admin-frontend/src/features/audit/{api.ts,AuditPage.tsx}` — 审计 API、只读表格、allowlist diff 与安全失败状态。
- `admin-frontend/src/features/{runs/README.md,README.md,audit/README.md}` — 新能力目录责任、允许依赖及父索引。
- `admin-frontend/src/App.tsx` — 受已有 probe guard 包裹的后台页面路由装配。
- `admin-frontend/src/features/{runs/RunsPage.test.tsx,audit/AuditPage.test.tsx}` — MSW/Vitest 的 filter、cursor、DOM 最小化、键盘及 401/403 契约。

## Decisions Made

- Run 详情客户端采用 strict object schema：后端若意外新增敏感顶层字段，解析失败而不是把它穿透到 Drawer。
- Audit 事件保持后端通用审计 DTO，但页面只从固定 safe-field set 渲染 scalar diff；不会显示 command key 或把未知 diff 解释为可信数据。
- 按 `768/1024/1280` 使用 Drawer 全宽/最大宽、表格局部滚动、`md` 两列及 `xl` 四卡/筛选网格；后台总体导航壳仍由 06-22 统一接入，避免在 `App.tsx` 违反布局职责边界。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test correctness] 移除 RED 测试中固定日期假设，并使 Drawer Escape 成为真实键盘行为**
- **Found during:** Task 2
- **Issue:** 运行页默认的最近 24 小时 UTC 范围不能固定为测试日期；仅将 Escape 绑定在遮罩元素上也无法覆盖焦点位于抽屉内部的键盘关闭路径。
- **Fix:** 测试改为断言 metrics/list 的两个 UTC 参数相同；Drawer 在打开时注册并清理 document Escape listener。
- **Files modified:** `admin-frontend/src/features/runs/{RunsPage.test.tsx,RunDetailDrawer.tsx}`。
- **Verification:** focused Vitest 6 passed、完整 Vitest 16 passed。
- **Committed in:** `09c5603`。

---

**Total deviations:** 1 auto-fixed（Rule 1: 1）。
**Impact on plan:** 修复了 UTC 与真实键盘可访问性合同；未扩大 API、数据表、依赖或数据暴露面。

## Verification

- `cd admin-frontend && npm test -- --run src/features/runs/RunsPage.test.tsx src/features/audit/AuditPage.test.tsx` — 2 files、6 tests passed。
- `cd admin-frontend && npm test` — 5 files、16 tests passed。
- `cd admin-frontend && npm run typecheck` — passed。
- `cd admin-frontend && VITE_ADMIN_API_BASE_URL=/api/v1/admin npm run build` — passed。
- 静态敏感字段/持久化扫描覆盖 runs/audit 生产代码：未发现 `localStorage`、`sessionStorage`、`indexedDB`、Cookie 写入或禁止的 raw 敏感字段标识。

## Browser Verification

- **Attempted paths:** `http://127.0.0.1:5179/admin/runs`、`http://127.0.0.1:5179/admin/audit`。
- **Observed result:** 两个真实产品路由均由 `AdminRouteGuard` 重定向至 `/admin/login`，没有 runtime-only 管理员 token 时不会渲染/缓存 runs 或 audit 内容。
- **Not verified:** 带真实管理员登录/refresh 会话的 API 数据、筛选、翻页、Drawer 详情与 401/403 端到端路径。
- **Integrity:** 未伪造 token、直写数据库、调用内部函数或将 MSW 当作浏览器验收；06-22 登录壳与 06-20 跨栈回归可补足完整路径。

## Known Stubs

None. 未登录时的占位登录根是既有 06-22 接线范围，不是 runs/audit 的假数据或替代服务端投影。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 06-20 可在真实管理员会话下验证 metrics/list/detail/audit 的公开端到端路径及 401/403 cache-clear。
- 06-22 可把已注册路由装入 `layouts/AdminShell` 和真实登录恢复流程；不得将 App 路由层扩展为领域请求或导航状态所有者。

## Self-Check: PASSED

- 已确认 `RunsPage.tsx`、`RunDetailDrawer.tsx`、`AuditPage.tsx`、两个 feature API 与 `runs/README.md` 均存在。
- 已确认 `981244f` 和 `09c5603` 位于 Git 历史；任务提交未删除受跟踪文件。

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-03*
