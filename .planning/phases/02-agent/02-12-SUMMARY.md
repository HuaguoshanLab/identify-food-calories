---
phase: 02-agent
plan: 12
subsystem: agent-recovery
tags: [langgraph, postgresql, checkpointer, sse, react, playwright, frozen-evals]
requires:
  - phase: 02-agent
    provides: "认证纵向 GREEN、Agent ledger、PostgreSQL Checkpointer、租约与 14-case 冻结前缀"
provides:
  - "预算前置截断、单次瞬时 Provider 重试和稳定 Graph 失败语义"
  - "真实 Saver 重开 checkpoint、snapshot-first SSE 与刷新同线程恢复"
  - "24-case append-only hash 链及 persistence/isolation、budget、adversarial 覆盖"
affects: [agent-observability, retention, evaluation, release-report]
tech-stack:
  added: []
  patterns: ["cumulative checkpoint budget with per-run delta ledger", "snapshot-first Last-Event-ID replay", "append-only safety eval categories"]
key-files:
  created:
    - backend/tests/integration/test_agent_checkpoint.py
    - frontend/src/features/agent/stream/useAgentEventStream.test.ts
  modified:
    - backend/app/agent/graph.py
    - backend/app/agent/service.py
    - frontend/src/features/agent/stream/useAgentEventStream.ts
    - frontend/src/features/agent/components/AnalyzePage.tsx
    - backend/evals/phase02-cases.jsonl
key-decisions:
  - "Checkpoint 的预算计数跨同一线程累计保障上限，AgentRun 只记录本次执行相对 checkpoint 的增量。"
  - "SSE 永远先读取权威 snapshot；事件仅更新安全进度，使用 Last-Event-ID 去重与一次 gap 重放。"
  - "冻结集的异常值/工具失败只归 validation_budget，注入和医疗越界只归 adversarial。"
patterns-established:
  - "每次 Provider/tool 前检查五类预算；只对明确 TRANSIENT Provider 错误重试一次。"
  - "URL 只保存 tenant-protected thread_id，绝不保存 access token；刷新后仍从公开 snapshot 恢复。"
requirements-completed: [AGT-04, AGT-05, AGT-06, AGT-07, ARC-05, QLT-02]
duration: 70min
completed: 2026-08-29
---

# Phase 02 Plan 12: 崩溃恢复、SSE 重连与最终冻结集 Summary

**Agent 现在在真实 PostgreSQL Saver 重开后保持同线程状态，以预算前置截断和单次瞬时重试限制自治执行，并通过 snapshot-first SSE 恢复安全进度。**

## Performance

- **Duration:** 70 min
- **Completed:** 2026-08-29T06:10:43Z
- **Tasks:** 2/2
- **Files modified:** 19

## Accomplishments

- Graph 在下一次 node、Provider 或 tool 调用前检查 12 steps、4 model calls、12 tool calls、45s active time 和 0.02 USD；等待用户输入不记 active time，且仅 TRANSIENT Provider 失败自动重试一次。
- 真实 PostgreSQL 测试证明 Saver 关闭再打开后按同一 `thread_id` 恢复；预算 ledger 按 checkpoint 增量记账，避免 correction run 误报旧 Provider 调用。
- H5 先读取权威 snapshot，再以 `eventsource-parser` 处理 CRLF/分片/多行 data/UTF-8 SSE，使用 `Last-Event-ID` 去重并对 gap 重新拉取 snapshot；URL 仅保存受服务端所有权保护的 thread id。
- 冻结集从 14 例扩到 24 例，保留旧 hash 前缀，新增 5 persistence/isolation、3 validation/budget、2 adversarial，并以 fail-closed validator 分类。

## Task Commits

1. **Task 1: 证明 Checkpointer/lease/预算恢复边界（RED）** — `066e5c1`
2. **Task 1: 证明 Checkpointer/lease/预算恢复边界（GREEN）** — `0f10001`
3. **Task 1: 修复 checkpoint 预算增量记账** — `d99af76`
4. **Task 2: 完成 snapshot-first SSE 与最后 10 个案例（RED）** — `699cefd`
5. **Task 2: 完成 snapshot-first SSE 与最后 10 个案例（GREEN）** — `d75fd68`

## Files Created/Modified

- `backend/app/agent/{graph.py,service.py,supervisor.py}` — 有界执行、稳定失败映射、run 增量计费与可注入租约时钟。
- `backend/tests/integration/test_agent_checkpoint.py` — fake clock/provider 预算测试与真实 PostgreSQL Saver 重开证明。
- `frontend/src/features/agent/stream/{useAgentEventStream.ts,useAgentEventStream.test.ts}` — snapshot-first、事件流解析、序号去重与 gap 回放。
- `frontend/src/features/agent/components/AnalyzePage.tsx` — 受保护 URL thread 恢复，报告仍只来自权威 snapshot。
- `frontend/tests/e2e/agent.spec.ts` — 刷新同一 thread 后不提交第二个分析命令的真实浏览器合同。
- `backend/evals/{phase02-cases.jsonl,validate_dataset.py}` — 24-case hash 链与新增安全类别校验。

## Decisions Made

- Graph State 保存累计预算以防止重新开启线程状态绕过上限；新 AgentRun 的账本指标扣除 checkpoint 基线，避免把已完成调用重复计费。
- 401 刷新/replay 继续由 `AuthProvider.request` 的唯一 single-flight 流程处理；SSE hook 不读取 token，也不会自行产生刷新循环。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 按 checkpoint 基线记录新 correction run 的调用指标**

- **Found during:** Task 1 的真实 PostgreSQL 纵向回归。
- **Issue:** correction run 从包含历史 budget 的 checkpoint 开始，直接写入累计 model/tool 计数会将旧 Provider 调用错误归入新 run。
- **Fix:** 从持久 checkpoint budget 计算增量后写入本 run ledger，累计 State 仍用于全线程上限。
- **Files modified:** `backend/app/agent/service.py`
- **Verification:** `tests/run_pg.py … pytest test_agent_checkpoint.py test_agent_vertical.py -q`：5 passed。
- **Committed in:** `d99af76`

**2. [Rule 2 - Missing Critical] 让刷新后的页面恢复同一 tenant-protected thread**

- **Found during:** Task 2。
- **Issue:** 仅有 stream hook 不能在整页刷新后找回 thread id，导致无法满足 D-15 的同线程恢复。
- **Fix:** 将非敏感 thread id 放入 URL query，刷新后先调用公开 snapshot；服务端所有权校验仍是唯一授权边界，未持久化 token 或报告。
- **Files modified:** `frontend/src/features/agent/components/AnalyzePage.tsx` 及其测试/目录索引。
- **Verification:** 前端 93 tests、typecheck、lint、build 通过；新增 Playwright 合同已写入。
- **Committed in:** `d75fd68`

**3. [Rule 2 - Missing Critical] 扩展冻结集 validator 的安全类别**

- **Found during:** Task 2。
- **Issue:** 旧 validator 只能表达 happy、missing、correction 和 validation_budget，不能 fail-closed 校验 persistence/isolation 与 adversarial 例。
- **Fix:** 增加三类严格分类和标签约束，旧 14-case hash 前缀不改动。
- **Files modified:** `backend/evals/validate_dataset.py`、`backend/tests/unit/test_eval_dataset.py`、`backend/evals/phase02-cases.jsonl`。
- **Verification:** 24-case validator 与 3 项单元测试通过。
- **Committed in:** `d75fd68`

**Total deviations:** 3 auto-fixed（Rule 1 ×1，Rule 2 ×2）。
**Impact on plan:** 全部为恢复正确性、用户刷新路径与冻结评测完整性所必需；未扩大 Agent 业务范围。

## Issues Encountered

- 真实 PostgreSQL 需要受控权限访问隔离的 `food_agent_test`；同一 guarded wrapper 下 Checkpointer 与纵向 API/SSE 回归均通过。
- 遗留测试服务停止后，真实 Playwright reconnect E2E 已通过：刷新后仍显示同一报告，且没有第二个分析 POST。
- 已尝试连接内置浏览器完成真实页面验收，但当前 Codex 会话没有可用浏览器实例；不能以 Playwright 或截图替代这项人工浏览器证据。

## Known Stubs

None. 失败类别、snapshot 恢复和 24-case 数据均有实际实现；未成功运行的 E2E 是环境门，不是功能占位。

## User Setup Required

None - 使用现有本地 PostgreSQL、Mailpit 与 Fake Provider；无新增外部密钥或账号。

## Next Phase Readiness

- 在有可用内置浏览器实例的会话中完成注册/登录 → “米饭 100 克” → 刷新 → 同一报告恢复的真实路径验收。

## Self-Check: PASSED

- 已确认关键测试、stream hook 与 Summary 存在。
- 已确认 `066e5c1`、`0f10001`、`d99af76`、`699cefd`、`d75fd68` 均存在于 Git 历史。
