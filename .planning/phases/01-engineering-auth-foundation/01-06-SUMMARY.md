---
phase: 01-engineering-auth-foundation
plan: 06
subsystem: authentication-database
tags: [postgresql, sqlalchemy, alembic, rate-limit, hmac, concurrency]

requires:
  - phase: 01-engineering-auth-foundation/01-05
    provides: 非枚举登录、数据库权威用户、session 与 refresh token 事务边界
provides:
  - 跨 worker/重启持久化的 PostgreSQL 权威登录失败限流
  - 不保存 raw 邮箱/IP 的 principal/source HMAC bucket
  - 0001→0002 空库迁移、约束、savepoint 与并发阈值真实 PostgreSQL 证据
affects: [01-09, 01-10, login-ui, auth-observability, deployment]

tech-stack:
  added: []
  patterns: [PostgreSQL atomic upsert rate limit, secret-scoped HMAC buckets, injected clock]

key-files:
  created: [backend/migrations/versions/0002_login_attempts.py, backend/tests/auth/test_login_rate_limit_service.py, backend/tests/integration/test_auth_database_protocols.py]
  modified: [backend/app/auth/models.py, backend/app/auth/ports.py, backend/app/auth/repository.py, backend/app/auth/service.py, backend/app/auth/api.py]

key-decisions:
  - "登录失败同时累计规范化 principal 与 source 两个 HMAC v1 bucket；数据库不保存 raw 邮箱或网络来源。"
  - "失败阈值固定为 5 次/5 分钟，封禁 5 分钟；窗口与 retry_after 只使用注入时钟计算。"
  - "Repository 使用 PostgreSQL INSERT ON CONFLICT DO UPDATE RETURNING 原子累计，Service 保留 commit/rollback 和稳定错误语义。"

patterns-established:
  - "限流检查在账号查询和 Argon2 前执行，bucket 与账号是否存在无关；非限流失败仍执行一次 Argon2。"
  - "成功登录在同一 Service 事务删除 principal/source bucket 并创建 session/refresh token。"

requirements-completed: [AUTH-02, ARC-02, ARC-04, ARC-07]

duration: 19 min
completed: 2026-08-27
---

# Phase 1 Plan 6: 数据库权威登录限流与 PostgreSQL 协议 Summary

**HMAC-only 双 bucket 与 PostgreSQL 原子 upsert 让登录限流在多 worker、重启和并发阈值下保持确定，并由真实迁移/事务测试证明。**

## Performance

- **Duration:** 19 min
- **Started:** 2026-08-27T07:41:22Z
- **Completed:** 2026-08-27T07:59:59Z
- **Tasks:** 2
- **Files modified:** 15

## Accomplishments

- 新增 `login_attempts` revision 0002，只持久化 64 字符 HMAC digest、失败次数、窗口和封禁时间；revision 严格接续 0001 且可降级回 0001。
- principal/source 两个 bucket 使用 PostgreSQL conflict row lock 原子累计；5 路并发失败严格得到 4 次统一认证失败与 1 次封禁，不依赖进程内状态或 `sleep`。
- 登录成功删除两个 bucket；窗口到期通过注入时钟确定性复位；429 统一返回 `RATE_LIMITED` 与安全的 `retry_after`，不泄露邮箱、密码、IP 或账号状态。
- 真实 PostgreSQL 证明 normalized email、current challenge、refresh token 约束，以及 savepoint rollback；完整后端回归 64 项全绿，无 skip。

## Task Commits

1. **Task 1 RED: 定义数据库权威登录限流合约** - `303daca` (test)
2. **Task 1 GREEN: 实现 HMAC bucket 与 PostgreSQL 原子限流** - `06ed5d9` (feat)
3. **Task 2: 证明 migration/Repository/并发数据库协议** - `40da8fa` (test)

## Files Created/Modified

- `backend/app/auth/models.py` - `LoginAttempt` HMAC-only ORM 模型和数据库约束。
- `backend/app/auth/ports.py` - 限流检查、失败累计与成功复位 Repository port。
- `backend/app/auth/repository.py` - PostgreSQL 原子 upsert、活动封禁查询与 bucket 删除。
- `backend/app/auth/service.py` - 双 bucket HMAC、注入时钟、稳定封禁异常和事务协议。
- `backend/app/auth/api.py` - 注入请求来源并映射稳定 429 `RATE_LIMITED` envelope。
- `backend/migrations/versions/0002_login_attempts.py` - 0001 后继登录限流 schema 与可逆 downgrade。
- `backend/tests/auth/test_login_rate_limit_service.py` - HMAC 隐私、阈值、retry 和成功复位单元合约。
- `backend/tests/integration/test_auth_database_protocols.py` - 真实 PG 迁移、约束、savepoint 与并发证据。
- auth、migration versions、auth tests、integration tests README - 同步职责、允许依赖和文件索引。

## Decisions Made

- 不按数据库 user_id 限流，因为这会让未知邮箱和已知邮箱走不同持久化路径；规范化提交邮箱直接进入 secret-scoped HMAC principal bucket。
- principal 和 source 必须同时受控：只按邮箱容易被分布式撞库绕过，只按来源会让攻击者轮换来源绕过。两者使用域分离的 `v1` 输入并共享阈值策略。
- Repository 返回最大活动 `blocked_until`；Service 统一计算向上取整的 `retry_after`，HTTP 层不参与策略或数据库访问。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical security boundary] 补充 API 来源注入和 429 翻译**
- **Found during:** Task 1 GREEN
- **Issue:** 计划 action 要求 source bucket 与稳定 429，但 `files` 清单遗漏 `api.py`，只改 Service 无法获得请求来源或完成 HTTP 合约。
- **Fix:** API 从 request client 提取来源、传给 Service，并把统一限流异常翻译为无敏感信息的 `RATE_LIMITED`。
- **Files modified:** `backend/app/auth/api.py`, `backend/tests/auth/test_login_me_api.py`
- **Verification:** HTTP 合约 15 passed；完整回归 64 passed。
- **Committed in:** `06ed5d9`

**2. [Rule 1 - Regression] 更新 0001 migration 测试的 head 预期**
- **Found during:** Task 2
- **Issue:** 原测试把 `head` 固定断言为 0001；新增合法后继 revision 后必然产生假失败。
- **Fix:** 保留空库重建语义，改为验证 head=0002 且包含 `login_attempts`，独立新测试再显式验证 0001→0002→0001。
- **Files modified:** `backend/tests/integration/test_auth_migration.py`, `backend/tests/integration/README.md`
- **Verification:** 全部 integration 5 passed。
- **Committed in:** `40da8fa`

---

**Total deviations:** 2 auto-fixed (1 Rule 1, 1 Rule 2)。
**Impact on plan:** 两项均是完成稳定 HTTP 安全边界和避免 migration 回归假失败所必需，没有扩展产品范围。

## Issues Encountered

- 沙箱默认禁止连接 Docker socket 和本机 55432；使用限定授权重跑相同命令后通过，未更改测试或回退到 SQLite。
- migration 测试最初把 Alembic 自身的 `alembic_version` 表误判为空库业务表，并在断言失败后未恢复 head；修正为空库只允许该版本表，并用 `finally` 无条件恢复 head，避免污染后续测试。

## Authentication Gates

None.

## Known Stubs

None. `blocked_until=None` 是未封禁 bucket 的真实状态，测试 fake 的空列表仅用于记录可观察调用，不流向运行时 UI 或业务结果。

## User Setup Required

None - 复用固定版本、回环绑定的 `postgres-test` 容器，不需要外部账号或新增密钥。

## Verification Evidence

- Task 1 RED：`test_login_rate_limit_service.py` collection 因 `LoginRateLimited` 不存在按预期失败。
- Task 1 GREEN：Service 限流与既有登录测试 `10 passed`；非 PG HTTP 合约 `15 passed, 1 deselected`；compileall 通过。
- Task 2 目标测试：真实 PostgreSQL `3 passed`，覆盖 migration 往返、约束/savepoint 和并发协议。
- 全部 integration：真实 PostgreSQL `5 passed`。
- 完整 backend pytest（真实 PostgreSQL + Mailpit）：`64 passed in 4.69s`，无 skip。

## Next Phase Readiness

- 01-09 登录 UI 可直接消费稳定 `429 RATE_LIMITED` 与安全 `retry_after`。
- 后续 refresh/password-reset 可以复用 Repository 事务边界，但不得复用 login bucket 保存 raw principal/source。
- 部署为多 worker 时不需要进程内共享缓存；PostgreSQL 是唯一权威限流状态。
- 无阻塞项。

## Self-Check: PASSED

- migration、Service 限流单测和真实 PostgreSQL 协议测试文件均存在。
- `303daca`、`06ed5d9`、`40da8fa` 均可从 Git 历史解析。
- 计划级 compileall、目标 PG 测试、全部 integration 和完整 backend 回归均通过；未发现阻塞目标的 stub 或计划外威胁面。

---
*Phase: 01-engineering-auth-foundation*
*Completed: 2026-08-27*
