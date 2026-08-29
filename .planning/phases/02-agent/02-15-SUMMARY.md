---
phase: 02-agent
plan: 15
subsystem: agent-deletion-ui
tags: [fastapi, react, playwright, postgresql, retention, visual-baseline]
requires:
  - phase: 02-agent
    provides: "tenant-scoped Agent ledger、lifecycle retention worker 与既有 generated DELETE operation"
provides:
  - "tenant-safe、幂等且带 due_at 的公开线程删除 API"
  - "带二次确认的 H5 删除入口，接受后关闭 stream、缓存和 URL thread state"
  - "未污染 official baseline 的 SHA-bound completed-analysis candidate"
affects: [phase-02-visual-approval, retention, agent-h5]
tech-stack:
  added: []
  patterns: ["deletion-pending as unavailable", "confirmation before destructive request", "candidate-only visual capture"]
key-files:
  created: [frontend/tests/e2e/h5-visual.spec.ts-snapshots/analyze-phase2-candidate-430-chromium-darwin.png]
  modified: [backend/app/agent/api.py, backend/app/agent/schemas.py, frontend/src/features/agent/components/AnalyzePage.tsx, frontend/tests/e2e/h5-visual.spec.ts]
key-decisions:
  - "DELETE response exposes the persisted due_at so the 24-hour deletion promise is independently verifiable."
  - "Visual candidate remains separate from the approved baseline until Plan 02-17 explicit review."
patterns-established:
  - "A deletion-pending thread returns the same 404 to owners, other users, and unknown-thread requests on every observable surface."
  - "A screenshot update command may create only a named candidate; official snapshots need SHA plus byte-for-byte protection."
requirements-completed: [AGT-04, ARC-05, QLT-02]
duration: 24min
completed: 2026-08-29
---

# Phase 02 Plan 15: 用户删除入口与视觉 Candidate Summary

**用户可从真实 H5 二次确认删除 Agent 会话，公开 API 返回可验证的截止时间，且 completed-analysis candidate 与 official 视觉基线严格隔离。**

## Performance

- **Tasks:** 3/3
- **Files modified:** 10

## Accomplishments

- `DELETE /api/v1/agent/threads/{id}` 现在返回持久化的 `due_at`；重复删除返回同一 intent，pending 后 snapshot、input、retry 和 events 均统一 404。
- H5 以明确文案和键盘可操作确认框呈现危险动作；成功后停止 SSE、移除 URL thread、清空本地报告与输入。
- 经真实注册、登录、公开 API 和 completed 报告生成 430×932 candidate；official `analyze-430` 前后 SHA 相同并通过 `cmp`。

## Task Commits

1. **Task 1: 接通 authenticated DELETE 与真实 PG 语义** — `5501d21`
2. **Task 2: 接通 H5 二次确认与删除 E2E** — `7ccb347`
3. **Task 3: 生成 candidate 并证明 official 未变** — `4013edd`

## Verification

- 真实 PostgreSQL：`test_agent_vertical.py -k 'delete or deletion_pending'` — 1 passed。
- 前端：OpenAPI `check-all`、组件 5 tests、lint 和 production build 通过。
- 真实 Playwright：`phase 2 delete thread`、`phase 2 visual candidate` 都通过，均使用 `food_agent_test`、真实注册登录与公开 API。
- official SHA before/after：`fba54a9449177837dc6f2496d29e479ad26b3b7d0b707de52c2ca6018df2ab4a`；`cmp`：PASS。
- candidate SHA：`19d4e5035919e8b28691f6e165012702f1a62404c082f21ddbb3925acf29ca2e`。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] 删除响应补齐持久化 deadline。**

- **Found during:** Task 1
- **Issue:** 已预声明的删除响应没有 `due_at`，客户端无法证明“24 小时内”承诺，真实 API 也无法满足计划验收。
- **Fix:** 添加 `due_at` 到 API schema、frozen OpenAPI 与生成 Zod 合同；不修改删除操作路径或请求体。
- **Verification:** PG owner/repeat/cross-user/pending 测试、`generate-contracts.mjs check-all` 通过。
- **Committed in:** `5501d21`

**Total deviations:** 1 auto-fixed（Rule 2 ×1）。**Impact:** 这是删除 SLA 可验证性与公开合同正确性所必需，不扩大功能范围。

## Browser Verification

内置浏览器控制工具在本执行会话不可调用，因此没有把 Playwright 替代为浏览器验收。真实 Playwright 已覆盖实际页面与公开 API；仍需在可用内置浏览器会话复核 H5 删除路径。

## Known Stubs

None. candidate 不是占位图；它刻意保持待人工批准，不能自动成为 official baseline。

## Next Phase Readiness

- `analyze-phase2-candidate-430-chromium-darwin.png` 等待 Plan 02-17 的显式人工视觉审批。
- official 基线未改变；未获得审批前不得替换或宣称其已批准。

## Self-Check: PASSED

- 确认 API、H5、candidate 和本 Summary 存在。
- 确认 `5501d21`、`7ccb347`、`4013edd` 位于 Git 历史。
