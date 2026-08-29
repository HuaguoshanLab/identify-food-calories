---
phase: 02-agent
plan: 02
subsystem: testing
tags: [postgresql, psycopg, alembic, playwright, fail-closed]
requires:
  - phase: 01-engineering-auth-foundation
    provides: "Pydantic Settings、Alembic test guard、Docker PostgreSQL 合同与 Playwright 生命周期基础"
provides:
  - "受显式 env 文件约束、保持正式 URL 互异的 PostgreSQL child wrapper"
  - "安全 reset → migration → checkpointer → seed → Uvicorn 的唯一可审计启动器"
  - "Playwright 通过 wrapper 启动后端的配置与真实 child 合同"
affects: [agent-bootstrap, postgres-checkpointer, seed-importer, e2e]
tech-stack:
  added: []
  patterns: ["fail-closed PostgreSQL child wrapper", "guarded initialization order", "Playwright provisioning contract test"]
key-files:
  created:
    - backend/.env.test.example
    - backend/tests/run_pg.py
    - backend/scripts/run_initialized_app.py
    - backend/scripts/README.md
    - frontend/playwright.config.test.ts
  modified:
    - backend/tests/unit/test_test_database_guards.py
    - frontend/playwright.config.ts
    - frontend/vite.config.ts
    - backend/README.md
    - frontend/README.md
key-decisions:
  - "DATABASE_URL 保持 5432/food_agent_dev 开发哨兵，TEST_DATABASE_URL 保持 55432/food_agent_test；wrapper 不重绑两者。"
  - "所有破坏性启动步骤只接收 validate_test_database_configuration() 返回的测试目标。"
  - "Checkpointer 与 seed 尚未交付时启动器必须停止，不能跳过步骤或提前启动 Uvicorn。"
patterns-established:
  - "真实 PostgreSQL child 统一使用 python tests/run_pg.py --env-file .env.test.example -- COMMAND。"
  - "Playwright 不再裸跑 reset、Alembic 或 Uvicorn，而是调用唯一初始化器。"
requirements-completed: [AGT-04, QLT-02]
duration: 11min
completed: 2026-08-29
---

# Phase 02 Plan 02: PostgreSQL 测试启动链 Summary

**以互异的开发哨兵和隔离测试库为边界，固定 PostgreSQL reset、迁移、Checkpointer、seed 与 FastAPI 的 fail-closed 启动顺序。**

## Performance

- **Duration:** 11 min
- **Started:** 2026-08-29T11:54:30+08:00
- **Completed:** 2026-08-29T04:05:10Z
- **Tasks:** 2/2
- **Files modified:** 10

## Accomplishments

- 创建 `.env.test.example` 与 `tests/run_pg.py`；危险 URL、错误方言、非 loopback、端口/库名不匹配或 URL 同目标时，child 在执行前被拒绝且不回显密码。
- 创建唯一初始化器，严格执行安全 schema reset → Alembic head → Checkpointer setup → seed apply → Uvicorn；任一步失败不再继续。
- Playwright 改为从仓库根启动测试服务、再经 wrapper 调用初始化器；真实 child 测试确认正式变量保持互异。
- 已在真实 `postgres-test` 上验证 reset 和 0001→0003 Alembic 迁移；随后因后续计划尚未创建的 Checkpointer 命令安全停止，未启动 Uvicorn。

## Task Commits

1. **Task 1: 建立唯一 fail-closed PG wrapper（RED）** — `3bfa5cc` (`test`)
2. **Task 1: 建立唯一 fail-closed PG wrapper（GREEN）** — `c76937b` (`feat`)
3. **Task 2: 固定初始化顺序并接入 Playwright（RED）** — `41f8370` (`test`)
4. **Task 2: 固定初始化顺序并接入 Playwright（GREEN）** — `59a838e` (`feat`)

## Files Created/Modified

- `backend/tests/run_pg.py` — 仅从显式 env 文件取得正式变量并在启动 child 前验证 compose 测试目标。
- `backend/scripts/run_initialized_app.py` — 有序、fail-closed 的测试数据库准备和 FastAPI 启动入口。
- `backend/tests/unit/test_test_database_guards.py` — URL 危险矩阵、真实 child 环境、精确启动 trace 与失败终止合同。
- `frontend/playwright.config.ts`、`frontend/playwright.config.test.ts` — 受保护 provisioning 命令及其真实 wrapper child 验证。

## Decisions Made

- 正式 `DATABASE_URL` 不能为了测试而被改成 `TEST_DATABASE_URL`；两者互异是 guard 的安全前提，不是可选配置。
- 真实 schema reset 只允许消费由现有 `validate_test_database_configuration()` 返回的隔离 URL。
- 启动器不会以缺失 Checkpointer/seed 作为理由跳过步骤；其实现由 Plan 08 接入后才能完整成功。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] 让 Playwright 配置合同测试实际被 Vitest 发现**
- **Found during:** Task 2
- **Issue:** Vitest 只包含 `src/**/*.test.*`，仓库根的 `playwright.config.test.ts` 不会被计划指定命令执行。
- **Fix:** 将该单一配置合同文件加入 Vitest include；未扩大测试目录。
- **Files modified:** `frontend/vite.config.ts`
- **Verification:** `npm test -- --run playwright.config.test.ts` 通过 2 项测试。
- **Committed in:** `59a838e`

**2. [Rule 1 - Bug] 隐藏初始化 child 失败时的 URL 凭据**
- **Found during:** Task 2 的真实 PostgreSQL 启动
- **Issue:** `CalledProcessError` 默认渲染完整命令，导致失败 traceback 中出现测试 URL 密码。
- **Fix:** 将 child 失败转换为固定的 `InitializationStepError`，不保留命令参数；补充定向回归测试。
- **Files modified:** `backend/scripts/run_initialized_app.py`, `backend/tests/unit/test_test_database_guards.py`
- **Verification:** 30 项 guard 测试通过；真实启动失败输出不再包含凭据。
- **Committed in:** `59a838e`

---

**Total deviations:** 2 auto-fixed（1 个 Rule 1，1 个 Rule 2）。
**Impact on plan:** 两项修复均为测试可执行性或凭据保护所必需，没有扩展产品范围。

## Issues Encountered

- 常规沙箱不能访问本机 Docker socket 和 loopback PostgreSQL；使用受控权限在 `postgres-test` 上完成真实 reset 与迁移验证。
- `scripts/setup_checkpointer.py` 与 `app.nutrition.importer` 明确由 Plan 08 创建。当前启动器在该步骤安全停止，这是防止假绿的预期行为，不是回退。

## Known Stubs

| Stub | File | Reason |
|---|---|---|
| `setup_checkpointer` child 命令 | `backend/scripts/run_initialized_app.py` | Plan 08 将交付真实 `scripts/setup_checkpointer.py`；当前缺失时 fail closed。 |
| `apply_seed` child 命令 | `backend/scripts/run_initialized_app.py` | Plan 08 将交付受控 FDC importer；当前缺失时 fail closed。 |

## User Setup Required

None - Docker 测试服务已由项目 compose 合同提供；没有新增外部账号或密钥。

## Next Phase Readiness

- 后续真实 PostgreSQL 计划必须通过 `tests/run_pg.py` 并保留互异的正式 URL。
- Plan 08 需要实现并验证稳定的 `scripts/setup_checkpointer.py --database-url <guarded-test-url>` 和 `python -m app.nutrition.importer --apply ... --database-url <guarded-test-url>` 接口，之后重新运行 `run_initialized_app.py --prepare-only`。

## Self-Check: PASSED

- `backend/.env.test.example`、`backend/tests/run_pg.py`、`backend/scripts/run_initialized_app.py`、`frontend/playwright.config.test.ts` 和本 Summary 均已确认存在。
- `3bfa5cc`、`c76937b`、`41f8370`、`59a838e` 均存在于 Git 历史。

*Phase: 02-agent*
*Completed: 2026-08-29*
