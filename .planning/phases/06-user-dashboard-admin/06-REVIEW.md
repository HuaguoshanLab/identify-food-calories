---
phase: 06-user-dashboard-admin
reviewed: 2026-09-04T09:50:49Z
depth: standard
files_reviewed: 25
files_reviewed_list:
  - backend/app/dashboard/ports.py
  - backend/app/dashboard/repository.py
  - backend/app/dashboard/service.py
  - backend/app/dashboard/api.py
  - backend/app/records/api.py
  - backend/app/records/service.py
  - backend/tests/dashboard/test_dashboard_service.py
  - backend/tests/dashboard/test_weekly_review_facts.py
  - backend/tests/unit/test_dashboard_api.py
  - backend/tests/unit/test_weekly_review_api.py
  - backend/tests/integration/test_dashboard_repository.py
  - backend/tests/integration/test_dashboard_overview_projection.py
  - frontend/src/features/records/api/client.ts
  - frontend/src/features/records/api/dashboard.ts
  - frontend/src/features/records/api/weeklyReview.ts
  - frontend/src/features/records/components/RecordsPage.tsx
  - frontend/src/features/records/api/client.test.ts
  - frontend/src/features/records/api/dashboard.test.ts
  - frontend/src/features/records/components/RecordsPage.test.tsx
  - frontend/tests/e2e/records-dashboard.spec.ts
  - frontend/tests/e2e/records-weekly-review.spec.ts
  - frontend/playwright.config.ts
  - README.md
  - docs/learning/06-dashboard-admin.md
  - docs/verification/phase-06-browser-acceptance.md
findings:
  critical: 1
  warning: 1
  info: 1
  total: 3
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-09-04T09:50:49Z  
**Depth:** standard  
**Files Reviewed:** 25  
**Status:** issues_found

## Summary

审查覆盖 06-30/31/32 的时区 source-of-truth、确认门控、React Query、两条 guarded Playwright 路径和证据文档，并追踪到 records 的确认 API。E2E 没有发现直写数据库、注入 token/Cookie 或 mock API 的捷径；dashboard repository 的 preference 查询也按 `user_id` 隔离。

但当前实现把“已确认统计时区”在第二次打开 Records 时重新交给浏览器时区决定，直接破坏本轮刚建立的 server-authoritative 窗口。另有 records 的 `ZoneInfo` 异常漏网，恶意/损坏 IANA key 会得到 500 而非受控 400。

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: 已确认的统计时区会被浏览器周起点覆盖

**Classification:** BLOCKER  
**Files:** `frontend/src/features/records/api/client.ts:50`, `frontend/src/features/records/components/RecordsPage.tsx:70-71`, `frontend/src/features/records/components/RecordsPage.tsx:86-89`, `backend/app/dashboard/api.py:85-89`, `backend/app/dashboard/service.py:98-100`

**Issue:** `dashboard-time-zone-confirmations` 是一次性命令；已有 preference 时后端固定返回 409。客户端把任意 409 变为 `null` 成功（`client.ts:50`），却继续用当前浏览器时区派生 `weekStart`，并将它作为 `overview` 与当前 `weekly-review` 的 query/key 参数。服务端 `get_overview()` 不校验该参数是否等于已确认 preference 下的当前周，直接把它作为聚合窗口。

用户首次以 `Asia/Shanghai` 确认、随后在 `America/Los_Angeles` 浏览器打开 Records 时，409 会放行；在两个时区跨周边界，页面就会用 LA 的周一请求，而服务端 `today` 仍按 Shanghai 返回。结果可能是“今日摘要”不属于趋势的七天窗口；客户端也可以通过 URL 选择任意 overview 周。这与“后端 preference 是唯一统计口径、浏览器不能成为 read authority”的 06-30/31 契约矛盾。现有 409 测试只断言“能继续读取”，没有覆盖 confirmed zone 与 browser zone 不同的情形。

**Fix:** 当前 Records 只需要“本周”时，不要让浏览器提交 `week_start`：overview/current weekly-review 应由服务端根据持久 preference 选定窗口，且其 Query key 使用稳定的 current-window key。若产品确实需要历史周，服务端必须明确区分该功能，并对可选周进行 domain validation。

同时把确认接口改为让前端能可靠获得已确认的安全 timezone（例如已确认同值时返回 200 的 `DashboardTimezoneConfirmationResponse`，不同值返回显式冲突；或增加受认证、只返回该用户 timezone 的只读 projection）。前端只能使用服务端返回的 zone 做显示或本地日期辅助，不能以当前 browser zone 覆盖它。补充在同一 UTC instant 下“stored Shanghai + browser LA”与反向组合的组件/API/E2E 回归，断言 today 始终位于 overview 的 week，且当前 overview/review 请求不含浏览器推导的范围。

## Warnings

### WR-01: Records 的绝对路径 IANA key 未被转换为 400

**Classification:** WARNING  
**Files:** `backend/app/records/service.py:201-205`, `backend/app/records/api.py:50-58`, `backend/app/records/api.py:77-85`, `backend/app/records/api.py:96-108`

**Issue:** 06-30 已在 dashboard service 捕获 `ZoneInfo` 的 `ValueError`（绝对路径 key 会触发它），但 records 的共用 `_validated_time_zone()` 只捕获 `TypeError` 和 `ZoneInfoNotFoundError`。因此经过 schema 长度校验的 `"/invalid-timezone"` 在确认餐食、编辑餐食或确认 dashboard timezone 时会逃出 `InvalidTimeZone` 映射，变成未处理 500。

**Fix:** 与 dashboard 相同，捕获 `(TypeError, ValueError, ZoneInfoNotFoundError)` 并统一抛出 `InvalidTimeZone`。给三个公开 records command 至少增加绝对路径 key 的 API 契约，断言 400、无记录/偏好写入且无异常详情泄露。

## Info

### IN-01: 教学文档引用了不存在的 Port 名称

**Classification:** INFO  
**File:** `docs/learning/06-dashboard-admin.md:19`

**Issue:** 文档称 dashboard 通过 `DashboardTimezonePort` 读取 preference；实际 public contract 名称为 `DashboardTimezoneReadPort`。这会让读者和后续实现者寻找不存在的接口。

**Fix:** 将文档名更新为 `DashboardTimezoneReadPort`，并继续说明它是 dashboard consumer-owned read boundary。

---

_Reviewed: 2026-09-04T09:50:49Z_  
_Reviewer: gsd-code-reviewer_  
_Depth: standard_
