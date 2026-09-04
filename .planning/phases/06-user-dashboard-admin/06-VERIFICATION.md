---
phase: 06-user-dashboard-admin
verified: 2026-09-04T10:05:00Z
status: gaps_found
score: 4/5 roadmap must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/5 roadmap must-haves verified
  gaps_closed:
    - "服务端以 records-owned、ZoneInfo 验证的 preference 计算本地 today 和 weekly-review 的本地 Monday。"
    - "上海周一凌晨 UTC 序列化错误已由 formatToParts 的本地日历算法覆盖。"
    - "README 和教学文档不再错误声称 Records/admin Playwright 资产缺失；真实浏览器验收已记录。"
  gaps_remaining:
    - "已有 preference 的 409 路径仍让当前浏览器推导的 week_start 定义 overview/review 窗口，破坏服务端统计时区唯一真相。"
    - "Records 的 absolute-path ZoneInfo key 未映射为受控 400，而会泄露为 500。"
  regressions: []
gaps:
  - truth: "用户可按已确认的统计时区一致地查看今日、本周摄入、趋势和周复盘。"
    status: failed
    reason: "RecordsPage 将确认接口的 409 作为读取成功后，仍从当前浏览器时区生成 week_start；DashboardService.get_overview 直接信任该参数，不验证它是否是持久 preference 下的当前本地周。跨时区/跨周打开会使 today 与趋势/复盘窗口不一致。"
    artifacts:
      - path: "frontend/src/features/records/api/client.ts"
        issue: "confirmDashboardTimeZone 对任何 409 返回 null，未获得或比对已确认的服务端统计时区。"
      - path: "frontend/src/features/records/components/RecordsPage.tsx"
        issue: "确认成功或 409 后以 browserTimeZone() 生成 weekStart，并把它传给 overview、weekly review 和 refresh。"
      - path: "backend/app/dashboard/service.py"
        issue: "get_overview 的 week_start 参数未限制为 preference 下的 current Monday；可被客户端任意 Monday 改写本周趋势。"
      - path: "backend/app/dashboard/api.py"
        issue: "公开 overview 合约保留了未受本地当前周约束的 week_start 输入。"
    missing:
      - "将当前 overview/current weekly-review 的窗口完全收归服务端持久 preference；移除客户端 current-week week_start authority，或为历史周提供显式、受域规则验证的独立合约。"
      - "确认 API 必须让前端可靠得到同一已确认 preference（同值幂等成功或受认证只读投影），不同 browser zone 必须显式冲突且不得放行覆盖。"
      - "增加 stored Asia/Shanghai + browser America/Los_Angeles 及反向组合的组件/API/E2E 回归，断言 today 一定落在 overview week 中，且当前窗口请求不携带浏览器派生范围。"
  - truth: "无效的 IANA 时区输入经公开 Records API 安全失败，不暴露异常或留下部分写入。"
    status: partial
    reason: "records service 的 _validated_time_zone 未捕获 ZoneInfo 的 ValueError。'/invalid-timezone' 和 '../etc/passwd' 会从服务层逃逸，三个 API handler 不能转换为既定 400。"
    artifacts:
      - path: "backend/app/records/service.py"
        issue: "仅捕获 TypeError 和 ZoneInfoNotFoundError，漏掉 ZoneInfo 对 absolute/非规范相对路径抛出的 ValueError。"
    missing:
      - "捕获 ValueError 并统一抛出 InvalidTimeZone；为 meal confirm、edit 与 dashboard timezone confirmation 的绝对路径 key 增加 400、无写入、无异常详情 API 回归。"
---

# Phase 06：用户看板与后台管理验证报告

**阶段目标：** 用户看懂历史摄入趋势，管理员可以安全维护 Agent 所依赖的数据和配置。

**验证时间：** 2026-09-04T10:05:00Z

**状态：** `gaps_found`
**复验：** 是——复核 06-30、06-31、06-32 后的最终实现。

## 验证范围与方法

读取了根、backend、frontend、admin-frontend 的 `AGENTS.md`，Phase 06 的 PLAN/SUMMARY 元数据和关键任务、`06-CONTEXT.md`、`REQUIREMENTS.md`、`ROADMAP.md`、前一份验证报告及新增 `06-REVIEW.md`。不采信 SUMMARY 自述，直接审查 dashboard/records/API/React/E2E 源码和测试。

本阶段 ROADMAP 虽标为 MVP，但目标不是有效的用户故事格式；因此按五条 ROADMAP Success Criteria 做目标倒推，而不伪造 User Flow Coverage。

## Goal Achievement

### Observable Truths

| # | Truth | Status | 直接证据 |
| --- | --- | --- | --- |
| 1 | 用户可在其已确认统计时区下查看一致的今日、本周、历史、趋势与周复盘。 | ✗ FAILED | `DashboardService` 现在正确用 preference + `ZoneInfo` 得到 local today，但 `get_overview(..., week_start)` 直接使用客户端 week_start。`RecordsPage` 在确认 409 后仍以当前 browser zone 推导并传入该参数；跨时区跨周时 today 可不在 week 内。 |
| 2 | 独立后台仅调用 `/api/v1/admin/*`；普通用户无法读取/修改后台数据，用户 H5 不含后台页面。 | ✓ VERIFIED | 独立 `admin-frontend/`、受限 API base、memory-only token 与 `AdminRouteGuard` 存在；guarded `admin-management` E2E 观察 RuntimeConfig `201`、目录命令 `200`、普通用户 probe `403`。catalog 四个 replay 命令在返回 replay/resource 前重新读取 DB active-admin role。 |
| 3 | 管理员可维护菜品、营养、来源、授权、版本并查看审计差异。 | ✓ VERIFIED | catalog draft → review → immutable publish → eligibility/disqualify 具备版本、If-Match、幂等及 allowlisted before/after audit diff；独立后台 E2E 覆盖生命周期。 |
| 4 | 管理员可查看运行、失败节点、工具耗时和费用，不暴露原图、密钥或思维链。 | ✓ VERIFIED | admin run DTO/UI 均为最小 allowlist，仅允许状态、版本、计数、耗时、费用、失败码和安全摘要；未发现 raw body、image、secret、full state 或 reasoning 进入该链路。 |
| 5 | README 具备架构图、状态图、时序图、调试与面试线索。 | ✓ VERIFIED | 根 README、三 SPA README 与中文教学文档都存在相关图、命令和链接的问答线索。网络端口说明与实际 Playwright 配置一致；另见教学 Port 命名 warning。 |

**Score:** 4/5 roadmap truths verified

### 06-30/31/32 专项复核

| 项目 | Status | Evidence |
| --- | --- | --- |
| records-owned preference → dashboard read Port | ✓ VERIFIED | `SqlAlchemyDashboardRepository.get_dashboard_timezone_for_user()` 以 `DashboardTimezonePreference.user_id == user_id` 读取，缺失时返回 `None`；service 的 `_local_dashboard_today()` 在 aggregate/provider 前以 `ZoneInfo` 验证。 |
| 用户本地日、DST 与周一数学 | ✓ VERIFIED | backend fake/service tests 覆盖 Shanghai/Los Angeles；`deriveLocalWeekStart()` 以指定 IANA `formatToParts`，不再用 `toISOString()` 截取 UTC 日期。 |
| confirmation gate | ⚠️ PARTIAL | 200 前阻断 dashboard reads 正确；但已有 preference 的 409 被无条件放行，随后把当前 browser zone 变为 range authority。 |
| 双 Records guarded E2E 与人工浏览器路径 | ✓ VERIFIED（证据范围内） | 两 E2E 均为 fresh guarded stack，观察 confirmation 在 read 之前且不传 `time_zone` header/query；浏览器证据记录普通用户 analyze → save → Records。它们没有测试“已确认 zone 与当前 browser zone 不同”的状态迁移。 |
| absolute-path IANA 输入 fail-closed | ✗ FAILED | 直接运行 `MealRecordService._validated_time_zone('/invalid-timezone')` 得到 `ValueError`，不是 `InvalidTimeZone`；API 映射未覆盖。 |

## Required Artifacts & Key Links

| Artifact/link | Status | Details |
| --- | --- | --- |
| `records/service.py` → persisted `consumed_local_date` | ✓ VERIFIED | 写入/编辑按 ZoneInfo 与 consumed_at 固化日期；历史 SQL 基于该列并保留 tenant/deleted filters。 |
| preference → dashboard `ZoneInfo` local today | ✓ VERIFIED | 最小 read Port 和 repository projection 已接入 overview/weekly service，缺失或损坏 preference 的 dashboard contract 为安全 409。 |
| Records confirmation → current overview/review range | ✗ NOT WIRED | 不同 browser zone 的 409 路径仍影响 `week_start`，服务端 overview 不校验 current-week relation。 |
| Dashboard/current weekly API → persisted preference only | ✗ NOT WIRED | API 允许客户端 `week_start` 改写 overview current window；weekly review 虽验证 Monday/future，仍没有阻止 current browser Monday 替代 preference current Monday。 |
| catalog commands → current DB RBAC | ✓ WIRED | active role 验证在 replay/query/return 前；normal/demoted replay regression 存在。 |
| Admin UI → public admin API → audited DB commands | ✓ WIRED | strict Zod feature client、probe guard 和 audited command response 形成真实链路。 |

## Data-Flow Trace

| Rendered data | Source | Real data | Status |
| --- | --- | --- | --- |
| Records overview/history/review | Authenticated dashboard API → tenant-filtered PostgreSQL aggregates/cache | 是 | ⚠️ HOLLOW at current-window boundary: data real, selected window can be browser-controlled. |
| Admin catalog/config/runs | Authenticated `/api/v1/admin/*` → DB RBAC/repository | 是 | ✓ FLOWING |

## Behavioral Spot-Checks

| Behavior | Command/result | Status |
| --- | --- | --- |
| Records client/date helper/type safety | `cd frontend && npm test -- --run src/features/records/api/client.test.ts src/features/records/api/dashboard.test.ts src/features/records/components/RecordsPage.test.tsx && npm run typecheck` → 3 files, 10 tests passed; typecheck passed | ✓ PASS, but tests encode the unsafe 409 continuation rather than cross-zone invariant |
| Dashboard timezone/weekly HTTP tests | `cd backend && uv run pytest tests/dashboard/test_dashboard_service.py tests/dashboard/test_weekly_review_facts.py tests/unit/test_dashboard_api.py tests/unit/test_weekly_review_api.py -q` → 15 passed | ✓ PASS, but no stored-zone/browser-zone mismatch coverage |
| Existing records service/API tests | `uv run pytest tests/unit/test_meal_record_api.py tests/records/test_record_service.py -q` → 11 passed | ✓ PASS, but no absolute-path ZoneInfo regression |
| Absolute ZoneInfo key | `MealRecordService._validated_time_zone('/invalid-timezone')` → `ValueError: ZoneInfo keys may not be absolute paths` | ✗ FAIL |

## Requirements Coverage

| Requirement | Status | Evidence |
| --- | --- | --- |
| UI-02 | ✗ BLOCKED | 页面、aggregates、history、trend、review 均存在，但核心“当前周/今日一致性”可被当前 browser range 改写。 |
| UI-03 | ✓ SATISFIED | versioned safe stage mapping、strict parser 与安全 DOM/E2E assertions 存在。 |
| ADM-01 | ✓ SATISFIED | independent SPA + backend DB-RBAC + normal-user rejection/read guards。 |
| ADM-02 | ✓ SATISFIED | catalog lifecycle、publication/eligibility、version/source/license/audit artifacts。 |
| ADM-03 | ✓ SATISFIED | 最小运行指标和 fail code UI/API；敏感字段未流出。 |
| ADM-04 | ✓ SATISFIED | versioned non-secret RuntimeConfig、budget validation、admission snapshot 与 admin UI。 |
| ADM-05 | ✓ SATISFIED | actor/time/reason/allowlisted before-after diff 的审计链。 |
| ARC-08 | ✓ SATISFIED | sibling admin SPA、独立 build/lock/E2E config、无 frontend/src import、后端 RBAC。 |
| EDU-02 | ✓ SATISFIED | README 图、启动/调试命令存在。网络端口陈述准确：开发 `5178/5179/8000`；Records E2E `5182/8002/5185`；Admin E2E `5183/8003/5184`，均与两个 Playwright config 一致。 |
| EDU-03 | ⚠️ PARTIAL | 面试线索存在，但 `docs/learning/06-dashboard-admin.md` 将真实接口错称为 `DashboardTimezonePort`；源码定义是 `DashboardTimezoneReadPort`，并且文档把 browser-derived week_start 描述得比实际更安全。修复术语和当前窗口边界后即可完整满足。 |

## Anti-Patterns / Documentation Accuracy

| File | Line/area | Severity | Impact |
| --- | --- | --- | --- |
| `frontend/src/features/records/api/client.ts` | confirmation 409 path | 🛑 BLOCKER | Treats any already-confirmed preference as permission to use an unrelated browser zone for current range. |
| `frontend/src/features/records/components/RecordsPage.tsx` | `weekStart` and three dashboard calls | 🛑 BLOCKER | Browser-derived value selects supposedly server-authoritative current dashboard/review window. |
| `backend/app/dashboard/service.py` | `get_overview(... week_start)` | 🛑 BLOCKER | No domain constraint ties supplied overview week to preference-local current Monday. |
| `backend/app/records/service.py` | `_validated_time_zone` | ⚠️ WARNING | Leaks `ValueError` for absolute/non-normalized ZoneInfo keys as 500. |
| `docs/learning/06-dashboard-admin.md` | timezone Port section | ℹ️ INFO | `DashboardTimezonePort` does not exist; actual interface is `DashboardTimezoneReadPort`. Network port names/numbers in docs are otherwise accurate. |

No unreferenced `TBD`/`FIXME`/`XXX` marker was found in the inspected Phase 06 production paths.

## Human Verification

The user has already confirmed the normal real-browser analyze → save → Records flow. No additional ordinary visual-only check blocks the report. After the two functional gaps are fixed, rerun the existing public browser path plus a controlled browser-zone-change scenario; deterministic/API/E2E tests must prove exact cross-zone calendar semantics.

## Gaps Summary

The previous server-UTC defect was genuinely fixed, but the closure is not sound: 06-31 retained a client-selected `week_start` and 06-30 lets overview trust it. That contradiction makes `UI-02` fail at ordinary cross-timezone/cross-week use. Separately, records input validation is inconsistent with dashboard validation and can expose a 500 for malformed but schema-valid ZoneInfo keys.

These are not deferred to Phase 7: Phase 7 covers general quality/security gates, not the Phase 6 statistical-window contract. Plan a focused Phase 6 gap closure before marking this phase complete.

---

_Verified: 2026-09-04T10:05:00Z_
_Verifier: gsd-verifier (codebase evidence; no product-code changes)_
