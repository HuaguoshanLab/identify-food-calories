---
phase: 01-engineering-auth-foundation
plan: 13
subsystem: account-recovery
tags: [fastapi, postgresql, smtp, mailpit, password-reset, security]
requires:
  - phase: 01-engineering-auth-foundation/01-04
    provides: 验证码挑战、邮件 Provider 和注册 HttpOnly context 基础设施
  - phase: 01-engineering-auth-foundation/01-10
    provides: refresh family 撤销与 Cookie/CSRF 安全边界
provides:
  - 密码恢复的验证码、HttpOnly context、稳定 API 错误与 Mailpit 闭环
  - PostgreSQL 行锁单次消费，以及密码更新和所有会话 family 撤销的原子事务
affects: [frontend-password-recovery, auth-session-security, phase-01-completion]
tech-stack:
  added: []
  patterns:
    - AccountRecoveryRepository 和 SessionFamilyRevoker port 保持 accounts 不依赖 auth repository
    - recovery context 只存于 HttpOnly cookie；未知账号使用服务端签名 decoy context
key-files:
  created:
    - backend/app/accounts/api.py
    - backend/app/accounts/service.py
    - backend/app/accounts/repository.py
    - backend/tests/accounts/test_account_recovery.py
  modified:
    - backend/app/main.py
    - backend/app/accounts/schemas.py
    - backend/app/README.md
key-decisions:
  - "密码重置在同一 SQLAlchemy Session 内更新密码、消费 challenge 并撤销用户全部 session family。"
  - "恢复入口和 context 使用固定外部 envelope；未知账号只获得服务端可验证的 HttpOnly decoy context。"
patterns-established:
  - "恢复用例通过独立 application port 调用会话撤销，而不是导入 auth repository。"
  - "涉及 Cookie 的恢复写操作执行精确 Origin/Referer 校验，保持既有 CORS/CSRF 规则。"
requirements-completed: [AUTH-06, ARC-02, ARC-03, ARC-04, ARC-07]
duration: 9min
completed: 2026-08-27
---

# Phase 01 Plan 13: 密码恢复与原子会话撤销 Summary

**通过共享验证码与 MailProvider 实现的密码恢复闭环：密码更新、challenge 消费和全部旧会话撤销在 PostgreSQL 中原子完成。**

## Performance

- **Duration:** 9 min
- **Started:** 2026-08-27T10:18:42Z
- **Completed:** 2026-08-27T10:27:34Z
- **Tasks:** 2/2
- **Files modified:** 14

## Accomplishments

- 新增 `accounts` 分层模块，复用 6 位 digest-only 验证码、10 分钟有效期、5 次尝试、60 秒冷却和 MailProvider。
- 新增 forgot/context/verify/resend/reset API；pending context 仅存在服务端可验证的 HttpOnly Strict cookie，API 与日志均不回显验证码。
- 真实 PostgreSQL 测试证明两个独立连接竞争 reset 时只有一个成功，且注入 family revoke 失败会回滚密码、challenge 和会话撤销；Mailpit 证明 SMTP 投递。

## Task Commits

1. **Task 1: 实现密码恢复 Service 与端口** - `16007a6`（RED tests），`281dd9e`（feature）
2. **Task 2: 暴露恢复 API 并验证真实 PG 竞争** - `1158ccb`（RED tests），`f6e2605`（feature），`718067b`（security fix）

## Files Created/Modified

- `backend/app/accounts/ports.py` - 恢复持久化与全部会话 family 撤销 Port。
- `backend/app/accounts/repository.py` - 同一请求 Session 内的 challenge 行锁和 session/refresh revoke adapter。
- `backend/app/accounts/service.py` - 验证码、密码更新和原子事务边界。
- `backend/app/accounts/api.py` - 恢复 HTTP 路由、错误映射、CSRF 与 HttpOnly cookie。
- `backend/tests/accounts/test_account_recovery.py` - fake、HTTP、Mailpit、真实 PostgreSQL 并发与 rollback 证据。

## Decisions Made

- reset 继续携带验证码；`/verify` 只做预检而不消费，实际消费与密码更新绑定为一次事务，避免引入未迁移的“已验证”临时状态。
- 所有 session 与 refresh token family 都在密码重置成功时撤销，旧浏览器的 refresh token 不能继续换取 access token。
- 未知账号使用有有效期的服务端 HMAC-signed decoy context，context、错误码和 cookie 生命周期不再形成二次账号枚举通道。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical security] 消除 recovery context 二次枚举通道**
- **Found during:** Task 2 安全复核
- **Issue:** 仅统一 `/forgot` 的 202 响应仍可能让攻击者以各自 cookie 调用 `/context`，通过真实 challenge 与未知账号的差异进行枚举。
- **Fix:** context 改为固定 pending envelope；未知账号发放服务端 HMAC 签名且限时的 decoy context，verify/reset 对其统一映射为无效验证码。
- **Files modified:** `backend/app/accounts/schemas.py`, `backend/app/accounts/service.py`, `backend/tests/accounts/test_account_recovery.py`
- **Verification:** 恢复模块 12 passed；完整后端 93 passed。
- **Committed in:** `718067b`

---

**Total deviations:** 1 auto-fixed (1 Rule 2 security)。
**Impact on plan:** 该修复是 T-13-01 非枚举承诺的必要条件，未增加产品范围。

## Issues Encountered

- 默认沙箱禁止 Docker socket 与回环 PostgreSQL；启动容器和测试均在受限授权后完成，未改用 SQLite 或 fake 替代真实并发证据。

## Authentication Gates

None.

## Known Stubs

None. 测试内的 `$argon2id$placeholder` 仅是 fake repository 的初始测试数据，既不流向 UI，也不进入生产持久化。

## Threat Flags

None. 新增恢复 API、邮件 adapter 调用和会话撤销均由计划 T-13-01、T-13-02、T-13-SC 覆盖并实施对应缓解。

## Verification Evidence

- Task 1 RED：`app.accounts.service` 不存在时测试 collection 失败；GREEN 后 fake Service 6 passed。
- Task 2 RED：`app.accounts.api` 不存在时测试 collection 失败；GREEN 后 API 与 fake Service 8 passed。
- `docker compose up -d --wait postgres-test mailpit` 后，恢复模块 12 passed，包含 SMTP/Mailpit、两个真实 PostgreSQL 连接的竞争消费、以及注入失败 rollback。
- 最终完整 backend 回归：`93 passed in 5.36s`，仅保留 Starlette TestClient 的第三方弃用警告；`compileall app` 通过。

## Next Phase Readiness

- 后端密码恢复 API 已可供前端安全接入；前端不得把 context、验证码或任何 reset token 写入 URL 或浏览器存储。
- 无阻塞项。

## Self-Check: PASSED

- `backend/app/accounts/api.py`、`backend/app/accounts/service.py`、`backend/app/accounts/repository.py` 和恢复测试文件均存在。
- `16007a6`、`281dd9e`、`1158ccb`、`f6e2605`、`718067b` 均可在 Git 历史解析。
- 计划要求的恢复 Service/API/真实 PostgreSQL/Mailpit 验证和完整后端回归均通过。

---
*Phase: 01-engineering-auth-foundation*
*Completed: 2026-08-27*
