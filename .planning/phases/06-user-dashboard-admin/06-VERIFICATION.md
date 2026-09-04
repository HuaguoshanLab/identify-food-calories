---
phase: 06-user-dashboard-admin
verified: 2026-09-04T08:37:25Z
status: gaps_found
score: 4/5 roadmap must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 51/54 plan must-have truths verified
  gaps_closed:
    - "四类 catalog 命令均在任何 replay/resource 返回前读取当前 PostgreSQL active-admin role；正常用户和已降权用户 replay 均被拒绝。"
    - "独立 admin-management 与 records-dashboard Playwright runner/spec 已存在、可启动隔离产品栈且覆盖真实公开路径。"
    - "全量 frontend Vitest 串行回归已恢复通过。"
  gaps_remaining:
    - "Dashboard 的‘今日/本周’窗口仍以服务器 UTC 日期计算，未连接用户确认的 IANA 统计时区；UTC 边界会把用户本地日和周窗口算错。"
  regressions: []
gaps:
  - truth: "用户可按其本地自然日查看今日、本周摄入、趋势和周复盘。"
    status: failed
    reason: "记录写入已持久化 consumed_local_date，但 dashboard/weekly-review 的当前日与周起点仍由服务器 UTC date 计算；前端又以 toISOString() 截取本地周一，东半球周一凌晨会把 week_start 发送为周日。"
    artifacts:
      - path: "backend/app/dashboard/service.py"
        issue: "DashboardService 与 WeeklyReviewService 默认 datetime.now(UTC).date()，没有读取 DashboardTimezonePreference 或接收/校验用户 IANA 时区。"
      - path: "backend/app/dashboard/api.py"
        issue: "overview/weekly-review HTTP 合约没有统计时区输入，也未在 composition 中注入用户时区读取端口。"
      - path: "frontend/src/features/records/components/RecordsPage.tsx"
        issue: "startOfWeek() 对本地 Date 调整后调用 toISOString().slice(0, 10)；UTC+ 时区的周一凌晨会产生前一日，导致后端 Monday 校验 422。"
    missing:
      - "为 dashboard 的当前日/周窗口建立明确、经 ZoneInfo 校验的用户统计时区来源，并把它接入 overview、history 相关周窗口与 weekly review。"
      - "避免用 UTC 序列化截取浏览器本地日期；增加 Asia/Shanghai 与 America/Los_Angeles 的 UTC 跨日、周一凌晨和 API 422 回归测试。"
---

# Phase 06：用户看板与后台管理验证报告

**阶段目标：** 用户看懂历史摄入趋势，管理员可以安全维护 Agent 所依赖的数据和配置。
**验证时间：** 2026-09-04T08:37:25Z
**状态：** `gaps_found`
**复验：** 是——针对上次 gap closure。

## MVP 合同守卫

ROADMAP 标记本阶段为 `mvp`，但 `gsd-sdk query user-story.validate` 对当前目标返回 `false`：它不是规定格式的用户故事。因此无法伪称完成 MVP User Flow Coverage；以下按 ROADMAP 五条成功标准做目标倒推。这是规划元数据缺陷，不是对代码功能的放行。

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | 用户可查看今日、本周摄入、历史餐食、趋势图与周复盘。 | ✗ FAILED | SQL 确实按 `consumed_local_date` 查询，但 `backend/app/dashboard/service.py` 以 `datetime.now(UTC).date()` 定义 today/week；API 未取得用户统计时区，`RecordsPage.tsx` 的 `toISOString()` 还会在 UTC+ 周一凌晨发送周日。该功能在时区边界不成立。 |
| 2 | 独立 `admin-frontend/` 仅调用 `/api/v1/admin/*`；普通用户不能读取/修改后台数据，用户 H5 不含后台页面。 | ✓ VERIFIED | 独立 Vite 项目、admin-only API base、内存 token 与 `AdminRouteGuard` 存在；`AdminService` 四类 catalog mutation 都先 `require_role()`，隔离 admin E2E 观察到 normal-user Bearer probe `403`、`/admin/forbidden` 且无 AdminShell/private DOM。 |
| 3 | 管理员可维护菜品、营养、来源、授权、版本并查看审计差异。 | ✓ VERIFIED | draft → review → immutable publish → eligibility/disqualify 由 `AdminService`/repository 事务、If-Match、idempotency 和 allowlisted audit diff 实现；admin-management E2E 观察 review/publish/disqualify `200`。 |
| 4 | 管理员可查看运行、失败节点、工具耗时与费用，同时不暴露原图、密钥或思维链。 | ✓ VERIFIED | `AdminRunDetailResponse` 是 strict allowlist；run API/UI 仅消费 status、版本、计数、耗时、费用、失败码和安全 digest。无 email、原图、raw body、State 或 secret 字段的流入路径。 |
| 5 | README 包含架构图、状态图、时序图、调试方式和面试深挖题。 | ✓ VERIFIED | 根 README 具备 Mermaid architecture/state/sequence 图、启动/调试命令和可链接源码/测试的面试题；三 SPA README 与 `docs/learning/06-dashboard-admin.md` 存在。见下方文档准确性 warning。 |

**Score:** 4/5 roadmap truths verified

### Prior Gaps Rechecked

| Prior gap | Status | Direct evidence |
| --- | --- | --- |
| Catalog replay 可绕过当前 DB-RBAC | ✓ CLOSED | `create_catalog_draft`、`patch_catalog_draft`、`publish_catalog_draft`、`disqualify_catalog_publication` 都在 replay 查询前调用 `require_role()`。`test_catalog_draft_service.py` 覆盖 create/patch 的 normal + demoted replay 拒绝；`test_catalog_lifecycle_service.py` 覆盖 publish/disqualify 的 normal + inactive-demoted replay 拒绝。活跃管理员 replay 保留同一 create/publish 对象语义。 |
| Records/SSE/weekly 与独立后台管理/拒绝的 E2E 资产缺失 | ✓ CLOSED | `frontend/tests/e2e/records-dashboard.spec.ts`、`admin-frontend/playwright.config.ts`、`admin-frontend/tests/e2e/admin-management.spec.ts` 都存在且为非 stub。两 runner 都从 guarded `food_agent_test`、Mailpit、FastAPI 与两个 SPA preview 开始，`reuseExistingServer: false`。 |
| 全量 frontend Vitest 回归失败 | ✓ CLOSED | 本轮根代理串行观察：`frontend npm test -- --run` 为 **26 files / 139 passed**。此前并发 timeout 在串行运行中可重复消失，属于资源竞争，不是仍存在的测试失败。 |

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- |
| `backend/app/records/service.py` + `0013_dashboard_time_attribution.py` | IANA 校验、不可漂移 local-date 归属和审计回填 | ✓ VERIFIED | `ZoneInfo` 校验并以 `consumed_at.astimezone(zone).date()` 写 `consumed_local_date`；迁移有一致性 check、用户/local-date partial index 和一次性 preference/audit 表。 |
| `backend/app/dashboard/{api,service,repository}.py` | 本地日 dashboard 读模型 | ⚠️ HOLLOW | tenant/soft-delete/local-date SQL、HMAC keyset 和 strict DTO 都是实作；但 current today/week 的时区来源未接线，见 blocker。 |
| `frontend/src/features/records/{api,components}` | 严格 DTO 的 summary/trend/history/weekly render | ⚠️ HOLLOW | `RecordsPage` 用 TanStack Query 与 strict Zod client 渲染四投影；本地周起点的 UTC 序列化错误破坏边界日。 |
| `backend/app/admin/service.py` + catalog tests | current DB-RBAC、catalog lifecycle、审计 | ✓ VERIFIED | 四个 replay return 前都 refresh active role；normal/demoted replay tests 和 active replay identity assertions 存在。 |
| `admin-frontend/playwright.config.ts` + `tests/e2e/admin-management.spec.ts` | 独立真实后台 management/rejection runner | ✓ VERIFIED | 公共注册/Mailpit 验证、audited bootstrap、Guard `200`、RuntimeConfig `201`、目录生命周期和 normal-user `403`；没有 DB 写入、token/Cookie 注入或 mock endpoint。 |
| `frontend/playwright.config.ts` + `tests/e2e/records-dashboard.spec.ts` | 独立真实 Records/SSE/weekly runner | ✓ VERIFIED | 同一 fresh runner 先由 admin UI 建立 enabled RuntimeConfig，后 normal user 走 analyze → `text/event-stream` → confirm-save → `/app/records`，并断言安全 DOM/SSE。 |
| `docs/verification/phase-06-browser-acceptance.md` | 与 Playwright 分层的实际 Codex 浏览器记录 | ✓ VERIFIED | 文件明确声明非 Playwright/截图/DB/token/internal shortcut；记录管理员 RuntimeConfig **v2**、normal-user analyze → safe SSE → save → Records，以及 normal-user probe `403`/forbidden/no private render。 |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| Meal record confirmation/edit | persisted local date | `ZoneInfo` → `consumed_local_date` | ✓ WIRED | service 计算，model/migration 约束，dashboard SQL 消费该列。 |
| Dashboard overview/weekly review | user local current date/week | date/window computation | ✗ NOT WIRED | service/API 只使用 server UTC；frontend week start 以 UTC string 截取。 |
| Catalog command | PostgreSQL active admin role | `require_role()` before replay/query response | ✓ WIRED | 代码顺序与 normal/demoted replay tests 一致。 |
| Admin UI | runtime/catalog public APIs | Guard response + browser UI actions | ✓ WIRED | admin E2E waits for actual `201`/`200`/`403` response，非 fixture 成功。 |
| Records UI | Agent/SSE/save/dashboard public APIs | authenticated requests + strict parse | ✓ WIRED | records E2E 在真实 guarded stack 上观察 SSE 与后续保存/Records 投影。 |

### Data-Flow Trace (Level 4)

| Artifact | Data variable | Source | Produces real data | Status |
| --- | --- | --- | --- | --- |
| `RecordsPage` | overview/history/weekly review | authenticated `/api/v1/dashboard/*` | SQL snapshot aggregation/weekly service，非静态数组 | ✓ FLOWING（日期窗口除外） |
| Dashboard repository | `consumed_local_date` totals | `MealRecord` persisted columns，先 user_id + deleted_at filter | PostgreSQL aggregate/keyset records | ✓ FLOWING |
| Admin catalog/config pages | strict DTO state | `/api/v1/admin/*` | DB RBAC + immutable/audited command results | ✓ FLOWING |
| Current dashboard window | `today`, Monday `week_start` | server UTC / browser ISO UTC | 未采用用户统计时区 | ✗ DISCONNECTED |

### Behavioral Spot-Checks

以下结果由本轮根代理在同一工作树串行实际观察；没有把 SUMMARY 当结果。

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Catalog RBAC replay + lint | Phase-06 catalog targeted pytest + ruff | 15 passed；ruff passed | ✓ PASS |
| H5 complete regression | `cd frontend && npm test -- --run` | 26 files / 139 passed | ✓ PASS |
| Admin component regression | `cd admin-frontend && npm test -- --run` | 9 files / 29 passed | ✓ PASS |
| Admin build/type safety | admin typecheck + build | both passed | ✓ PASS |
| Independent admin management E2E | `admin-management` isolated runner | 1 passed / 12.7 s; RuntimeConfig `201`, lifecycle `200`, normal probe `403` | ✓ PASS |
| Independent Records E2E | `records-dashboard` isolated runner | 1 passed / 13.3 s; RuntimeConfig `201` → safe SSE → save `201` → overview/history/weekly | ✓ PASS |
| User-local Monday / UTC-boundary dashboard behavior | no targeted test exists | static trace disproves the required connection | ✗ FAIL |

### Probe Execution

Step 7c: **SKIPPED** — Phase 06 has no declared `scripts/**/tests/probe-*.sh`; the applicable executable cross-stack evidence is the two isolated Playwright runners above.

### Requirements Coverage

| Requirement | Status | Evidence |
| --- | --- | --- |
| UI-02 | ✗ BLOCKED | Views, SQL and E2E exist, but local-day/current-week definition is wrong at UTC boundaries. |
| UI-03 | ✓ SATISFIED | Versioned safe stage DTO, allowlist mapping and strict frontend parser; E2E asserts no forbidden SSE/DOM terms. |
| ADM-01 | ✓ SATISFIED | Independent SPA plus backend DB-RBAC; all four catalog replay paths now recheck active role. |
| ADM-02 | ✓ SATISFIED | Draft/review/publish/disqualify with immutable snapshots and future-use eligibility. |
| ADM-03 | ✓ SATISFIED | Minimal run metrics/list/detail DTO and UI; sensitive fields excluded. |
| ADM-04 | ✓ SATISFIED | Non-secret versioned RuntimeConfig, positive caps, admission snapshot and UI-created v1 E2E. |
| ADM-05 | ✓ SATISFIED | Reason, actor/time and scalar before/after audit diff stored/read via protected API. |
| ARC-08 | ✓ SATISFIED | Sibling `admin-frontend/`, independent lock/build/E2E config, no user-H5 import boundary violation. |
| EDU-02 | ✓ SATISFIED | Required diagrams and debug documentation exist; see warning on stale E2E wording. |
| EDU-03 | ✓ SATISFIED | Root README and learning document supply source/test-linked interview prompts and answers. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `backend/app/dashboard/service.py` | 85, 89–90 | server-UTC date is presented as user dashboard current date | 🛑 BLOCKER | UTC boundary gives the user the wrong today/week facts. |
| `frontend/src/features/records/components/RecordsPage.tsx` | 13 | local week calculation serialized as UTC date | 🛑 BLOCKER | UTC+ users can request Sunday as `week_start` during local Monday early hours and receive 422. |
| `README.md` | 72 | says admin Playwright config and Records spec are absent | ⚠️ WARNING | Both assets now exist and pass isolated E2E; debugging guidance is stale. |
| `docs/learning/06-dashboard-admin.md` | 64 | says records/admin Playwright assets are still missing | ⚠️ WARNING | Contradicts current test assets and verification evidence; update after the functional gap is fixed. |

No unreferenced `TBD`/`FIXME`/`XXX` debt marker was found in the Phase 06 production paths inspected.

## Browser Evidence (separate from Playwright)

The browser evidence file is internally consistent and intentionally narrow. It records, without sensitive identifiers:

- Admin on the independent SPA creates a non-secret enabled RuntimeConfig and sees server-confirmed **v2**.
- A normal user completes real analyze → safe progress/SSE → save → Records, including today, seven-day trend table, history and low-coverage review.
- The same normal user receives a real Bearer admin probe `403`, arrives at forbidden, and sees no AdminShell/catalog/overview content.

It explicitly does **not** claim that Playwright is browser evidence and lists untested cross-day/history, other weekly states, config-disable, historical-snapshot and expired-session paths. The documented browser evidence is therefore truthful for the requested three paths; it cannot repair the discovered UTC window defect.

## Deferred Items

None. Phase 7's general quality/security/CI goals do not specifically implement a user-timezone source for dashboard windows, so this is not conservatively deferrable.

## Gaps Summary

The three prior blockers are genuinely closed: RBAC replay ordering is fixed and tested, both isolated E2E assets execute the real public stacks, the catalog dialog is viewport-reachable, and full H5 Vitest passes serially. The phase still cannot pass because its central dashboard promise fails at ordinary timezone boundaries. Persisting each meal's local date is not sufficient when the API chooses "today" and the current week in server UTC, and the browser sends an ISO-derived wrong Monday in UTC+ time zones.

Fix the timezone-window contract and add boundary regression tests, then re-verify. Also correct stale README/learning claims so operational documentation no longer says the now-present E2E assets are absent.

---

_Verified: 2026-09-04T08:37:25Z_
_Verifier: gsd-verifier (codebase evidence; no production/test/STATE/ROADMAP changes)_
