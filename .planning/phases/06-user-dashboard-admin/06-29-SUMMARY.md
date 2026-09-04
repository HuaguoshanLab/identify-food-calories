---
phase: 06-user-dashboard-admin
plan: 29
subsystem: cross-stack-e2e-browser-evidence
tags: [playwright, codex-browser, react, fastapi, postgresql, mailpit, rbac, runtime-config]
requires:
  - phase: 06-28
    provides: isolated admin runner and RuntimeConfig lifecycle E2E
provides:
  - Records-specific isolated E2E that creates RuntimeConfig through the independent admin UI before user analysis.
  - Codex built-in-browser evidence for administrator configuration, ordinary-user records, and ordinary-user admin denial.
affects: [phase-06-verification, records-dashboard, admin-rbac, runtime-config]
tech-stack:
  added: []
  patterns: [guarded PostgreSQL E2E startup, UI-created runtime policy, safe SSE assertions, browser-and-automation evidence separation]
key-files:
  created: [frontend/tests/e2e/records-dashboard.spec.ts]
  modified: [frontend/playwright.config.ts, frontend/tests/e2e/README.md, docs/verification/phase-06-browser-acceptance.md, docs/verification/README.md]
key-decisions:
  - "Codex built-in-browser observations remain distinct from Playwright, even when both cover the same public flow."
  - "The earlier 06-28 dialog timeout was corrected with viewport and in-viewport interaction constraints; the latest isolated E2E is passing."
patterns-established:
  - "Each Records E2E run owns its empty guarded database, user and admin previews, first-admin audit bootstrap, and UI-created RuntimeConfig."
requirements-completed: [UI-02, UI-03, ADM-01, ADM-04]
duration: cross-session
completed: 2026-09-04
status: complete
---

# Phase 06 Plan 29: Records E2E and Browser Evidence Summary

**隔离 Records E2E 与 Codex 内置浏览器共同证明：管理员可安全更新未来配置，普通用户可完成安全分析、保存和记录看板，且普通用户无法渲染后台私有内容。**

## Performance

- **Duration:** 跨会话执行，未将中断时间伪装为有效执行时长。
- **Completed:** 2026-09-04
- **Tasks:** 2/2 完成。
- **Files modified:** 5

## Accomplishments

- `ed1e687` 的 Records runner 在同一个空隔离库中，先完成受审计首位管理员 bootstrap、admin Guard 200 和 RuntimeConfig UI `POST 201`，随后才允许普通用户分析。
- Codex 内置浏览器实际确认管理员在 RuntimeConfig UI 创建启用的非密钥 v2 配置；普通用户从安全五阶段流完成 130 kcal 报告、保存及 Records 的摘要、趋势、history 和低覆盖周复盘。
- 同一普通用户经真实后台登录触发 Bearer probe 拒绝并到达 `/admin/forbidden`；页面没有渲染 AdminShell、catalog 或 overview。
- `admin-management` 的旧超时已查明为对话框按钮不在视口；加入真实 UI 滚动约束、runner viewport 和 in-viewport 断言后，最新 isolated E2E 在 14.6 秒通过 RuntimeConfig `201`、审核/发布/失格 `200` 与普通用户 `403`。

## Task Commits

1. **Task 1: 让 Records runner 自行完成 admin configuration preflight 后的真实用户 E2E** — `ed1e687` (`test`)
2. **Task 2: 用 Codex 内置浏览器复走实际公开路径，并记录可核查验收证据** — 本次原子文档提交（`docs`）

## Files Created/Modified

- `frontend/playwright.config.ts` — Records runner 拥有用户/admin 预览、双 CORS origin、guarded reset 和无 server reuse。
- `frontend/tests/e2e/records-dashboard.spec.ts` — 断言 RuntimeConfig 201、用户安全 SSE、保存和 Records 四项投影。
- `frontend/tests/e2e/README.md` — 登记 Records runner 的独立 reset 与禁止捷径合同。
- `docs/verification/phase-06-browser-acceptance.md` — 记录通过的内置浏览器路径、通过的最新后台 E2E 与仍待浏览器复验项目。
- `docs/verification/README.md` — 保持浏览器与自动化证据层级索引准确。

## Decisions Made

- 内置浏览器与 Playwright 是两类证据：前者只记录真实产品页面及公开 API 的可观察结果，后者只记录可重复自动化门禁。
- RuntimeConfig 只记录“启用的非密钥版本”和页面确认，不记录 endpoint、密钥、身份材料或配置标识符。
- 普通用户的一餐 Records 结果是主验收证据；本地调试管理员的两餐累计仅作交叉检查。

## Verification

- `cd frontend && E2E_FRONTEND_PORT=5182 E2E_BACKEND_PORT=8002 E2E_RECORDS_ADMIN_FRONTEND_PORT=5185 npm run test:e2e -- --grep records-dashboard` — **passed**，1 Playwright test。
- `cd admin-frontend && E2E_ADMIN_BACKEND_PORT=8003 E2E_ADMIN_USER_FRONTEND_PORT=5183 E2E_ADMIN_FRONTEND_PORT=5184 npm run test:e2e -- --grep admin-management` — **passed**，最新 isolated run 为 14.6 秒。
- Codex 内置浏览器 — **passed**：管理员 RuntimeConfig 创建、普通用户 analyze → save → Records，以及普通用户后台 forbidden 三条真实公开页面路径。
- 本次文档更新后运行 Markdown/链接检查和 `git diff --check`。

## Browser Verification

已完成。验收使用 Codex 内置浏览器直接操作 `127.0.0.1:5178` 用户端和 `127.0.0.1:5179` 独立后台的真实 SPA 及公开 API；未使用 Playwright、截图、数据库直写、seed、token 或 Cookie 注入、内部函数替代。已验证的页面结果和未覆盖项目见 [`phase-06-browser-acceptance.md`](../../../docs/verification/phase-06-browser-acceptance.md)。

## Earlier Service Interruption

交接中曾报告服务不可用/503。后续恢复后的隔离运行与本次真实页面路径均可用；证据不足以确认早前 503 根因，因此未作推断。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Browser E2E interaction] 修复目录审核对话框的视口交互失败**
- **Found during:** 06-28 `admin-management` 隔离 E2E
- **Issue:** 审核提交按钮不在视口，导致预期公开请求超时。
- **Fix:** 添加真实 UI 滚动约束、runner viewport 和 in-viewport 断言。
- **Verification:** 最新 isolated E2E 14.6 秒通过 RuntimeConfig `201`、审核/发布/失格 `200` 及普通用户 `403`。
- **Committed in:** `a71e4f1`（上游 06-28 修复）

**Total deviations:** 1 个上游 Rule 1 修复；本计划的收尾文档未扩展源码或测试范围。

## Known Stubs

None。该计划没有新增生产 UI stub；未覆盖的浏览器场景已在验收记录中明确列为后续复验项。

## Threat Flags

None。变更仅更新验证证据与计划总结，未引入新的网络端点、认证路径、文件访问或 schema 信任边界。

## Next Phase Readiness

- Phase 06 的 06-29 目标已完成：配置准入、普通用户 Records 路径及普通用户后台拒绝均有自动化与真实浏览器证据。
- 跨日分页、更多周复盘状态、后台 overview/filter/disable、catalog 历史稳定性和过期会话仍需按浏览器验收记录逐项复验，不能被当前结果隐含为通过。

## Self-Check: PASSED

- 确认 Records E2E 资产、两份验收文档和本 SUMMARY 均存在。
- 确认任务提交 `ed1e687` 与上游修复 `a71e4f1` 存在于 Git 历史。
- 确认 SUMMARY 与验收记录均将内置浏览器、Playwright 和未复验项目明确分层。
