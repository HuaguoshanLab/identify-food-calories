---
phase: 04-meal-records-and-memory
plan: "07"
subsystem: agent-memory-api-e2e
tags: [langgraph, fastapi, postgres, mailpit, playwright, react]
requires:
  - phase: 04-05
    provides: direct-memory ledger and provisioning state machine
  - phase: 04-06
    provides: lifespan-owned provisioning and deletion worker
provides:
  - Graph-to-tool direct preference capture with replay-safe state marker
  - Public register/Mailpit/verify/login A/B memory API contract
  - H5 regression path for direct preference management
affects: [phase-04-uat, memory, agent, frontend-e2e]
tech-stack:
  added: []
  patterns:
    - Fresh-text graph effects cross only a typed tool boundary and use a bounded budget.
    - Public API tests establish identity only through registration, cookie verification, and login.
key-files:
  created:
    - backend/tests/integration/test_direct_memory_public_api.py
  modified:
    - backend/app/agent/graph.py
    - backend/app/agent/tools.py
    - backend/app/agent/state.py
    - frontend/tests/e2e/agent.spec.ts
    - docs/learning/04-meal-records-and-long-term-memory.md
key-decisions:
  - "直接偏好写入仅限 fresh text 的 typed Graph tool；重放只读取完成 marker。"
  - "公开跨栈身份链固定使用 http://127.0.0.1:5178、Mailpit 和登录签发的 Bearer token。"
patterns-established:
  - "Graph direct-write safety: state retains no raw statement, ledger ID, provider ID, request key, or score."
requirements-completed: [MEM-03, MEM-04, MEM-05]
duration: 1h 10m
completed: 2026-09-01
---

# Phase 4 Plan 07: Direct Preference Product-Path Summary

Graph 现在会把 fresh 文本中的明确忌口经唯一 typed tool 写入本地 memory ledger，并由公开认证 API 与 H5 E2E 覆盖其管理路径。

## Completed Tasks

1. **Graph typed capture** — `fa7e290`, `0bf6600`
   - RED 测试覆盖“米饭 100 克，我不吃辣”的单次 capture、130.0 kcal 不变、安全 state 和 replay 不重复。
   - Graph 不导入 MemoryService/ORM/Provider；Session adapter 才构造 MemoryService。
   - 直接写入消耗既有 tool budget，并在 checkpoint 中只留下完成 marker 与摘要散列。

2. **Public A/B memory API contract** — `7058a5e`
   - A/B 只经 public register → Mailpit code → verify cookie/Origin → login 获得 Bearer token。
   - 证明 A 可 list/update/delete，B 对 A 的 GET/PATCH/DELETE 都不可用，删除后公共 Agent retrieval context 为空。

3. **H5 E2E and teaching evidence** — `d16aa72`
   - Playwright 覆盖分析→我的→记忆→编辑→确认删除→刷新空态、无敏感字段与 320px 无横向溢出。
   - E2E 与 CORS origin 统一到 `http://127.0.0.1:5178`。

## Verification

- PASS — `cd backend && uv run pytest tests/unit/test_agent_memory_context.py tests/memory/test_memory_service.py -q`：14 passed。
- PASS — `cd backend && SMTP_HOST=127.0.0.1 SMTP_PORT=1025 CORS_ORIGINS='["http://127.0.0.1:5178"]' uv run python tests/run_pg.py --env-file .env.test.example -- uv run python -m pytest tests/integration/test_direct_memory_public_api.py -q`：1 passed。
- PASS — `cd frontend && npm run typecheck && npm run lint`。
- PENDING — `npm exec playwright test tests/e2e/agent.spec.ts` 无法由 Playwright 自行启动，因为用户现有 FastAPI 已占用 `127.0.0.1:8000`；项目配置 `reuseExistingServer: false`，未复用也未终止该进程。
- PENDING — 内置浏览器只读检查确认 `http://127.0.0.1:5178/app/analyze` 可访问、记忆入口可导航。实际 `米饭 100 克，我不吃辣` 提交属于健康偏好数据传输，且确认删除会破坏数据；两者均等待用户即时确认。当前本地 `/app/me/memories` 显示“暂时无法加载记忆”，尚未在不重启现有服务的前提下诊断或修改。

## Deviations from Plan

### Auto-fixed Issues

1. **[Rule 1 - Bug] Direct preference extraction rejected meal-plus-preference text**
   - **Found during:** Task 1
   - **Issue:** 原白名单提取只匹配整句 `我不吃辣`，会漏掉 UAT 实际输入 `米饭 100 克，我不吃辣`。
   - **Fix:** 按中文/英文句段匹配仍受限的一人称明确表达；测试 Fake provider 同步支持该受控组合输入。
   - **Files modified:** `backend/app/memory/service.py`, `backend/app/providers/reasoning/fake.py`
   - **Verification:** 14 related unit tests passed。
   - **Commit:** `0bf6600`

2. **[Rule 2 - Correctness] E2E origin aligned to the user-selected local endpoint**
   - **Found during:** Task 3
   - **Issue:** Playwright 仍用 4173，无法证明用户指定的 `127.0.0.1:5178` CORS 路径。
   - **Fix:** 预览脚本与 Playwright base URL 统一为 5178。
   - **Files modified:** `frontend/package.json`, `frontend/playwright.config.ts`
   - **Verification:** TypeScript 与 ESLint passed；完整 E2E 等待端口释放后执行。
   - **Commit:** `d16aa72`

**Total deviations:** 2 auto-fixed. **Impact:** 修复了用户实际输入的直接偏好捕获，并让测试端点和产品端点一致。

## Known Stubs

None. 自动化 E2E 是完整测试，不是 mock UI；其执行因现有用户服务端口占用而待恢复。

## Browser Verification Pending

继续前需要用户即时确认，允许浏览器向本地 `http://127.0.0.1:5178` 提交健康偏好文字“米饭 100 克，我不吃辣”，随后在同一测试路径确认删除该新建记忆。不会对现有用户记忆执行删除。

## Self-Check: PASSED

- 已确认本 Summary、公开 API 集成测试和 H5 E2E 文件存在。
- 已确认 `fa7e290`、`0bf6600`、`7058a5e`、`d16aa72` 均存在于 Git 历史。
