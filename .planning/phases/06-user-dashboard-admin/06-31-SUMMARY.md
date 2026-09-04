---
phase: 06-user-dashboard-admin
plan: 31
subsystem: ui
tags: [react, typescript, tanstack-query, vitest, intl, timezone]
requires:
  - phase: 06-30
    provides: "records-owned 已确认统计时区与 server-authoritative dashboard 读取合约"
provides:
  - "严格的 records 统计时区 confirmation client，200 和既有 409 都可释放读取 gate"
  - "由 IANA formatToParts 和稳定 calendar arithmetic 推导的用户本地 Monday"
  - "确认失败时关闭 overview/history/weekly-review 请求的可恢复 RecordsPage UI"
affects: [06-32, frontend-records, dashboard-api]
tech-stack:
  added: []
  patterns:
    - "浏览器时区只传 records confirmation command；dashboard query key 仅包含服务端读取实际变量"
    - "instant + IANA formatToParts 提取 calendar parts，再进行与 host TZ 无关的周一算术"
key-files:
  created:
    - frontend/src/features/records/components/RecordsPage.test.tsx
  modified:
    - frontend/src/features/records/api/client.ts
    - frontend/src/features/records/api/dashboard.ts
    - frontend/src/features/records/api/weeklyReview.ts
    - frontend/src/features/records/components/RecordsPage.tsx
key-decisions:
  - "409 仅按 records confirmation 的既有 preference 合约作为幂等读取成功处理，不读取或覆盖其历史口径。"
  - "前端只序列化本地 Monday；用户统计窗口的权威判断仍留在 06-30 后端。"
patterns-established:
  - "统计前置条件：先确认 browser-proposed IANA zone，成功后才能启用 dashboard reads。"
  - "跨时区日历：不使用 toISOString、host-local getter 或固定 offset 来计算统计周。"
requirements-completed: [UI-02]
duration: 7min
completed: 2026-09-04
---

# Phase 6 Plan 31: H5 统计时区确认与本地周起点 Summary

**RecordsPage 现先确认浏览器 IANA 时区，再读取服务端权威投影，并用 `Intl.formatToParts()` 正确序列化跨时区的本地 Monday。**

## Performance

- **Duration:** 7min
- **Started:** 2026-09-04T09:27:00Z
- **Completed:** 2026-09-04T09:34:05Z
- **Tasks:** 2/2
- **Files modified:** 9

## Accomplishments

- 增加严格 confirmation DTO；200 解析安全响应，records 合约定义的 409 作为已有 preference 的幂等成功，其他失败保持可恢复。
- 移除 overview/history/weekly review query key 中的 browser timezone，公开 dashboard reads 不再传递 `time_zone`。
- RecordsPage 把 confirmation 作为 overview、history、weekly review 的 enable gate；失败时不伪造零数据或泄露内部错误。
- 新增 Shanghai 周一清晨、Los Angeles DST/UTC 跨日、200/409 gate 和确认失败闭合读取的 deterministic 前端回归测试。

## Task Commits

1. **Task 1: 建立严格的统计时区确认客户端，并让 dashboard query key 只反映服务端权威窗口** - `1f8e016` (feat)
2. **Task 2: 先确认口径再加载 Records，并以本地 calendar parts 生成 Monday** - `5e04a90` (fix)

## Files Created/Modified

- `frontend/src/features/records/api/client.ts` - records-owned timezone confirmation 的严格 JSON client。
- `frontend/src/features/records/api/dashboard.ts`、`weeklyReview.ts` - 只按实际 `weekStart`/cursor 缓存和请求，移除 browser zone。
- `frontend/src/features/records/components/RecordsPage.tsx` - confirmation gate、可恢复错误 UI 与 deterministic local Monday helper。
- `frontend/src/features/records/components/RecordsPage.test.tsx` - 跨时区边界和用户可见读取 gate 测试。
- `frontend/src/features/records/api/README.md`、`components/README.md` - 公共时区边界和文件索引。

## Decisions Made

- 浏览器 zone 可以作为 confirmation command 的非权威输入，但 dashboard/read client 不再将其当成数据切换参数或 cache key。
- 用显式 IANA `formatToParts()` 获取 local calendar date，并只对该无时区日历值做稳定算术，避免 UTC 字符串截断和 Vitest host-TZ 偶然性。

## TDD Evidence

- Task 1 先新增 confirmation/409 与 dashboard cache-key 红灯；实现 strict client 后转绿。
- Task 2 先新增 RecordsPage helper、confirmation gate 和失败关闭读取红灯；实现 gate 与 calendar helper 后转绿。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test correctness] 修正 Los Angeles DST 测试中错误的 UTC 边界 instant**
- **Found during:** Task 2
- **Issue:** 初始红灯把已进入 PDT 的 `2026-03-09T07:30:00Z` 误标为当地周日；实际它是当地周一 00:30。
- **Fix:** 使用真正的 UTC 跨日临界 `06:30Z` 验证上一周，并以 `07:30Z` 验证当地周一。
- **Files modified:** `frontend/src/features/records/components/RecordsPage.test.tsx`
- **Verification:** Shanghai、Los Angeles/DST 与组件 gate 测试共 10 项通过。
- **Committed in:** `5e04a90`

---

**Total deviations:** 1 auto-fixed（Rule 1 test correctness）。
**Impact on plan:** 仅修正测试事实，使 DST 覆盖真实有效；未扩展产品范围或依赖。

## Issues Encountered

- Task 1 移除旧 query key 参数后，未完成的 RecordsPage 立即被 TypeScript 检出为旧调用；按 Task 2 接线完成后恢复全绿，没有留下兼容旁路。
- Vite build 继续报告现有产物超过 500 kB 的建议性 warning；构建成功，且本计划不进行无关拆包重构。

## Known Stubs

None - 本计划修改的读取 gate、calendar helper 和错误 UI 均已连接真实公开 API，不依赖 placeholder 或 mock 数据。

## User Setup Required

None - 沿用现有浏览器时区和 records confirmation API，无新环境变量或外部配置。

## Next Phase Readiness

- 06-32 可消费 confirmation-first H5 合约，执行 guarded E2E 与真实内置浏览器验收。
- 真实浏览器验收由 06-32 负责；本计划只完成可测的客户端实现与构建门禁。

## Self-Check: PASSED

- 已确认 9 个计划相关文件存在，两个 task commit `1f8e016`、`5e04a90` 可从 Git 历史读取。
- 计划验证通过：`npm test -- --run src/features/records/components/RecordsPage.test.tsx src/features/records/api/client.test.ts src/features/records/api/dashboard.test.ts`（3 files / 10 tests）、`npm run typecheck`、`npm run build`。

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-04*
