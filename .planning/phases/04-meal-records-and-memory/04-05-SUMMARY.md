---
phase: 04-meal-records-and-memory
plan: "05"
subsystem: memory
tags: [postgresql, alembic, mem0, idempotency, outbox]
requires:
  - phase: 04-02
    provides: tenant-bound preference ledger and deletion intent
  - phase: 04-03
    provides: safe personal-context retrieval boundary
provides:
  - source-run-audited direct preference ledger and cancellable provisioning intent
  - deterministic explicit-preference allowlist and infer=False Mem0 direct contract
affects: [04-06, 04-07, agent-memory-write]
tech-stack:
  added: [memory_provision_outbox, opaque request-key resolver]
  patterns: [local-ledger-first, PostgreSQL partial-unique-idempotency, exact-metadata-resolve]
key-files:
  created:
    - backend/migrations/versions/0009_direct_memory_provisioning.py
  modified:
    - backend/app/memory/service.py
    - backend/app/memory/providers.py
    - backend/app/memory/repository.py
    - backend/app/records/models.py
decisions:
  - "Direct writes commit their local ledger and provision intent before Provider I/O."
  - "Only deterministic first-person allowlist matches can write automatically; image, parser and model observations cannot."
  - "Mem0 direct writes resolve an exact opaque request key first, use infer=False, and accept exactly one returned ID."
metrics:
  duration: 12m
  completed: 2026-09-01
---

# Phase 4 Plan 05: Direct Memory Provisioning Summary

直接表达的饮食偏好现在会以可审计、可取消、幂等的本地 ledger/outbox 先落库，并仅以单条 `infer=False` canonical record 写入 Mem0。

## Completed Tasks

### Task 1: 直接偏好账本与 provisioning/delete 协调状态

- 新增 `0009` Alembic migration：source run、opaque request-key digest、provisioning 状态、`memory_provision_outbox` 与 PostgreSQL partial unique idempotency constraints。
- 同一用户对同一 canonical 偏好的同 run / 跨 run 重复陈述复用 active ledger；不同用户永远隔离。
- 删除在 Provider claim 前会原子取消 pending intent；若已经 claim 或外部 ID 未绑定，则保留可重试的删除 intent。

### Task 2: 白名单提取与 infer=False Provider 合同

- 新增 `explicit-preference.v1` 的确定性一人称提取：当前支持忌口、目标和稳定偏好；视觉、解析结果、历史和模型推测不会自动写入。
- Fake Provider 记录 exact request key 和 `infer=False`，且每个 key 只对应一个 canonical direct record。
- Mem0 adapter 先用 user-scoped metadata exact resolver 查找 request key；不存在才调用 `add(..., infer=False)`，并在零个或多个 ID 时 fail closed。

## Verification

- `uv run python tests/run_pg.py --env-file .env.test.example -- uv run alembic upgrade head`
- `uv run pytest tests/memory/test_memory_service.py tests/unit/test_memory_api.py -q` → `13 passed`
- `uv run python tests/run_pg.py --env-file .env.test.example -- uv run pytest tests/integration/test_memory_deletion_chain.py tests/integration/test_retrieval_isolation.py -q` → `2 passed`
- `uv run ruff check app/memory/providers.py app/memory/service.py app/memory/ports.py app/memory/repository.py app/records/models.py migrations/versions/0009_direct_memory_provisioning.py tests/memory/test_memory_service.py tests/unit/test_memory_api.py tests/integration/test_memory_deletion_chain.py` → passed

## Decisions Made

- 先提交本地 ledger 与 outbox，再进行外部 Provider I/O；这使重试、删除竞争和未知外部结果都有权威恢复点。
- request key 是不对外暴露的 SHA-256 opaque value；ledger 保存其 digest，durable intent 保存 key 以支持 exact remote resolve。
- 直接写固定使用 Mem0 `infer=False`，避免 Provider 从一条用户已确认的 canonical 表达再拆分或推断更多事实。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 更新真实 PostgreSQL 删除链测试以匹配 provision-first 合同**
- **Found during:** Task 2
- **Issue:** 旧集成测试假定 `create_direct()` 会同步外呼；新的正确合同先创建 pending intent，未 provision 前删除应取消而不是创建 deletion outbox。
- **Fix:** 测试先执行 `process_due_provisioning()`，再验证已写入外部副本的删除重试链。
- **Files modified:** `backend/tests/integration/test_memory_deletion_chain.py`
- **Commit:** `3788e4b`

## Known Stubs

None.

## Self-Check: PASSED

- 已确认 migration、memory service 与 Provider 文件存在。
- 已确认 TDD RED/GREEN commits `bf6fc89`, `f4c742b`, `a6d5e8f`, `3788e4b` 存在。
