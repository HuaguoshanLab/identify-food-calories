---
phase: 05-diet-planning-subgraph
plan: "05"
subsystem: ui
tags: [react, typescript, tanstack-query, zod, h5, profile]
requires:
  - phase: 05-03
    provides: validated planning profile DTOs and the public authenticated request boundary
  - phase: 05-07
    provides: owner-scoped `/api/v1/planning/profile` CRUD contract
provides:
  - protected DetailLayout route for personal profile view, edit, empty, and deletion states
  - explicit validated profile PUT/DELETE client with cache invalidation after deletion
  - a single personal-profile entry from 我的 while memory remains the preference authority
affects: [05-06, 05-09, profile, planning-prefill, h5-settings]
tech-stack:
  added: []
  patterns: [validated public profile CRUD client, shared planning-profile query key, DetailLayout settings route]
key-files:
  created: [frontend/src/features/plans/api/profile.ts, frontend/src/features/plans/components/PersonalProfilePage.tsx]
  modified: [frontend/src/App.tsx, frontend/src/routePaths.ts, frontend/src/app/MePage.tsx]
key-decisions:
  - "Profile and planning prefill share the `planning-profile` query key, so mutation success cannot leave a stale body/goal snapshot."
  - "Preferences remain a link to the existing memory page; this profile UI exposes no preference fields or mutations."
patterns-established:
  - "Profile mutations parse closed Zod DTOs before calling the authenticated public API."
  - "Destructive profile deletion sets cached profile data to null, invalidates dependent planning queries, then returns focus to the DetailLayout h1."
requirements-completed: [PLN-01, PLN-06]
duration: 9min
completed: 2026-09-01
---

# Phase 5 Plan 05: 个人资料详情路由、编辑与删除 Summary

**受保护的个人资料 DetailLayout，提供显式身体资料/目标编辑、不可逆删除与无陈旧预填缓存的公开 CRUD 边界。**

## Performance

- **Duration:** 9 min
- **Started:** 2026-09-01T08:55:00Z
- **Completed:** 2026-09-01T09:03:45Z
- **Tasks:** 2/2
- **Files modified:** 12

## Accomplishments

- 新增 `/app/me/profile` 受保护路由，并通过 `DetailLayout title="个人资料"` 呈现，无 Tab bar。
- 资料页可查看、编辑和删除最小 body/goal 数据；删除采用精确 D-18 文案、确认操作和 h1 焦点回归。
- `profile.ts` 对公开 API 做 Zod 校验；删除时同步清空并失效 profile/规划预填缓存，偏好始终只链接既有 memory 页。

## Task Commits

1. **Task 1: 写资料路由、删除与偏好职责分离的 RED 合同** - `81a0656` (`test`)
2. **Task 2: 实现个人资料详情、路由和显式 CRUD client** - `1343514` (`feat`)

## Files Created/Modified

- `frontend/src/features/plans/api/profile.ts` - 认证 profile GET/PUT/DELETE、Zod 写入 DTO、结构化错误与共享 Query key。
- `frontend/src/features/plans/components/PersonalProfilePage.tsx` - 查看、空态、RHF/Zod 编辑和安全删除的 DetailLayout 内容。
- `frontend/src/App.tsx`、`frontend/src/routePaths.ts`、`frontend/src/app/MePage.tsx` - 集中路由和唯一个人资料 SettingsLinkRow。
- `frontend/src/features/plans/components/PersonalProfilePage.test.tsx`、`frontend/src/App.test.tsx`、`frontend/tests/e2e/profile.spec.ts` - 组件、路由和后续公开 E2E 合同。

## Decisions Made

- Profile 与规划预填共用 `['planning-profile']`；保存写回并失效该键，删除设为 `null` 后再失效该键和规划查询，避免 H5 从缓存复活已删除资料。
- 忌口和口味不进入资料表单或 mutation；资料页只提供通往 `/app/me/memories` 的真实链接。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 修正新增资料入口后的旧设置链接断言**
- **Found during:** Task 2
- **Issue:** 既有测试把“我的”设置列表固定为两个入口；新增计划要求的唯一个人资料行后，该断言会错误失败。
- **Fix:** 更新测试为四个完整入口，并断言个人资料和 memory 的路由职责。
- **Files modified:** `frontend/src/app/AppPages.test.tsx`
- **Verification:** targeted Vitest 16/16 passed。
- **Committed in:** `1343514`

**2. [Rule 1 - Bug] 修正 204 删除测试响应构造**
- **Found during:** Task 2
- **Issue:** 测试 mock 为 HTTP 204 创建了空字符串响应体；Fetch 标准禁止 204 带 body，导致删除路径误报失败。
- **Fix:** 使用 `null` body 的 204 Response，使测试模拟真实 API 语义。
- **Files modified:** `frontend/src/features/plans/components/PersonalProfilePage.test.tsx`
- **Verification:** profile 删除、空态和 cache contract tests passed。
- **Committed in:** `1343514`

**3. [Rule 2 - Missing Critical] 同步 plans API 与 components 目录索引**
- **Found during:** Task 2
- **Issue:** 根级 AGENTS.md 要求目录文件变化时同步维护索引；新增 profile client/page 若未登记会破坏目录职责审计。
- **Fix:** 更新 API 与 components README 文件索引及职责描述。
- **Files modified:** `frontend/src/features/plans/api/README.md`, `frontend/src/features/plans/components/README.md`
- **Verification:** README 列出新增实现文件，typecheck/lint passed。
- **Committed in:** `1343514`

---

**Total deviations:** 3 auto-fixed (2 Rule 1 bugs, 1 Rule 2 documentation requirement).
**Impact on plan:** 必要的测试、标准语义和目录合同修复；未扩大产品范围。

## Issues Encountered

完整公开浏览器路径要先由 Plan 09 把 `/app/plans` 从占位页接入资料复核和餐单流；Plan 06 已明确负责在该集成完成后运行 Playwright 与 Codex 内置浏览器。本计划未把占位页伪装成可验收路径。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 09 可直接复用 `api/profile.ts` 的 `getPlanningProfile` 与 `planningProfileQueryKey` 完成只读预填。
- Plan 06 应执行 `profile.spec.ts` 的公开注册→Mailpit→登录→编辑→删除路径，并完成真实浏览器验收。

## Self-Check: PASSED

- `frontend/src/features/plans/components/PersonalProfilePage.tsx` and `frontend/src/features/plans/api/profile.ts` exist.
- Commits `81a0656` and `1343514` exist in Git history.
- `npm run typecheck`, `npm run lint`, and the targeted 16-test Vitest suite passed.

---
*Phase: 05-diet-planning-subgraph*
*Completed: 2026-09-01*
