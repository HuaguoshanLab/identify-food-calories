---
phase: 06-user-dashboard-admin
plan: 20
subsystem: cross-stack-acceptance
tags: [playwright, vitest, pytest, fastapi, react, zod, postgresql, browser-acceptance]
requires:
  - phase: 06-04
    provides: H5 records dashboard and public read APIs
  - phase: 06-09
    provides: weekly-review API and H5 presentation
  - phase: 06-15
    provides: catalog lifecycle UI
  - phase: 06-19
    provides: admin runs and audit UI
  - phase: 06-22
    provides: admin session shell and overview
provides:
  - 真实普通用户从已发布受控目录分析、保存到 records dashboard 的浏览器证据
  - 目录 lifecycle 路由与已发布 canonical-name 搜索、保存和 history DTO 的回归修复
  - Phase 06 自动化与内置浏览器证据记录，明确未能运行的 Playwright 门禁
affects: [phase-06-verification, frontend, backend, admin-frontend]
tech-stack:
  added: []
  patterns: [runtime-only-admin-route-assembly, strict-public-dto-compatibility, completed-validated-record-source]
key-files:
  created:
    - docs/verification/README.md
    - docs/verification/phase-06-browser-acceptance.md
    - frontend/src/features/records/api/client.test.ts
    - frontend/src/features/records/api/dashboard.test.ts
  modified:
    - backend/app/nutrition/repository.py
    - backend/app/records/repository.py
    - frontend/src/features/records/api/client.ts
    - frontend/src/features/records/api/dashboard.ts
    - admin-frontend/src/App.tsx
key-decisions:
  - "已发布 admin 目录条目的 canonical_name 必须作为受控匹配名暴露，不能只依赖 aliases。"
  - "餐食保存只能读取 completed_validated Agent 事件，拒绝任何未验证终态。"
  - "前端 strict Zod DTO 必须兼容 FastAPI 的 response_model_exclude_none 与 RFC 3339 时间格式，不能把成功响应误报为失败。"
patterns-established:
  - "浏览器发现的跨栈契约断裂以最小生产修复和隔离 PostgreSQL/前端回归测试闭合。"
  - "验收记录明确区分真实浏览器成功、自动化 PASS 与因缺少 E2E 资产或公开准备路径而未完成的门禁。"
requirements-completed: [UI-02, UI-03, ADM-01, ADM-02, ADM-03, ADM-04, ADM-05, ARC-08]
duration: 20min
completed: 2026-09-04
---

# Phase 06 Plan 20: 跨栈真实路径回归与内置浏览器验收 Summary

**真实用户已从管理员发布的受控“白米饭”完成 130 kcal 分析、确认保存、详情和 records 看板闭环；后台 catalog lifecycle、runs 最小详情与 audit 也经独立 SPA 验证。**

## Performance

- **Duration:** 20 min
- **Started:** 2026-09-04T02:02:57Z
- **Completed:** 2026-09-04T02:22:00Z
- **Tasks:** 3/3（自动化缺口已如实记录）
- **Files modified:** 18

## Accomplishments

- 修复管理员草稿从保存结果进入受保护 lifecycle 页的缺口；真实管理员通过公开 UI 创建、审核并发布 authorized 测试菜品。
- 修复已发布目录 canonical name 遗漏、完成报告事件名不匹配、保存请求缺少 IANA 时区、records/history 严格 DTO 漂移，使真实 H5 完成分析→保存→详情→overview/trend/history/weekly 的闭环。
- 写入可复查的浏览器验收记录；冻结周复盘 eval、隔离 PostgreSQL 保存纵向测试和前端 DTO 回归均通过。

## Task Commits

1. **Task 1: 扩展真实用户 H5 与周复盘 E2E** — `b26c2de`、`4f8afc5`、`458c04e`、`d6e2271`、`d09d5eb`（fix/test）
2. **Task 2: 扩展真实 admin 管理与拒绝 E2E** — `7d50af3`、`dc8fbbb`（fix/test）
3. **Task 3: 内置浏览器公开 API 验收及证据记录** — 本提交的验收文档与元数据。

## Files Created/Modified

- `admin-frontend/src/App.tsx`、`features/catalog/{CatalogDraftPage,CatalogLifecyclePage}.tsx` — 将保存草稿接入受运行时管理员会话保护的审核/发布路由。
- `backend/app/nutrition/repository.py` — 已发布目录将 canonical name 纳入受控候选，避免可发布但不可分析。
- `backend/app/records/repository.py` — 仅从 `completed_validated` 事件读取可保存报告。
- `frontend/src/features/records/api/{client,schemas,dashboard}.ts` — 发送浏览器 IANA 时区，解析本地日期归属、RFC 3339 时间及省略的末页 cursor。
- `docs/verification/phase-06-browser-acceptance.md` — 自动化、真实浏览器路径、结论和未完成门禁的逐项证据。

## Decisions Made

- 真实浏览器中发现的 404/422/严格解析失败全部按生产契约修复；没有用客户端默认记录、宽松 passthrough DTO、数据库直写或伪造 token 掩盖错误。
- 后台完整页重载丢失 runtime-only access token 是设计行为；受保护页验收均在同一次手工登录后的 SPA 导航中完成。
- 未补写虚假的 Playwright 文件：`records-dashboard.spec.ts`、admin Playwright config 与 `admin-management.spec.ts` 仍不存在，不能把浏览器证据或 Vitest 当作它们的 PASS。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Integration] 目录 lifecycle 页面未被独立后台路由或草稿保存结果接入**
- **Found during:** Task 2
- **Fix:** 添加 guarded lifecycle route 与“审核与发布目录”真实链接。
- **Verification:** catalog/lifecycle focused tests 7 passed、typecheck、build；真实管理员 UI 完成草稿→审核→发布。
- **Committed in:** `dc8fbbb`。

**2. [Rule 2 - Integration] 已发布目录 canonical name 无法被 Agent 受控搜索选中**
- **Found during:** Task 1
- **Fix:** publication DTO 将 canonical name 合并为受控匹配名。
- **Verification:** 隔离 PostgreSQL publication search 3 passed；真实“白米饭 100 克”报告生成 130 kcal。
- **Committed in:** `b26c2de`。

**3. [Rule 2 - Integration] 保存请求和可保存报告事件与实际 API/Agent 契约不一致**
- **Found during:** Task 1
- **Fix:** 前端提交 IANA time_zone 并解析本地日期字段；records repository 仅读取 `completed_validated`。
- **Verification:** Agent→保存 PostgreSQL 纵向、Service/API 共 12 passed；真实确认保存及详情成功。
- **Committed in:** `4f8afc5`、`458c04e`。

**4. [Rule 2 - Integration] history strict DTO 拒绝 FastAPI 末页形状**
- **Found during:** Task 1
- **Fix:** 兼容 RFC 3339 offset 和 `response_model_exclude_none` 省略的 `next_cursor`，末页恢复为 null。
- **Verification:** history/client/component 4 tests、typecheck、build；真实 history 显示一条已保存记录。
- **Committed in:** `d6e2271`、`d09d5eb`。

---

**Total deviations:** 4 auto-fixed（Rule 2：4）。
**Impact on plan:** 均为真实公开路径的正确性缺口，修复未增加依赖、表或绕过通道。

## Verification

- `cd backend && uv run pytest tests/evals/test_weekly_review_eval.py -q` — PASS，14 passed。
- 隔离 PostgreSQL：`tests/integration/test_catalog_publish_eligibility.py` — PASS，3 passed；`tests/integration/test_meal_records.py tests/records/test_record_service.py tests/unit/test_meal_record_api.py` — PASS，12 passed。
- 前端：records API/history/component focused Vitest — PASS，4 passed；typecheck、production build — PASS。
- 后台：catalog focused Vitest — PASS，7 passed；typecheck、production build — PASS。
- Codex 内置浏览器：真实用户“白米饭 100 克”报告 130 kcal→保存→详情 `admin-publication-v1`→records 130/1、趋势、history、低覆盖周复盘；真实管理员 catalog lifecycle、runs 最小详情和 audit 均成功。详见 `docs/verification/phase-06-browser-acceptance.md`。

## Known Stubs

没有产品运行时 stub。以下自动化验收资产仍缺失，不能标作通过：

- `frontend/tests/e2e/records-dashboard.spec.ts`；现有隔离 E2E 环境也没有通过公开路径准备 RuntimeConfig 的机制。
- `admin-frontend` 的 Playwright 配置与 `tests/e2e/admin-management.spec.ts`。

## User Setup Required

无新的密钥或外部服务配置。为补齐未完成 E2E，需要隔离测试环境提供可经公开路径准备的 RuntimeConfig 和可重复认证链，不能复用或导出实际凭据。

## Next Phase Readiness

- 用户与管理员关键成功路径已有真实浏览器证据，目录发布可驱动真实受控分析和保存。
- 仍应补齐缺失的 Playwright assets，以及普通用户后台拒绝、过期会话、catalog 失格/历史稳定、跨日 cursor、admin overview/filter/runtime disable 的真实验收，再将 Phase 6 标为无保留完成。

## Self-Check: PASSED

- 已确认浏览器验收记录及两份 records API 回归测试文件存在。
- 已确认 `7d50af3`、`dc8fbbb`、`b26c2de`、`4f8afc5`、`458c04e`、`d6e2271`、`d09d5eb`、`74ca2b3` 均位于 Git 历史。

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-04*
