---
phase: 04-meal-records-and-memory
plan: "06"
subsystem: infrastructure
tags: [postgresql, transactional-outbox, fastapi-lifespan, memory, concurrency]
requires:
  - phase: 04-05
    provides: auditable direct-memory ledger, provision outbox, and exact Provider request keys
provides:
  - one lifespan-owned PostgreSQL-lease worker that drains provision and delete intents
  - delete-wins state transitions before claim, before remote call, and after remote create
  - PostgreSQL evidence for concurrent direct capture and outcome-unknown recovery
affects: [04-07, agent-memory-write, memory-deletion]
tech-stack:
  added: []
  patterns: [claim-commit-recheck-bind, exact-request-key-recovery, delete-wins-outbox]
key-files:
  created:
    - backend/tests/integration/test_memory_direct_write_idempotency.py
  modified:
    - backend/app/agent/retention.py
    - backend/app/main.py
    - backend/app/memory/service.py
    - backend/app/memory/repository.py
key-decisions:
  - "外部 Provider 调用永远在 claim 提交之后、绑定前重查之后，不能持有 PostgreSQL 行锁。"
  - "outcome_unknown 只按稳定 request key resolve，绝不再次盲写 create。"
  - "删除后的 post-create bind 必须重开 durable delete intent，防止早期 no-op cleanup 留下远端记录。"
patterns-established:
  - "Provider outbox worker: 生命周期 worker 独占 lease，图节点和路由不领取 outbox。"
  - "跨 Session 行锁: recheck/bind 显式 populate_existing，再 FOR UPDATE，避免 ORM identity map 读取过期状态。"
requirements-completed: [MEM-03, MEM-04, MEM-05, MEM-06]
duration: 48min
completed: 2026-09-01
---

# Phase 4 Plan 06: Direct Memory Lifespan Worker Summary

**直接偏好通过 FastAPI lifespan 的 PostgreSQL lease worker 安全 provision，并在并发、未知结果和删除交错时保持零重复、删除优先。**

## Performance

- **Duration:** 48min
- **Completed:** 2026-09-01T03:01:19Z
- **Tasks:** 2/2
- **Files modified:** 12

## Accomplishments

- 将 direct-memory provision outbox 接入唯一的 lifespan retention worker；capture 只提交本地账本和 intent。
- 对 claim、外呼前 recheck、外呼后 bind 三个事务边界执行删除优先，未知结果只 exact-resolve request key。
- 使用真实 PostgreSQL 覆盖并发 capture、worker 重启、删除时序和跨用户隔离。

## Task Commits

1. **Task 1: 接线单一租约 worker，并实现删除胜过 provisioning 的三种竞争语义** - `4f47956` (feat)
2. **Task 2: 用真实 PostgreSQL 验证并发、outcome unknown 与删除残留为零** - `f615664` (test)
3. **竞态修复: 重查时强制刷新跨 Session 行状态** - `56a3264` (fix)

## Files Created/Modified

- `backend/app/agent/retention.py`、`backend/app/agent/supervisor.py`、`backend/app/main.py` — 将 provision callback 接入生命周期唯一 worker，并保留安全计数。
- `backend/app/memory/service.py`、`backend/app/memory/repository.py`、`backend/app/memory/ports.py` — 以 claim → commit → recheck → Provider → bind/delete-intent 实现 durable worker 协议。
- `backend/app/memory/providers.py` — Fake Provider 删除 direct record，模拟远端已清理的真实语义。
- `backend/tests/integration/test_agent_retention.py`、`backend/tests/integration/test_memory_direct_write_idempotency.py` — 真实 PG 时序、并发和 outcome-unknown 证据。
- `backend/tests/memory/test_memory_service.py`、`backend/tests/README.md`、`backend/tests/integration/README.md` — queued provisioning 单测与测试索引。

## Decisions Made

- 外部调用不能在数据库锁内执行；否则删除会被网络延迟阻塞并留下不可证明的时序漏洞。
- `outcome_unknown` 后只能解析 stable key；解析不到时有界失败，不能重试 create。
- 绑定前发现 ledger 已删除时不写回 external ID，也不重新激活账本，只补/重开删除 intent。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] 补齐 MemoryService/Repository 的 worker 事务契约**
- **Found during:** Task 1
- **Issue:** 04-05 的 service 会在 capture 路径直接调用 Provider，且无法表达 claim/recheck/bind 的跨事务删除优先语义。
- **Fix:** 将 direct provision 移到 lifespan callback，并增加 row-locked claim、recheck、unknown-result 和 delete-intent 协议。
- **Files modified:** `backend/app/memory/service.py`、`backend/app/memory/repository.py`、`backend/app/memory/ports.py`、`backend/app/memory/providers.py`、`backend/tests/memory/test_memory_service.py`
- **Verification:** memory 单测 11 passed；真实 PostgreSQL integration passed。
- **Committed in:** `4f47956`

**2. [Rule 1 - Bug] 强制刷新跨 Session 的 provision 行状态**
- **Found during:** Task 2 最终并发验证
- **Issue:** worker Session 的 identity map 可能在 recheck/bind 时保留删除前的 ledger，导致删除后继续 provision。
- **Fix:** 锁定前使用 `populate_existing=True`，确保每次外呼前/后都读取数据库当前状态。
- **Files modified:** `backend/app/memory/repository.py`、`backend/tests/integration/test_agent_retention.py`、`backend/tests/integration/test_memory_direct_write_idempotency.py`
- **Verification:** 隔离的生命周期边界测试 passed；最终 PostgreSQL suite passed。
- **Committed in:** `56a3264`

**Total deviations:** 2 auto-fixed（1 missing critical，1 bug）

## Known Stubs

None.

## Issues Encountered

- 一次组合执行中既有 retention 边界测试出现时序性失败；隔离复现通过，最终完整执行也通过。没有放宽断言或隐藏该测试。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 04-07 可以把 graph 的明确一人称偏好写入接到此 durable worker，并完成公开 API 与浏览器 E2E 验收。
- 本计划没有用户可见页面变更；浏览器验收留给 04-07。

## Self-Check: PASSED

- `04-06-SUMMARY.md` exists.
- Task commits `4f47956`, `f615664`, and `56a3264` exist.
