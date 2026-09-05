---
phase: 06-user-dashboard-admin
plan: 34
subsystem: api
tags: [fastapi, dashboard, zoneinfo, timezone, pytest, ruff]
requires:
  - phase: 06-33
    provides: "records-owned statistical-timezone confirmation with safe replay and invalid-IANA rejection"
provides:
  - "服务端由已确认 preference 定义 overview 与默认 weekly-review 的当前本地周"
  - "显式 weekly-review 仅接受已结束本地 Monday，GET 与 refresh 共用同一边界"
  - "DashboardTimezoneReadPort 的准确中文教学与目录索引"
affects: [06-35, 06-36, dashboard, records]
tech-stack:
  added: []
  patterns:
    - "current read window 在 Service 通过 tenant-scoped DashboardTimezoneReadPort 和 injected aware clock 推导"
    - "explicit weekly history 由同一 Service helper 在 facts/cache/Provider 前拒绝 current、future 与非 Monday"
key-files:
  created: []
  modified:
    - backend/app/dashboard/service.py
    - backend/app/dashboard/api.py
    - backend/tests/dashboard/test_dashboard_service.py
    - backend/tests/unit/test_dashboard_api.py
    - backend/tests/unit/test_weekly_review_api.py
    - docs/learning/06-dashboard-admin.md
key-decisions:
  - "overview 移除 week_start 服务签名；未声明的浏览器 query 不参与 current aggregate 范围。"
  - "weekly-review 省略 week_start 才表示当前周；显式参数只表示已结束的历史周。"
patterns-established:
  - "DashboardRepository Protocol 继承 DashboardTimezoneReadPort，避免重复和漂移 records-owned preference 的读取契约。"
requirements-completed: [UI-02, EDU-03]
duration: 18min
completed: 2026-09-05
---

# Phase 6 Plan 34: 服务端统计时区当前窗口 Summary

**Dashboard 当前 overview 与默认周复盘现在只由已确认统计时区和注入时钟定义，浏览器不能改写当前周。**

## Performance

- **Duration:** 18 min
- **Started:** 2026-09-05T10:03:00+08:00
- **Completed:** 2026-09-05T10:21:00+08:00
- **Tasks:** 2/2
- **Files modified:** 13

## Accomplishments

- 删除 overview 的 caller-selected `week_start`，Service 只按 preference-local today/current Monday 聚合七天。
- 无参数 weekly GET/refresh 仍读取当前周；显式 current、future 或非 Monday 在 facts、cache 和 Provider 前统一返回 422，已结束 Monday 保持可读。
- 用 fake-service 与 HTTP 合约覆盖 preference-local week、浏览器范围无效、current/history 分界以及 409 fail-closed，并同步 dashboard/test README。
- 教学材料准确改用 `DashboardTimezoneReadPort`，说明 records 写入与 dashboard consumer-owned 只读边界。

## Task Commits

1. **Task 1: 让当前 dashboard 完全以 preference 定义，并收紧 weekly history 域规则** - `cecb675` (test), `d9e3d0b` (fix)
2. **Task 2: 修正 DashboardTimezoneReadPort 教学与真实 current/history 契约** - `a9e7734` (docs)

## Files Created/Modified

- `backend/app/dashboard/service.py` - 以 `DashboardTimezoneReadPort` 派生当前周，并统一验证显式历史周。
- `backend/app/dashboard/api.py` - overview 不再传递浏览器范围；weekly 公开 422 语义匹配 completed-only 规则。
- `backend/tests/dashboard/test_dashboard_service.py`、`test_weekly_review_facts.py` - 覆盖本地当前窗口与 explicit-current 拒绝。
- `backend/tests/unit/test_dashboard_api.py`、`test_weekly_review_api.py` - 覆盖 HTTP 忽略 overview query 与 GET/refresh 历史边界。
- `backend/app/README.md`、`backend/app/dashboard/README.md`、`backend/tests/**/README.md` - 同步模块职责和测试索引。
- `docs/learning/06-dashboard-admin.md`、`docs/learning/README.md` - 校正 Port 名称、边界与教学索引。

## Decisions Made

- 当前窗口从公开读取参数中移除；FastAPI 对未声明 query 保持兼容性忽略，但它绝不能到达聚合 Service。
- 当前周只由省略 `week_start` 表示；任何显式值都被当成历史请求并必须是已结束的本地 Monday。

## Verification

- `cd backend && uv run pytest tests/dashboard/test_dashboard_service.py tests/dashboard/test_weekly_review_facts.py tests/unit/test_dashboard_api.py tests/unit/test_weekly_review_api.py -q` — **18 passed**。
- `cd backend && uv run ruff check app/dashboard tests/dashboard tests/unit/test_dashboard_api.py tests/unit/test_weekly_review_api.py` — **All checks passed**。
- `rg -n "DashboardTimezonePort|DashboardTimezoneReadPort|week_start" docs/learning/06-dashboard-admin.md docs/learning/README.md`，并确认旧 `DashboardTimezonePort` 为零处 — **passed**。
- `git diff --check` — **passed**。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test correctness] 修正 stub dependency override 的 callable 形状**
- **Found during:** Task 1
- **Issue:** 新增可注入 Dashboard stub 时，FastAPI dependency override 必须是返回 stub 的 callable；直接提供实例会在 dependency introspection 失败。
- **Fix:** 用零参数 lambda 返回显式 stub。
- **Files modified:** `backend/tests/unit/test_dashboard_api.py`
- **Verification:** 红灯阶段只剩生产契约缺口；绿灯阶段 18 项目标测试通过。
- **Committed in:** `cecb675`

---

**Total deviations:** 1 auto-fixed（Rule 1 - test correctness）。
**Impact on plan:** 只使 HTTP 合约测试正确连接 dependency override；没有扩展接口、schema、依赖或数据范围。

## Issues Encountered

- 受限沙箱不能读取项目现有 uv 缓存；获授权后使用同一缓存运行测试，未安装或下载依赖。

## Known Stubs

None - current-window、历史周验证和文档均连接现有 Service/API，没有空数据或 placeholder 代替行为。

## User Setup Required

None - 不需要新增环境变量、密钥、迁移或外部服务配置。

## Next Phase Readiness

- 06-35 可以安全移除 H5 的浏览器范围控制，因为服务端不再接受它作为 current-window authority。
- 06-36 可在公开 API/E2E 和真实浏览器路径中验证跨时区一致性；仍须由该计划执行其指定的浏览器验收。

## Self-Check: PASSED

- 已确认关键源码、四份测试、目录 README 与两份学习文档均存在。
- `cecb675`、`d9e3d0b` 与 `a9e7734` 均可从 Git 历史读取。
- 已扫描本计划修改文件，未发现会阻塞目标的 placeholder、TODO、FIXME 或空数据 stub。

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-05*
