---
phase: 06-user-dashboard-admin
plan: "09"
subsystem: dashboard-ui
tags: [fastapi, pydantic, react, zod, tanstack-query, vitest, playwright, weekly-review]
requires:
  - phase: 06-user-dashboard-admin
    provides: facts-first weekly-review cache and bounded safety graph
  - phase: 06-user-dashboard-admin
    provides: projection-only records H5 page shell and strict dashboard client patterns
provides:
  - closed safe weekly-review HTTP outcome contract
  - accessible Records H5 coverage, abstention, success, and retry states
  - authenticated low-coverage browser regression path
affects: [records-page, dashboard-api, weekly-review-cache, phase-06-browser-uat]
tech-stack:
  added: []
  patterns: [closed HTTP safety enum, strict Zod outcome DTO, cache-preserving retry mutation]
key-files:
  created: [backend/tests/unit/test_weekly_review_api.py, frontend/src/features/records/api/weeklyReview.ts, frontend/src/features/records/components/WeeklyReview.tsx, frontend/src/features/records/components/WeeklyReview.test.tsx, frontend/tests/e2e/records-weekly-review.spec.ts]
  modified: [backend/app/dashboard/api.py, backend/app/dashboard/schemas.py, backend/app/dashboard/service.py, frontend/src/features/records/components/RecordsPage.tsx]
key-decisions:
  - "HTTP exposes only insufficient_coverage, safety_abstain, success, and retryable_error; graph and provider codes never cross the trust boundary."
  - "Refresh retains the same versioned cache key and only becomes visible for retryable service outcomes; low coverage exits before graph invocation."
patterns-established:
  - "Dashboard API composes the bounded graph in its dependency factory while WeeklyReviewService maps result codes into a closed public DTO."
  - "Records H5 keeps weekly review at the end of the existing PageScrollArea and validates every response before rendering."
requirements-completed: [UI-02]
duration: 17min
completed: 2026-09-02
---

# Phase 06 Plan 09: Safe Weekly Review HTTP and H5 Summary

**周复盘现已通过严格公开 DTO 呈现覆盖事实、保守弃权、最多三条一般饮食参考与受限重试，不泄露 Provider、prompt、facts 原文或技术错误。**

## Performance

- **Duration:** 17 min
- **Started:** 2026-09-02T11:40:00Z
- **Completed:** 2026-09-02T11:57:13Z
- **Tasks:** 2/2
- **Files modified:** 15

## Accomplishments

- 增加 `/api/v1/dashboard/weekly-review` 与 `/refresh`：仅接受当前周或已结束周的周一，并通过 `extra=forbid` 的安全枚举返回范围、覆盖天数、餐数与确定性汇总。
- 接线既有 versioned cache 与 06-23 bounded graph；覆盖不足在图调用之前返回，未知和安全路径不显示建议，只有可重试服务故障显示“重新生成”。
- 在 `/app/records` 的历史记录之后新增语义化周复盘组件，保留既有单一滚动根、焦点与底部导航；客户端 Zod 拒绝额外/技术字段。
- 添加 HTTPX、Vitest 与真实注册→验证码→登录→记录页 Playwright 路径，验证低覆盖 API 响应不含内部字段且页面无重试操作。

## Verification

- `cd backend && uv run pytest tests/unit/test_weekly_review_api.py tests/dashboard/test_weekly_review_facts.py tests/dashboard/test_weekly_review_cache_service.py -q` — PASS（5 passed）。
- `cd backend && uv run ruff check app/dashboard/api.py app/dashboard/schemas.py app/dashboard/service.py tests/unit/test_weekly_review_api.py` — PASS。
- `cd frontend && npm test -- --run src/features/records/components/WeeklyReview.test.tsx` — PASS（5 passed）。
- `cd frontend && npm run typecheck && npm run build` — PASS；构建仅报告既有的大于 500 kB chunk 警告。
- `cd frontend && E2E_FRONTEND_PORT=5181 E2E_BACKEND_PORT=8011 npm run test:e2e -- --grep records-weekly-review` — PASS（1 passed）。默认 8000 端口已有未知进程，测试拒绝复用；改用隔离备用端口，未触碰该进程。
- 内置浏览器验收未完成：macOS 处于锁屏，自动解锁失败，无法在可见浏览器重复真实注册登录路径。未伪造 token、会话或数据库数据；Playwright 已覆盖实际公开 API 路径。

## Task Commits

1. **Task 1: 写复盘 HTTP 与三状态 H5 RED 测试** — `c0901c4` (`test`)
2. **Task 2: 接线端点和可访问周复盘组件** — `44dfecb` (`feat`)

## Files Created/Modified

- `backend/app/dashboard/{api.py,schemas.py,service.py}` — 安全公共投影、周边界、cache-preserving graph 编排和枚举映射。
- `frontend/src/features/records/api/weeklyReview.ts` — strict Zod DTO、请求函数与带时区/周的 Query key。
- `frontend/src/features/records/components/{WeeklyReview.tsx,RecordsPage.tsx}` — 周范围、客观汇总、互斥状态、固定免责声明和仅 retryable 的 mutation。
- `backend/tests/unit/test_weekly_review_api.py`、`frontend/src/features/records/components/WeeklyReview.test.tsx`、`frontend/tests/e2e/records-weekly-review.spec.ts` — HTTP、组件与真实登录跨栈证据。

## Decisions Made

- 周复盘的 Provider/graph failure code 不进入 HTTP；客户端只能接收四个用户可理解的 closed outcome，防止技术详情被渲染或误解。
- “重新生成”不清除或绕过 cache key；低覆盖和安全弃权没有按钮，避免把不足事实或不确定结果重新提交给模型。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] 在 Dashboard Service 增加安全公共投影映射**
- **Found during:** Task 2
- **Issue:** 06-07 的 cache service 仍使用旧式字符串 Provider，06-23 的 bounded graph 尚未接入 HTTP；若在路由直接拼装，会违反 API → Service 边界且无法安全区分 retryable 与弃权。
- **Fix:** 为既有 `WeeklyReviewService` 增加 graph-result 到 closed public DTO 的映射；API 仅做认证、周输入校验与依赖装配。
- **Files modified:** `backend/app/dashboard/service.py`, `backend/app/dashboard/api.py`, `backend/app/dashboard/schemas.py`。
- **Verification:** HTTPX 5 项、Ruff、实际 FastAPI/Playwright 公开路径通过。
- **Committed in:** `44dfecb`。

**2. [Rule 1 - Bug] 修正 E2E 中不共享浏览器内存 access token 的请求方式**
- **Found during:** Task 2
- **Issue:** Playwright 的独立 `page.request` 与 H5 的 runtime-only access token 不共享，直接调用公开 API 收到 401，不能证明真实页面路径。
- **Fix:** 监听登录后 RecordsPage 自身已认证请求的公开 API 响应；保留真实页面注册、验证码、登录与路由。
- **Files modified:** `frontend/tests/e2e/records-weekly-review.spec.ts`。
- **Verification:** 隔离 PostgreSQL/Mailpit/FastAPI/Vite 下 E2E 通过。
- **Committed in:** `44dfecb`。

---

**Total deviations:** 2 auto-fixed（Rule 1: 1，Rule 2: 1）。
**Impact on plan:** 两项均维持既定架构、安全边界与真实认证证据；未增加依赖或产品范围。

## Issues Encountered

- 默认 E2E 端口 `8000` 被未知现有 Python 进程占用。配置正确拒绝复用，故以 `8011/5181` 运行完全隔离的测试环境。
- 内置浏览器被 macOS 锁屏阻断；此项明确保留为人工浏览器验收，不将 E2E 冒充为可见浏览器验收。

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 后续工作可复用 closed weekly-review HTTP contract；真实可见浏览器验收仍需在主机解锁后，从真实登录进入 `/app/records` 复核低覆盖卡片。
- `OUTCOME_UNKNOWN` 不可重放；后续不得把它改为可重试按钮或向 H5 暴露技术代码。

## Self-Check: PASSED

- Confirmed `frontend/src/features/records/api/weeklyReview.ts` and `frontend/src/features/records/components/WeeklyReview.tsx` exist.
- Confirmed `c0901c4` and `44dfecb` exist in Git history.

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-02*
