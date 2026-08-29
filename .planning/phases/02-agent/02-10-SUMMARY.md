---
phase: 02-agent
plan: 10
subsystem: agent-vertical-green
tags: [fastapi, langgraph, postgres, sse, react, playwright, nutrition]
requires:
  - phase: 02-agent
    provides: "Agent ledger、Nutrition Service、FDC seed、Checkpointer bootstrap 与冻结 API 合同"
provides:
  - "认证用户从页面到受控目录营养报告的首个真实纵向 GREEN"
  - "tenant-safe 持久账本、Checkpointer、只读 SSE 重放和权威 snapshot"
  - "真实 PostgreSQL 与 Playwright 的 direct-grams 回归证据"
affects: [agent-followup, meal-history, evaluation, frontend-agent]
tech-stack:
  added: []
  patterns: ["graph-to-tool-only", "safe-event-replay-plus-snapshot", "test-runtime-database-isolation"]
key-files:
  created:
    - backend/tests/integration/test_agent_vertical.py
    - frontend/tests/e2e/agent.spec.ts
  modified:
    - backend/app/agent/api.py
    - backend/app/agent/service.py
    - backend/app/agent/graph.py
    - frontend/src/features/agent/components/AnalyzePage.tsx
    - frontend/src/features/agent/stream/useAgentEventStream.ts
key-decisions:
  - "Graph 只调用 Provider 与 NutritionToolAdapter；持久化、认证和 ORM 全部留在 graph 外。"
  - "SSE 只回放安全进度事件，报告只能从已认证的权威 snapshot 读取。"
  - "test 环境显式使用经过 guard 校验的 TEST_DATABASE_URL，保留 DATABASE_URL 开发哨兵且不重绑变量。"
patterns-established:
  - "所有 Agent 快照都先按 thread_id/user_id 查询账本，再读取任何持久状态或事件。"
  - "客户端以认证 request + 生成的 Zod schema 消费 snapshot，不从 SSE 组装营养数值。"
requirements-completed: [AGT-01, AGT-02, AGT-04, AGT-06, AGT-07, NUT-01, NUT-02, NUT-03, NUT-04, NUT-05, ARC-05, ARC-06, QLT-02]
duration: 68min
completed: 2026-08-29
---

# Phase 02 Plan 10: 认证 Agent 首个纵向 GREEN Summary

**登录用户输入“米饭 100 克”后，经持久 Graph、确定性 Nutrition Service、真实 PostgreSQL ledger/Checkpointer 与安全 SSE，获得权威 130.0 kcal 餐食报告。**

## Performance

- **Duration:** 68 min
- **Completed:** 2026-08-29
- **Tasks:** 2/2
- **Files modified:** 26

## Accomplishments

- 将 API、持久 run ledger、租约 supervisor、Graph、Fake Provider 和 NutritionToolAdapter 接成单一纵向路径；Graph 不导入 ORM 或 Repository。
- Provider Fake 只识别受控的“米饭 100 克”sentinel；营养值始终来自 USDA FDC 目录与内部 Decimal 计算，展示端才舍入。
- SSE 仅重放按用户过滤的 `running` / `completed` 安全事件；事件不含餐食文本、Provider body、State、CoT 或最终营养值，UI 只从 snapshot 渲染报告。
- 添加真实 PG 集成测试与真实注册、Mailpit 验证、登录、Agent 页面 Playwright E2E；确认 thread/run/event/checkpoint/受控目录均落在隔离数据库。

## Task Commits

1. **Task 1: 接通 Graph、ledger、Checkpointer、supervisor 与只读 SSE** — `f7bfc83` (`feat`)
2. **Task 2: 把同一 sentinel E2E 转为真实报告 GREEN** — `5719e48` (`feat`)

## Files Created/Modified

- `backend/app/agent/api.py` — 认证 API、tenant-safe snapshot 与只读 SSE replay。
- `backend/app/agent/service.py` — run 执行、事件账本、状态持久化与 checkpoint 写入。
- `backend/app/agent/graph.py`、`tools.py` — 无 ORM 的受控 Graph/Tool 边界。
- `backend/app/core/{config,database}.py` — test 运行时统一选择已验证的隔离数据库。
- `backend/tests/integration/test_agent_vertical.py` — 真实 PG/API/SSE/checkpoint 纵向证明。
- `frontend/src/features/agent/{components/AnalyzePage.tsx,stream/useAgentEventStream.ts}` — 权威快照报告和安全事件进度。
- `frontend/tests/e2e/agent.spec.ts` — 真实注册登录后的 direct-grams 合同。

## Decisions Made

- Checkpointer 是短期状态存储；业务 snapshot 和 SSE 都以 PostgreSQL Agent ledger 为权威来源。
- `APP_ENV=test` 不把 `DATABASE_URL` 改写成测试 URL，但应用 session factory 统一通过 `validate_test_database_configuration()` 选择测试目标；这避免认证和 Agent 访问不同数据库。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] 为 snapshot 增加报告字段和 tenant-safe 事件读取 Port**
- **Found during:** Task 1
- **Issue:** 冻结的 sentinel 合同只有线程状态，无法让页面渲染真实权威报告；Repository 也没有安全读取事件的接口。
- **Fix:** 补充最小 `report` snapshot 字段、事件/最新 run 查询 Port 与机械合同重生成。
- **Files modified:** `backend/app/agent/{api,ports,repository,schemas,service}.py`, `backend/openapi-agent-v1.json`, `frontend/src/features/agent/api/schemas.generated.ts`
- **Verification:** `check-all`、mypy、真实 PG integration 与 Playwright 通过。
- **Committed in:** `f7bfc83`, `5719e48`

**2. [Rule 1 - Bug] 统一 test FastAPI 运行时数据库目标**
- **Found during:** Task 2 的真实 E2E
- **Issue:** 认证依赖仍用开发哨兵库、Agent runtime 用测试库，已认证用户无法满足 Agent ledger 外键。
- **Fix:** 增加受 guard 保护的 `runtime_database_url()`，test 进程的所有应用 session 统一选取 `TEST_DATABASE_URL`。
- **Files modified:** `backend/app/core/config.py`, `backend/app/core/database.py`, `backend/app/main.py`
- **Verification:** 真实 PG 集成、真实注册/登录 Playwright E2E 通过。
- **Committed in:** `5719e48`

**Total deviations:** 2 auto-fixed（Rule 2 ×1，Rule 1 ×1）。
**Impact on plan:** 两项都是首个用户可见 GREEN 与测试数据库隔离正确性的必要条件，没有扩展产品范围。

## Issues Encountered

- 初次 Playwright 发现认证与 Agent 指向不同数据库，已按上述 Rule 1 修复。
- 内置浏览器实际走到注册和 Mailpit 验证码页面；提交验证码时临时本地 API 生命周期终止，页面显示“服务暂时不可用”。因此**不宣称内置浏览器验收通过**。同一正常注册→验证→登录→分析的真实 Playwright 路径已通过，后续应在稳定常驻服务下补一次内置浏览器验收。

## Browser Verification

- **尝试路径：** `http://127.0.0.1:4173/` → 创建账号 → 本地 Mailpit 读取验证码 → 验证邮箱。
- **结果：** 注册和验证码展示成功；验证码提交遇到临时服务不可用，未继续声称页面 Agent 流程通过。
- **自动化补充：** Playwright 的真实公开路径（注册、Mailpit 验证、登录、`/app/analyze`、输入“米饭 100 克”、获取报告与 SSE）通过。

## User Setup Required

None - 使用已有本地 PostgreSQL、Mailpit、受控 FDC seed 与 Fake Provider；没有新增外部密钥。

## Next Phase Readiness

- 后续 Agent 计划可在该纵向路径上增加追问、纠正、重试和删除，不得绕开 tenant-safe service、确定性 Nutrition Tool 或 snapshot/SSE 分治。
- 需要补做一次内置浏览器的稳定常驻服务验收，不能以本次 Playwright 代替该项目硬规则。

## Self-Check: PASSED

- 已确认 `f7bfc83`、`5719e48` 与真实 PG/E2E 测试工件存在。
- 已运行 mypy、Ruff、真实 PG integration、OpenAPI `check-all`、前端 typecheck/Vitest 和同名 Playwright E2E。

*Phase: 02-agent*
*Completed: 2026-08-29*
