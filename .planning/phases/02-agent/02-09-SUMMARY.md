---
phase: 02-agent
plan: 09
subsystem: api-contract
tags: [fastapi, openapi, zod, typescript, bearer-authentication, contract-drift]
requires:
  - phase: 01-engineering-auth-foundation
    provides: "权威 Bearer access-token/session 验证与前端内存认证请求边界"
  - phase: 02-agent
    provides: "Agent ledger、Graph runtime factory 合同和前端 agent API 目录边界"
provides:
  - "六个稳定 operationId 的 Bearer-protected Agent v1 public sentinel"
  - "运行时 OpenAPI 到 frozen JSON、TS/Zod 与 operation client 的机械生成/逐字漂移门"
affects: [agent-api, agent-runtime, sse, frontend-agent-ui, vertical-green]
tech-stack:
  added: []
  patterns: ["runtime OpenAPI as the single contract input", "temporary byte-for-byte contract drift check", "authenticated 501 sentinel"]
key-files:
  created:
    - backend/app/agent/api.py
    - backend/app/agent/schemas.py
    - backend/openapi-agent-v1.json
    - frontend/src/features/agent/api/generate-contracts.mjs
    - frontend/src/features/agent/api/schemas.generated.ts
    - frontend/src/features/agent/api/client.generated.ts
  modified:
    - backend/app/main.py
    - backend/app/agent/graph.py
    - frontend/src/features/agent/api/README.md
key-decisions:
  - "冻结的 Agent JSON、TS、Zod 与 client 全部从 create_app().openapi() 生成，禁止以 frozen JSON 为输入反推。"
  - "在真实执行链到位前，所有已认证 Agent operation 统一返回 AGENT_NOT_IMPLEMENTED/501，禁止假成功。"
patterns-established:
  - "浏览器 operation client 只调用 requestWithAccess，既不直接 fetch 也不读取或持久化 token。"
  - "FastAPI 生命周期只委托一个 runtime factory；当前 no-op 不能在请求路径中隐式初始化持久资源。"
requirements-completed: [AGT-02, AGT-04, ARC-05, QLT-02]
duration: 24min
completed: 2026-08-29
---

# Phase 02 Plan 09: Agent API Sentinel 与机械合同生成 Summary

**六个经真实 Bearer 验证的 Agent v1 operation 先以统一 501 sentinel 冻结，并从实际 FastAPI OpenAPI 逐字生成浏览器 TypeScript、Zod 与请求客户端。**

## Performance

- **Duration:** 24 min
- **Completed:** 2026-08-29T05:10:19Z
- **Tasks:** 2/2
- **Files modified:** 13

## Accomplishments

- 预声明 create、input、snapshot、events、retry、delete 六个稳定 operationId；未认证请求返回 401，经过同一 access-token/session 验证后的请求返回 `AGENT_NOT_IMPLEMENTED`/501。
- 新增独立 HTTP schema，明确从 ORM、LangGraph State 和 Provider DTO 隔离；状态在公共合同中一次性覆盖 waiting、partial、completed、retryable、terminal 与 deletion_pending。
- 实现 `generate-all` / `check-all`：子进程执行 `create_app().openapi()`，抽取 Agent operation 后生成 frozen JSON、同文件 TS/Zod schema 和认证 operation client；检查在临时目录重建并逐字比较所有工件。
- FastAPI lifespan 只经 no-op runtime factory 预留一次初始化位置，后续运行时接线不会被塞入路由或请求处理。

## Task Commits

1. **Task 1: 预声明完整 Agent v1 公共 operations（RED）** — `7d83669` (`test`)
2. **Task 1: 预声明完整 Agent v1 公共 operations（GREEN）** — `ddbd061` (`feat`)
3. **Task 2: 建立 runtime OpenAPI 四类生成与 501 sentinel 合同** — `f9ff66f` (`feat`)

## Files Created/Modified

- `backend/app/agent/{api,schemas}.py` — 六个安全 operation、501 error envelope 与独立公共 DTO。
- `backend/app/{main.py,agent/graph.py}` — 单一 lifespan factory seam 与明确 no-op 实现。
- `backend/openapi-agent-v1.json` — 从真实 FastAPI runtime 生成的 Agent-only frozen contract。
- `frontend/src/features/agent/api/{generate-contracts.mjs,schemas.generated.ts,client.generated.ts}` — 机械生成器、Zod/TS 产物与唯一认证 client。
- `backend/tests/unit/test_agent_api_contract.py` — HTTP 401/501 与 operationId 的 TDD 合同。
- `backend/app/agent/README.md`、`backend/README.md`、`frontend/src/features/agent/api/README.md`、`backend/tests/unit/README.md` — 文件职责与索引。

## Decisions Made

- 操作 client 接受内存中的 access token 参数，并只通过既有 `requestWithAccess` 发送；不读取 localStorage、query token 或直接 `fetch`。
- Frozen 工件只保存从 runtime 提取的 Agent API slice 与其递归引用的 component，避免无关认证端点变化制造噪音，同时不允许遗漏本 slice 的 schema drift。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] 为 FastAPI lifespan 增加显式 no-op runtime factory**
- **Found during:** Task 1
- **Issue:** 计划要求 main lifespan 委托 runtime factory，但既有 Protocol 只允许返回真实 runtime；若直接在 main 中跳过 factory，后续会重新引入请求期初始化和资源生命周期漂移。
- **Fix:** 将 factory 返回类型明确为可空，并在 `graph.py` 提供 `NoopAgentRuntimeFactory`；`main.py` 无条件委托它而不创建持久资源。
- **Files modified:** `backend/app/agent/graph.py`, `backend/app/main.py`
- **Verification:** Agent API TestClient 合同、`mypy app` 和 Ruff 均通过。
- **Committed in:** `ddbd061`

**2. [Rule 1 - Bug] 修复生成器的仓库根目录与浏览器 API 前缀解析**
- **Found during:** Task 2
- **Issue:** 初版生成器从嵌套目录上溯一级过多，找不到后端虚拟环境；并且 client 会把 `/api/v1` 再交给已自带该前缀的认证 request helper，造成双前缀请求。
- **Fix:** 使用正确的五级根路径，并在生成 client 时将公开 OpenAPI 的 `/api/v1` 前缀转换为 helper 所需的相对路径。
- **Files modified:** `frontend/src/features/agent/api/generate-contracts.mjs`
- **Verification:** `generate-all`、`check-all`、前端 typecheck/lint 和 90 项前端回归全部通过。
- **Committed in:** `f9ff66f`

---

**Total deviations:** 2 auto-fixed（Rule 2 ×1，Rule 1 ×1）。
**Impact on plan:** 都是生命周期与公开请求路径正确性的必要修复，没有扩大产品范围。

## Known Stubs

| Stub | File | Reason |
|---|---|---|
| `AGENT_NOT_IMPLEMENTED` 501 sentinel | `backend/app/agent/api.py` | 这是本计划的安全目标：在 02-10 接通真实所有权、Graph 与结果链之前，公开 operation 不能伪造成功。 |
| no-op runtime factory | `backend/app/agent/graph.py` | 02-10 才注入已初始化的真实运行时；当前 factory 只固定生命周期边界。 |

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 02-10 可以只填真实执行与公开响应，不应新增 operation、手写 DTO 或修改 client 结构。
- 每次变更 Agent HTTP schema 后必须运行 `node frontend/src/features/agent/api/generate-contracts.mjs generate-all`、`check-all` 与 `npm run typecheck`。

## Verification

- `cd backend && .venv/bin/python -m pytest tests/unit -q`：67 passed
- `cd backend && .venv/bin/python -m mypy app && .venv/bin/python -m ruff check app tests/unit/test_agent_api_contract.py`：PASS
- `cd frontend && node src/features/agent/api/generate-contracts.mjs generate-all && node src/features/agent/api/generate-contracts.mjs check-all`：PASS
- `cd frontend && npm run typecheck && npm test && npm run lint`：90 passed，PASS

## Self-Check: PASSED

- 已确认 `api.py`、`schemas.py`、`openapi-agent-v1.json`、生成器、两个生成 TypeScript 文件和本 Summary 均存在。
- 已确认 `7d83669`、`ddbd061` 与 `f9ff66f` 均存在于 Git 历史。

*Phase: 02-agent*
*Completed: 2026-08-29*
