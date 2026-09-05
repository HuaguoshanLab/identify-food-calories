---
phase: 06-user-dashboard-admin
plan: 35
subsystem: ui
tags: [react, typescript, tanstack-query, vitest, timezone, dashboard]
requires:
  - phase: 06-34
    provides: "服务端由已确认统计时区定义 current overview 与默认周复盘的无范围契约"
provides:
  - "严格 200 的统计时区 confirmation client，以及可分类的 different-zone 409 冲突"
  - "不含浏览器范围的 current dashboard URL 与稳定 Query key"
  - "confirmation-gated RecordsPage：冲突时零 dashboard read，成功时只渲染服务端 today/week"
affects: [06-36, records, dashboard, frontend-e2e]
tech-stack:
  added: []
  patterns:
    - "浏览器 IANA 只能作为 records confirmation command 输入，不能成为 current dashboard range 或 cache authority"
    - "current weekly review 与 completed history 使用独立 URL、函数和 Query key"
key-files:
  created: []
  modified:
    - frontend/src/features/records/api/client.ts
    - frontend/src/features/records/api/dashboard.ts
    - frontend/src/features/records/api/weeklyReview.ts
    - frontend/src/features/records/components/RecordsPage.tsx
    - frontend/src/features/records/components/RecordsPage.test.tsx
key-decisions:
  - "只有 confirmation 的严格 HTTP 200 才开启 current dashboard reads；409 绝不伪装为幂等成功。"
  - "当前 overview/default weekly review 的请求与 Query key 不接受浏览器生成的 week_start/time_zone；显式 completed history 单独建模。"
patterns-established:
  - "安全冲突 UI 只输出可恢复的本地说明，不暴露 HTTP detail、已存 preference、token、Provider 或状态内部信息。"
requirements-completed: [UI-02]
duration: 6min
completed: 2026-09-05
---

# Phase 6 Plan 35: H5 服务端当前窗口门控 Summary

**Records H5 现在只在同统计时区的严格确认成功后读取服务端 current 窗口；浏览器本地周一无法再改写今日、趋势或默认周复盘。**

## Performance

- **Duration:** 6 min
- **Started:** 2026-09-05T02:03:00Z
- **Completed:** 2026-09-05T02:09:02Z
- **Tasks:** 2/2
- **Files modified:** 10

## Accomplishments

- `confirmDashboardTimeZone` 仅严格解析 200；same-zone replay 可读，different-zone 409 抛出可分类冲突，400、网络错误与 malformed DTO 保持失败。
- overview 与默认 weekly review 改为无范围的 server-current URL、稳定 `current` key；已结束周保留独立 typed history API/key。
- Records 页面移除 `deriveLocalWeekStart`，409 时不发 overview/history/weekly read，成功后保持“今日摘要 → 本周趋势 → 历史记录 → 周复盘”的既有 H5 顺序。
- Shanghai 与 Los Angeles 固定 fixture、冲突零读取和安全错误文案均由组件测试覆盖，且不依赖运行机时区。

## Task Commits

1. **Task 1: 收紧 confirmation client、range-free current URLs 与 Query keys** - `c3d118f` (test), `f39d119` (fix)
2. **Task 2: 让 RecordsPage 以 confirmation gate 读取 server-current，并同步 feature/components README** - `75cdf4f` (test), `db02bf0` (fix)

## Files Created/Modified

- `frontend/src/features/records/api/client.ts` - 严格 confirmation DTO 与 409 冲突分类。
- `frontend/src/features/records/api/dashboard.ts`、`weeklyReview.ts` - server-owned current API/key，独立 completed history。
- `frontend/src/features/records/api/*.test.ts` - 严格 200、409、current URL/key 与 completed history 回归。
- `frontend/src/features/records/components/RecordsPage.tsx` - 不再派生浏览器周范围，安全门控全部当前读取。
- `frontend/src/features/records/components/RecordsPage.test.tsx` - Shanghai/LA fixed fixture、零读取、D-01 顺序和安全文案。
- `frontend/src/features/records/{README.md,api/README.md,components/README.md}` - 同步 current/history 与 confirmation gate 的文件索引。

## Decisions Made

- 不把 409 当作“已确认”；它只表示当前浏览器 IANA 与持久统计口径冲突，必须停止看板请求。
- current 请求不携带调用方日期范围；历史周必须显式走独立 API，不能复用 current cache key。

## Verification

- `cd frontend && npm test -- --run src/features/records/components/RecordsPage.test.tsx src/features/records/api/client.test.ts src/features/records/api/dashboard.test.ts` — **3 files, 11 tests passed**。
- `cd frontend && npm run typecheck` — **passed**。
- `cd frontend && npm run build` — **passed**；仅有既有 500 kB chunk 建议，未影响构建成功。
- `git diff --check` — **passed**。
- `rg -n "deriveLocalWeekStart|week_start|time_zone" ...` — current `RecordsPage` 与 current API 无 browser-derived range；仅 typed completed-history 路径保留 `week_start`。

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - 没有新增依赖、迁移或外部配置。

## Known Stubs

None - confirmation、current dashboard reads 与安全冲突界面均连接公开 API，没有 placeholder 或空数据替代实现。

## User Setup Required

None - 不需要新增环境变量、密钥或服务配置。

## Next Phase Readiness

- 06-36 可使用真实公开 API、隔离 E2E 和内置浏览器路径验证 same-zone current read 与 changed-zone zero-read 行为。
- 浏览器验收仍必须由 06-36 执行，不能以本计划组件测试代替。

## Self-Check: PASSED

- 10 个计划内源码、测试和 README 均存在；`c3d118f`、`f39d119`、`75cdf4f`、`db02bf0` 均可从 Git 历史读取。
- 已扫描计划改动文件，未发现会阻塞目标的 TODO、FIXME、placeholder 或空数据 stub。

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-05*
