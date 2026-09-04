---
phase: 06-user-dashboard-admin
plan: 30
subsystem: api
tags: [fastapi, sqlalchemy, postgresql, zoneinfo, dashboard, weekly-review]
requires:
  - phase: 06-29
    provides: "已验证的 records/dashboard 公开链路与当前 Phase 6 缺口报告"
provides:
  - "records-owned 已确认统计时区的 tenant-scoped dashboard 只读投影"
  - "由 ZoneInfo 和 aware injected clock 定义的用户本地 overview 与 weekly-review 窗口"
  - "无效或缺失时区的 fail-closed 409，以及用户本地 Monday 的 422 校验"
affects: [06-31, 06-32, frontend-records, dashboard-api]
tech-stack:
  added: []
  patterns:
    - "dashboard 通过最小只读 Port 消费 records-owned preference，不写入也不猜测历史口径"
    - "Service 在 aggregate、facts、cache 或 Provider 工作前将 aware UTC instant 转为已验证 IANA 本地日期"
key-files:
  created: []
  modified:
    - backend/app/dashboard/ports.py
    - backend/app/dashboard/repository.py
    - backend/app/dashboard/service.py
    - backend/app/dashboard/api.py
    - backend/tests/integration/test_dashboard_repository.py
key-decisions:
  - "统计时区唯一来自 records 一次确认的 preference；Dashboard 不接受 query/header/browser 值作为权威来源。"
  - "缺失或无法用 ZoneInfo 解析的持久化值统一映射为无内部细节的 409，而不是回退 UTC。"
  - "weekly-review 的 Monday/current-week 规则归 Service，API 只映射 409/422。"
patterns-established:
  - "用户本地统计窗口：先读取 tenant-scoped preference，再 ZoneInfo 复验并将注入的 aware instant astimezone。"
  - "跨模块偏好所有权：records 负责确认/写入和审计，dashboard 只持有 consumer-owned read Port。"
requirements-completed: [UI-02]
duration: 9min
completed: 2026-09-04
---

# Phase 6 Plan 30: 用户统计时区窗口 Summary

**已确认 IANA 统计时区现在驱动 dashboard 的今日、自然周和 weekly review，使服务端部署时区不再决定用户统计结果。**

## Performance

- **Duration:** 9min
- **Started:** 2026-09-04T09:16:27Z
- **Completed:** 2026-09-04T09:25:27Z
- **Tasks:** 2/2
- **Files modified:** 13

## Accomplishments

- 增加 records-owned `DashboardTimezonePreference` 的 dashboard 只读 Port 和 `user_id` scoped SQL projection；缺失行保持 `None`，不伪造 UTC。
- `DashboardService` 与 `WeeklyReviewService` 使用相同的 ZoneInfo local-today/Monday 规则，并在聚合、facts、cache 或 Provider 前 fail closed。
- 公开 overview、weekly GET 和 refresh 将统计口径前置条件映射为安全 409；非周一或未来周一以该用户本地周窗口稳定映射为 422。
- 覆盖 Shanghai、Los Angeles、DST、UTC 跨日、跨租户 preference、损坏 IANA 和既有目标投影/缓存回归。

## Task Commits

1. **Task 1: 定义 dashboard 的只读统计时区边界，并从已确认 preference 做 tenant-scoped 投影** - `7ac1d33` (feat)
2. **Task 2: 用同一个 validated IANA zone 驱动 overview、weekly review 与本地 Monday HTTP 校验** - `ab28461` (fix)
3. **Task 2 follow-up: 完整拒绝所有无效 ZoneInfo key** - `2922c66` (fix)

## Files Created/Modified

- `backend/app/dashboard/ports.py` - records-owned 已确认统计时区的最小只读 contract。
- `backend/app/dashboard/repository.py` - tenant-scoped preference projection，保留原有餐食聚合过滤条件。
- `backend/app/dashboard/service.py` - ZoneInfo 本地日期/周窗口和 domain-level precondition/validation 规则。
- `backend/app/dashboard/api.py` - 安全的 409/422 HTTP 映射，并把同一 local today 传入 graph facts。
- `backend/tests/dashboard/` 与 `backend/tests/unit/` - DST、UTC 边界、前置条件和 API 合约回归。
- `backend/tests/integration/` - PostgreSQL preference 隔离与既有 overview target projection 回归。
- `backend/app/README.md`、`backend/app/dashboard/README.md` - records preference 所有权和 dashboard 分层职责索引。

## Decisions Made

- Dashboard 只读取 records 模块一次确认的 IANA preference；它不从任一 `MealRecord` 推测当前口径，也不提供写入入口。
- 服务层而非 API 决定 current Monday 与 completed-week 合法性，以保证 overview、weekly facts 和 graph facts 同一用户的时间语义一致。
- 损坏持久化时区与缺失 preference 都必须中止于确定性、无泄露的前置条件，不能以服务器 UTC 保底。

## TDD Evidence

- Task 1 的 PostgreSQL 红灯先确认 repository 尚无 `get_dashboard_timezone_for_user`，随后实现并转绿。
- Task 2 的服务测试先因缺少 `DashboardTimezonePreconditionError` 导入失败，随后实现 ZoneInfo 规则并转绿。
- 红灯与实现按任务原子提交；没有制造不可验证的空测试提交。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] 更新受影响的既有 dashboard 测试替身以实现新的 read Port**
- **Found during:** Task 2（service contract 回归）
- **Issue:** `test_weekly_review_cache_service.py` 的 fake repository 与 `test_dashboard_overview_projection.py` 的真实 fixture 没有创建已确认 preference；新 fail-closed 合约会让它们在被测业务之前失败。
- **Fix:** fake repository 提供已确认 `Asia/Shanghai`，PostgreSQL target-projection fixture 为两个测试用户创建既有 preference。
- **Files modified:** `backend/tests/dashboard/test_weekly_review_cache_service.py`、`backend/tests/integration/test_dashboard_overview_projection.py`
- **Verification:** dashboard 服务回归 32 passed；受影响 PostgreSQL integration 4 passed。
- **Committed in:** `ab28461`

**2. [Rule 1 - Security bug] 将 ZoneInfo 的绝对路径 ValueError 纳入 fail-closed 分支**
- **Found during:** Task 2 提交后安全边界审查
- **Issue:** `ZoneInfo` 对绝对路径形式的损坏 key 抛出 `ValueError`；只捕获不存在/类型错误会让该持久化损坏值产生 500。
- **Fix:** Service 和 HTTP/API regression fixtures 同时捕获 `ValueError`，并新增 `/invalid-timezone` 覆盖。
- **Files modified:** `backend/app/dashboard/service.py`、dashboard service/API tests
- **Verification:** 完整时区回归 15 passed、PostgreSQL integration 4 passed、Ruff passed。
- **Committed in:** `2922c66`

---

**Total deviations:** 2 auto-fixed（Rule 1 security bug、Rule 3 blocking）。
**Impact on plan:** 修复仅使 fail-closed 对所有 ZoneInfo 异常完整生效，并让既有 fixtures 显式满足新的安全前置条件；未扩展产品范围、未新增 schema 或依赖。

## Issues Encountered

- 初次运行 guarded PostgreSQL 测试时 sandbox 无权读取现有 uv cache；获得授权后测试正常执行。没有安装、替换或新增任何依赖。
- FastAPI/Starlette 对现有 `HTTP_422_UNPROCESSABLE_ENTITY` 给出 deprecation warning；计划要求此稳定常量且现有契约仍依赖它，因此未做无关框架重构。

## Known Stubs

None - 本计划修改的生产路径不以空值、placeholder 或 mock 数据承载用户统计结果。

## User Setup Required

None - 沿用 records 已有的统计时区确认流程，无新环境变量或外部服务配置。

## Next Phase Readiness

- 06-31 可基于已确认 preference 的公开 409/422 合约，修复浏览器端 Monday 序列化与跨栈 E2E。
- 06-32 可在用户真实浏览器路径中验证 H5 展示和文档证据；本计划不操作浏览器。

## Self-Check: PASSED

- 已确认 13 个计划相关生产/测试/文档文件存在，Task commits `7ac1d33`、`ab28461` 均可从 Git 历史读取。
- 计划规定验证通过：15 个 service/API 测试、3 个 PostgreSQL repository 测试与 Ruff；额外受影响 PostgreSQL overview projection 回归通过（合计 4 个 integration tests）。

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-04*
