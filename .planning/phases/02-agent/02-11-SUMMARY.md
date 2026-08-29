---
phase: 02-agent
plan: 11
subsystem: agent-followup
tags: [langgraph, postgres, fastapi, react, sse, frozen-evals]
requires:
  - phase: 02-agent
    provides: "认证 Agent 首个纵向 GREEN、受控 FDC 目录、tenant-safe ledger、Checkpointer 与机械 API 合同"
provides:
  - "单次集中追问、同线程 checkpoint 恢复与无重复解析"
  - "partial 披露、候选显式选择和 dirty-item 定向修正"
  - "5 happy、5 missing/ambiguity、4 correction 的 append-only 冻结评测链"
affects: [agent-retry, retention, observability, evaluation, frontend-agent]
tech-stack:
  added: []
  patterns: ["stable latest checkpoint upsert", "validated text-to-Command resume", "authoritative snapshot clarification UI", "dirty-item deterministic recalculation"]
key-files:
  created: []
  modified:
    - backend/app/agent/state.py
    - backend/app/agent/graph.py
    - backend/app/agent/service.py
    - backend/app/agent/api.py
    - frontend/src/features/agent/components/AnalyzePage.tsx
    - backend/evals/phase02-cases.jsonl
key-decisions:
  - "冻结 HTTP 合同仍只接收 text；服务端仅将可验证的 JSON 或单题文本转换为 Command(resume=...)。"
  - "每个 thread 只保留最新可恢复 checkpoint，使用稳定 checkpoint id 和递增 blob version 避免恢复旧等待状态。"
  - "候选默认不选中，未知项目以 partial/unaccounted_items 明示，不能补零。"
patterns-established:
  - "Graph 只消费 State、Provider 与 NutritionToolAdapter；Service 在 tenant ownership 校验后读取 Checkpointer 并构造 Command。"
  - "恢复和修正只计算 dirty item；既有 Provider 调用和未受影响的确定性结果保持不变。"
requirements-completed: [AGT-02, AGT-03, AGT-04, AGT-06, NUT-02, NUT-03, NUT-04, NUT-05, QLT-02]
duration: 12min
completed: 2026-08-29
---

# Phase 02 Plan 11: 集中追问、partial 与定向修正 Summary

**餐食分析现在会一次展示全部缺失/歧义信息，在同一用户线程恢复而不重复解析，并且只重算被修正的受控目录项目。**

## Performance

- **Duration:** 12 min
- **Started:** 2026-08-29T13:37:44+08:00
- **Completed:** 2026-08-29T13:50:22+08:00
- **Tasks:** 2/2
- **Files modified:** 18

## Accomplishments

- Graph State 保存稳定 item id、输入版本、集中问题、候选和已取得的确定性结果；waiting resume 不重新调用 Provider。
- API 在所有权验证后从同一 Checkpointer 恢复；完成线程只接受定向修正，新餐仍需创建新 thread。SSE 继续只发送安全摘要，报告始终来自权威 snapshot。
- H5 展示已理解项目、全部问题和最多三个候选；候选初始不选中。partial 和警告使用文字与图标，修正和排除不会在浏览器计算营养值。
- 真实 PostgreSQL 测试覆盖缺克数→恢复→改量，证明恢复 run 仍为一次模型调用；冻结 JSONL 从 5 例扩展到 14 例，旧 prefix hash 不变。

## Task Commits

1. **Task 1: 实现可重入集中追问与局部重算** — `76c7ed6` (`feat`)
2. **Task 2: 接通 H5 并追加 9 个语义案例（RED）** — `40717d8` (`test`)
3. **Task 2: 接通 H5 并追加 9 个语义案例（GREEN）** — `dea5c59` (`feat`)

## Files Created/Modified

- `backend/app/agent/{state,graph,service,api}.py` — 集中 interrupt payload、validated Command resume、checkpoint 最新状态与 partial/report presenter。
- `backend/tests/{unit/test_runtime_foundation.py,integration/test_agent_vertical.py}` — Graph dirty-item 证明与真实 PG/API/checkpoint 恢复回归。
- `frontend/src/features/agent/components/AnalyzePage.tsx` — 可访问集中追问、候选选择、partial 提示和定向修正界面。
- `backend/evals/{phase02-cases.jsonl,validate_dataset.py}` — 14-case immutable hash chain 与 missing/correction 分类校验。
- `frontend/src/features/agent/stream/useAgentEventStream.ts` — 将 callback ref 更新放到 effect，满足 React lint 生命周期规则。

## Decisions Made

- 公共 OpenAPI 不增加原始 Graph State 字段；多项追问的 UI 将受控答案编码为 text 内的严格 JSON，单一克数/候选可用文本解析。
- Checkpointer 不承担业务授权或审计，但作为每个用户 thread 的最新短期恢复状态；状态 blob 每次写入使用新 version，防止 stale waiting snapshot。
- 目录外项目不伪造数值：有已知项目时完成为 partial，并清楚列出未计入项目。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] 修复 Checkpointer 恢复到旧 waiting 状态**

- **Found during:** Task 2 的真实 PostgreSQL 恢复/修正测试。
- **Issue:** fresh checkpoint id 和固定 blob version 可能让 saver 读取旧等待状态，导致完成后的修正失败。
- **Fix:** 使用 thread UUID 作为 latest checkpoint id，并为每次持久化生成新的 state blob version。
- **Files modified:** `backend/app/agent/service.py`, `backend/tests/integration/test_agent_vertical.py`
- **Verification:** 真实 PG/API 缺克数→恢复→150g 修正通过，且 correction run 的 `model_calls == 0`。
- **Committed in:** `dea5c59`

**2. [Rule 2 - Missing Critical] 让等待态权威 snapshot 携带已聚合的问题**

- **Found during:** Task 2 的 API 集成测试。
- **Issue:** snapshot presenter 只读取 completed event，H5 无法安全渲染 waiting interrupt。
- **Fix:** 仅读取安全 `waiting_input`/`completed` business event 中的 report；SSE 格式不变且不泄露 payload。
- **Files modified:** `backend/app/agent/api.py`, `backend/tests/integration/test_agent_vertical.py`
- **Verification:** 真实 API 返回一个包含全部 questions 的 waiting snapshot。
- **Committed in:** `dea5c59`

**3. [Rule 1 - Bug] 修复现有 SSE hook 的 render 期 ref 写入**

- **Found during:** Task 2 前端 lint。
- **Issue:** `useAgentEventStream` 在 render 中写 ref，违反 React hooks lint，阻断本计划质量门。
- **Fix:** 移到依赖 `onEvent` 的 effect，不改变 SSE 的只读事件边界。
- **Files modified:** `frontend/src/features/agent/stream/useAgentEventStream.ts`
- **Verification:** 前端 typecheck、Vitest 与 ESLint 通过。
- **Committed in:** `dea5c59`

**4. [Rule 2 - Missing Critical] 扩展冻结集校验器以拒绝伪造的修正案例**

- **Found during:** Task 2 append-only 14-case 验收。
- **Issue:** 原 validator 只认可 happy/missing/budget，且 CLI 强制未在计划命令中提供的 happy-tag 参数，无法安全验证 correction composition。
- **Fix:** 增加 correction 语义/历史/resume payload 校验，并保持旧 5 case hash 不变。
- **Files modified:** `backend/evals/validate_dataset.py`, `backend/tests/unit/test_eval_dataset.py`, `backend/evals/phase02-cases.jsonl`
- **Verification:** 9 项 unit tests 与 14-case composition validator 通过。
- **Committed in:** `dea5c59`

**Total deviations:** 4 auto-fixed（Rule 2 ×3，Rule 1 ×1）。
**Impact on plan:** 全部为恢复正确性、snapshot 可用性、质量门和冻结评测完整性所必需；没有改变公开 nutrition truth 或 Graph/ORM 边界。

## Issues Encountered

- 内置浏览器已真实进入 `/app/analyze` 并按产品路由跳转到登录页。继续完成登录会在浏览器中发送测试邮箱和密码；当前会话未获得该敏感数据传输的即时授权，因此没有越过登录表单，也不宣称已完成浏览器端到端验收。

## Browser Verification

- **已验证路径：** `http://127.0.0.1:4173/app/analyze` → `/login?returnTo=%2Fapp%2Fanalyze`。
- **观察结果：** 未认证访问正确进入登录页，登录页具有邮箱、密码与继续入口。
- **待确认：** 获得即时授权后，用本地测试账号走注册/验证/登录 → 输入“米饭” → 补充“100 克” → 改为“150 克”的实际浏览器路径。

## User Setup Required

None - 未新增外部密钥或服务。

## Next Phase Readiness

- 02-12 可以在保持 tenant-safe snapshot/SSE 分治的前提下增加断流恢复与更丰富的 partial/排除场景。
- 后续任何恢复节点必须保留 stable item id/input version/dirty set，禁止重新调用已完成的 Provider 或工具。
- 浏览器端到端验收仍需要在本地测试 H5 中提交测试账号凭据的即时授权。

## Self-Check: PASSED

- 已确认 `76c7ed6`、`40717d8`、`dea5c59` 与所有关键实现/测试/冻结集工件存在。
- 已运行 mypy、Ruff、9 项 unit tests、真实 PostgreSQL 专项回归（4 passed）、OpenAPI `check-all`、前端 Vitest/typecheck/lint 与 14-case validator。

*Phase: 02-agent*
*Completed: 2026-08-29*
