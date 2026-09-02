# Deferred Items

## 2026-09-02 — Phase 05 Plan 11 isolated planning E2E generation failure

- **Scope:** `frontend/tests/e2e/plans.spec.ts` real synthetic-user path.
- **Observed:** The self-owned `8001` FastAPI and `5179` Vite services start successfully, registration, Mailpit verification, login, profile read, memory read, and `POST /api/v1/agent/threads/diet-planning` succeed. Both planning E2E cases then render `暂时无法生成计划 请检查资料和网络后重试；若问题持续，请稍后再试。` before `今日三餐计划` appears.
- **Why deferred:** The failure precedes this plan's replacement-summary/focus/scroll contract and is outside the plan's allowed frontend focus change. No unrelated Agent or backend behavior was changed.
- **Follow-up:** Diagnose the isolated diet-planning Agent completion path, then rerun `E2E_BACKEND_PORT=8001 E2E_FRONTEND_PORT=5179 npm exec playwright test tests/e2e/plans.spec.ts`.
