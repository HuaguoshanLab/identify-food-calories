---
phase: 02-agent
plan: 14
subsystem: retention
tags: [postgresql, advisory-lock, langgraph-checkpointer, fastapi-lifespan, retention, tenant-isolation]
requires:
  - phase: 02-agent
    provides: "Agent ledger、PostgreSQL Checkpointer、FastAPI persisted runtime 与生命周期 supervisor"
provides:
  - "FastAPI lifecycle-owned PostgreSQL advisory-lease retention worker"
  - "精确 24h 删除、7d checkpoint/SSE 与 30d 最小审计清理边界"
  - "真实 PostgreSQL fake-clock、跨租户与 crash lease recovery 证据"
affects: [agent-api, agent-runtime, checkpointing, privacy, phase-02-release]
tech-stack:
  added: []
  patterns: ["database advisory lease", "earliest-eligibility scheduler", "tenant-scoped retention service", "fake-clock lifecycle proof"]
key-files:
  created:
    - backend/app/agent/retention.py
    - backend/tests/integration/test_agent_retention.py
  modified:
    - backend/app/agent/service.py
    - backend/app/agent/repository.py
    - backend/app/agent/supervisor.py
    - backend/app/agent/api.py
    - backend/app/main.py
    - backend/app/core/config.py
key-decisions:
  - "retention 互斥由 PostgreSQL session advisory lock 提供，进程崩溃后连接关闭会自动释放。"
  - "删除 intent 的 purge_after 固定为 requested_at + 24h - poll_interval，给最长五分钟调度保留 SLA 余量。"
  - "checkpoint 清理由 Checkpointer 的 adelete_thread 完成，ledger 清理始终使用 SQL tenant/thread 条件。"
patterns-established:
  - "后台保留任务由 lifespan 启动，不能依赖手工 CLI 或进程内 mutex。"
  - "边界调度使用 min(now + poll_interval, earliest_eligible_at)，不提前删除。"
requirements-completed: [AGT-04, AGT-07, QLT-02]
duration: 19min
completed: 2026-08-29
---

# Phase 02 Plan 14: D-18 自动保留与级联清理 Summary

**FastAPI 生命周期现在以 PostgreSQL advisory lease 自动执行 24 小时会话删除、7 天 Checkpoint/SSE 清理与 30 天最小审计清理，并由真实数据库证明租户隔离和崩溃恢复。**

## Performance

- **Duration:** 19 min
- **Started:** 2026-08-29T15:11:57+08:00
- **Completed:** 2026-08-29T15:30:00+08:00
- **Tasks:** 3/3
- **Files modified:** 13

## Accomplishments

- 生产环境要求显式配置 7d/30d/24h 与不超过 5 分钟的 poll interval；本地与测试保有安全值但生产绝不静默回退。
- `RetentionWorker` 由真实 FastAPI lifespan 启动，使用 PostgreSQL advisory lease、最早期限唤醒和 Checkpointer `adelete_thread()` 清理短期状态。
- 删除请求先持久化 tenant-bound intent；到期后只删除该 user/thread 的 checkpoint、事件和 ledger，其他 tenant 不受影响。
- 真实 PostgreSQL + fake clock 覆盖 24h-poll 间隔、7d/30d 精确边界、跨租户保留与连接丢失后的 lease 接管。

## Task Commits

1. **Task 1: 锁定 retention 配置与生命周期合同** — `25cf4a5`、`6b3f4e6`
2. **Task 2: 建立自动 lease retention worker** — `28db845`
3. **Task 3: 真实 PostgreSQL 证明 24h/7d/30d 与 lease（RED/GREEN）** — `7d09e7a`、`1f60aca`、`dab989b`

## Files Created/Modified

- `backend/app/agent/retention.py` — 实际生命周期 Worker、PostgreSQL lease、最早期限唤醒和无敏感内容的计数。
- `backend/app/agent/service.py`、`repository.py`、`ports.py` — tenant-scoped intent、候选选择与删除事务边界。
- `backend/app/agent/supervisor.py`、`backend/app/main.py` — 将 Worker 与 Checkpointer 接入实际 FastAPI lifespan。
- `backend/app/agent/api.py` — 认证删除操作先持久化 intent，再唤醒 Worker。
- `backend/tests/integration/test_agent_retention.py` — 真实 PostgreSQL 生命周期、时钟、租户和 lease 回归。

## Decisions Made

- 采用 session advisory lock 作为跨 worker 的 cleanup lease；连接关闭天然释放，避免僵尸 lease 或手工修复。
- 保留周期以 eligibility boundary 而不是粗粒度轮询为准，poll interval 只限制最晚唤醒时间。
- 业务 ledger 仍是所有权真相；Checkpointer 仅按显式 thread namespace 删除，不承担授权判定。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] 补齐持久化删除 intent 的公开接线**
- **Found during:** Task 2/3
- **Issue:** 原有 DELETE operation 仍是 501 sentinel，Worker 没有任何经过认证的方式接收用户删除请求。
- **Fix:** 在 API 通过 Service 持久化 intent 并唤醒生命周期 Worker；不暴露内部 checkpoint 或 raw state。
- **Files modified:** `backend/app/agent/api.py`, `backend/app/main.py`, `backend/app/agent/supervisor.py`
- **Verification:** 真实 PostgreSQL API→lifespan→worker 删除回归通过。
- **Committed in:** `1f60aca`

**2. [Rule 1 - Bug] 保持既有生产配置错误的确定性优先级**
- **Found during:** Task 3 回归
- **Issue:** retention 显式配置检查过早执行，遮蔽了既有 DeepSeek/Tracing 的 fail-closed 错误合同。
- **Fix:** 保留所有 retention 校验，但放在既有 Provider/Tracing 校验之后。
- **Files modified:** `backend/app/core/config.py`, `backend/tests/unit/test_agent_api_contract.py`
- **Verification:** 14 项 targeted unit tests、mypy 与 ruff 通过。
- **Committed in:** `1f60aca`

**3. [Rule 1 - Bug] 正确模拟 PostgreSQL session lease 的崩溃释放**
- **Found during:** Task 3 lease 回归
- **Issue:** 仅关闭 SQLAlchemy Session 会把连接归还连接池，session advisory lock 并未模拟进程崩溃释放。
- **Fix:** 测试关闭持锁 worker 的独立 Engine pool，再验证第二 worker 获取同一 lease。
- **Files modified:** `backend/tests/integration/test_agent_retention.py`
- **Verification:** 真实 PostgreSQL retention/checkpoint 套件 `5 passed`。
- **Committed in:** `dab989b`

**Total deviations:** 3 auto-fixed（Rule 2 ×1，Rule 1 ×2）。
**Impact on plan:** 均为 D-18 的可用性、安全边界或真实数据库证据所必需；未增加未授权的数据访问能力。

## Threat Flags

| Flag | File | Description |
|---|---|---|
| `threat_flag: deletion-api` | `backend/app/agent/api.py` | 新增认证删除入口；通过 Bearer 主体、Service tenant/thread 查询和持久化 deadline 限制删除范围。 |

## Known Stubs

None. 用户删除 UI 将由后续 Plan 15 接入；后端自动清理路径没有占位实现。

## User Setup Required

生产部署需显式设置 `RETENTION_CHECKPOINT_EVENT_DAYS=7`、`RETENTION_AUDIT_DAYS=30`、`RETENTION_DELETION_SLA_HOURS=24` 与不超过 300 秒的 `RETENTION_POLL_INTERVAL_SECONDS`。

## Next Phase Readiness

- Plan 15 可将既有 delete Agent thread operation 接到用户 H5，而不需要新增后台清理机制。
- 后续部署必须让每个应用实例都保留 PostgreSQL 连接能力；没有数据库 lease 时 Worker 不得退化为内存锁。

## Self-Check: PASSED

- `backend/app/agent/retention.py`、真实 PostgreSQL retention 测试和本 Summary 均存在。
- `25cf4a5`、`6b3f4e6`、`28db845`、`7d09e7a`、`1f60aca`、`dab989b` 均存在于 Git 历史。
- `tests/run_pg.py --env-file .env.test.example -- .venv/bin/python -m pytest tests/integration/test_agent_retention.py tests/integration/test_agent_checkpoint.py -q`：`5 passed`。

*Phase: 02-agent*
*Completed: 2026-08-29*
