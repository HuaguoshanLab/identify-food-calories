---
phase: 01-engineering-auth-foundation
plan: 04
subsystem: registration-auth
tags: [fastapi, argon2id, hmac, smtp, mailpit, postgresql]

requires:
  - phase: 01-engineering-auth-foundation/01-03
    provides: 用户与验证码 ORM、Repository port、partial-current 约束和隔离 PostgreSQL fixture
provides:
  - 注册、pending context、验证码验证与重发的 FastAPI 闭环
  - 6 位 ASCII 验证码的摘要存储、10 分钟/5 次/60 秒/替换/单次消费策略
  - 可替换 MailProvider 与本地 Mailpit SMTP adapter
  - 非枚举 202、HttpOnly context cookie 和稳定安全错误 envelope
affects: [01-05, 01-06, 01-08, 01-10, auth, frontend-registration, password-reset]

tech-stack:
  added: [pwdlib 0.3.1 with Argon2]
  patterns: [API-Service-Repository separation, provider injection, scoped HMAC digests, deterministic fake providers]

key-files:
  created: [backend/app/notifications/ports.py, backend/app/notifications/smtp.py, backend/app/auth/security.py, backend/app/auth/service.py, backend/app/auth/api.py, backend/tests/auth/test_registration_verification.py]
  modified: [backend/app/main.py, backend/app/auth/schemas.py, backend/app/auth/ports.py, backend/app/auth/repository.py, backend/pyproject.toml]

key-decisions:
  - "验证码使用 CSPRNG 生成 6 位 ASCII 数字，按高熵 context 作用域做 HMAC；数据库不保存明文验证码或 context。"
  - "context 由服务端密钥和 challenge UUID 可重建，再以摘要落库；冷却期重复注册可复用有效 context，避免枚举侧信道且不绕过冷却。"
  - "邮箱验证只激活账号并要求重新登录，不在验证端点自动创建 session 或签发 token。"

patterns-established:
  - "Provider port：Service 依赖 MailProvider Protocol，本地/生产 SMTP 只是可替换 adapter。"
  - "稳定 HTTP 翻译：API 只管理 Cookie/CORS/status/envelope，验证码策略只存在于 Service。"

requirements-completed: [AUTH-01, AUTH-02, AUTH-06, ARC-02, ARC-03, ARC-07]

duration: 15 min
completed: 2026-08-27
---

# Phase 1 Plan 4: 注册邮箱验证闭环 Summary

**Argon2id 未激活账号注册、摘要化邮箱验证码协议与 Mailpit SMTP 投递组成可追问、不可枚举、单次激活的后端闭环。**

## Performance

- **Duration:** 15 min
- **Started:** 2026-08-27T06:45:22Z
- **Completed:** 2026-08-27T07:00:12Z
- **Tasks:** 2
- **Files modified:** 17

## Accomplishments

- 注册固定 `role=user`，用 Argon2id 保存密码摘要，创建未激活用户；验证码为 CSPRNG 生成的 6 位 ASCII 数字，数据库只保存 context/code HMAC。
- Service 权威执行 10 分钟到期、最多 5 次、60 秒重发冷却、新码替换旧码和成功后单次消费；重复注册不会绕过冷却或产生枚举侧信道。
- 提供 register/context/verify/resend 四个 FastAPI 路由，context 只进入同源 HttpOnly Cookie，响应只含掩码邮箱、时间和稳定状态/error code。
- `MailProvider` 隔离应用层与 SMTP；真实 PostgreSQL + Mailpit 集成测试证明邮件收到验证码、产品 API 不暴露验证码且验证后账号才激活。

## Task Commits

1. **Task 1 RED: 固化注册验证码应用协议** - `3b0b460` (test)
2. **Task 1 GREEN: 实现 MailProvider、Argon2id 与验证码 Service** - `289a103` (feat)
3. **Task 2 RED: 固化注册 API 与 Mailpit 闭环合约** - `6e47d74` (test)
4. **Task 2 GREEN: 暴露安全 HTTP API 并接通 Mailpit** - `68699e5` (feat)

## Files Created/Modified

- `backend/app/notifications/ports.py` / `smtp.py` - 可替换邮件 port 与 SMTP/Mailpit adapter。
- `backend/app/auth/security.py` - Argon2id、验证码 CSPRNG、可重建 opaque context 与作用域 HMAC 原语。
- `backend/app/auth/service.py` - 注册、context、过期、次数、冷却、替换和单次消费协议。
- `backend/app/auth/api.py` / `main.py` - 四个注册路由、HttpOnly Cookie、CORS 与稳定安全 envelope。
- `backend/app/auth/ports.py` / `repository.py` - 当前 user/purpose challenge 的锁定查询能力。
- `backend/app/auth/schemas.py` - 12–128 字符密码、6 位 ASCII code、公开 dispatch/context/success 合约。
- `backend/tests/auth/test_registration_verification.py` - fake Service、HTTP/OpenAPI、真实 PostgreSQL 与 Mailpit 证据。
- app、auth、notifications、tests/auth README - 职责、允许依赖和文件索引。

## Decisions Made

- context 原文不落库，但不能使用一次性随机值后丢失，否则冷却期重复注册会收到无法查询的 context 并泄露账号状态。改为 `HMAC(secret, challenge_id)` 生成 opaque context，再保存其 HMAC 摘要；只有持有服务端密钥才能重建。
- 错误次数在每次错误验证后立即提交，确保请求失败不会回滚安全计数；成功时消费 challenge、激活用户并在同一事务提交。
- 邮件发送成功后才提交用户/challenge；provider 失败执行 rollback。Phase 1 不引入 outbox 或异步基础设施。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical dependency] 补充并锁定 Argon2id 实现**
- **Found during:** Task 1 GREEN
- **Issue:** 计划要求 Argon2id，但 `pyproject.toml` 和虚拟环境没有密码哈希实现，无法安全保存注册密码。
- **Fix:** 按 Phase 1 已验证研究与官方文档加入 `pwdlib[argon2]==0.3.1`，使用 `PasswordHash.recommended()`。
- **Files modified:** `backend/pyproject.toml`, `backend/app/auth/security.py`
- **Verification:** 生成摘要以 `$argon2id$` 开头；完整测试套件通过。
- **Committed in:** `289a103`

**2. [Rule 1 - Information disclosure] 修复冷却期重复注册 context 枚举侧信道**
- **Found during:** Task 2 GREEN
- **Issue:** 若冷却期重复注册返回一个没有服务端摘要的新 context，后续 `/context` 会对已有账号返回 409、对新账号返回 200，形成账号枚举差异。
- **Fix:** 从服务端密钥与 challenge UUID 重建不可猜测 context，数据库仍只保存摘要；重复请求复用当前有效 context 且不再次发信。
- **Files modified:** `backend/app/auth/security.py`, `backend/app/auth/service.py`, `backend/tests/auth/test_registration_verification.py`
- **Verification:** 新增测试证明响应形状一致、context 有效、challenge/mail 数量不变；注册文件 15 passed。
- **Committed in:** `68699e5`

---

**Total deviations:** 2 auto-fixed (1 Rule 1, 1 Rule 2)。
**Impact on plan:** 两项均为密码安全与非枚举正确性所必需，没有扩张产品范围或改变既定架构。

## Issues Encountered

- 当前 GSD 安装使用旧版 `gsd-tools.cjs`，不支持新版 `query` 子命令；状态初始化与后续追踪使用其等价旧命令/受控文档更新。
- 沙箱默认禁止访问本机 Docker 端口和 Git index；使用限定授权执行同一测试和提交命令，没有绕过测试或 hook。

## Authentication Gates

None.

## Known Stubs

None. `email_verified_at=None`、`consumed_at=None`、`invalidated_at=None` 和未激活状态均是验证码真实生命周期，不是占位实现。

## User Setup Required

None - 复用 01-01 固定的 PostgreSQL test 与 Mailpit 容器，不需要外部账号或密钥。

## Verification Evidence

- Task 1 RED：缺少 `app.auth.security`，pytest collection 按预期失败。
- Task 1 GREEN：注册协议与 unit tests → `26 passed`。
- Task 2 RED：缺少 `app.auth.api`，pytest collection 按预期失败。
- 注册 Service/API/PostgreSQL/Mailpit 文件 → `15 passed`。
- `.venv/bin/python -m compileall -q app migrations tests` → 通过。
- 完整 backend pytest（真实 PostgreSQL + Mailpit）→ `35 passed in 2.19s`。
- OpenAPI 包含四个注册路由且不含 `password_hash`、`code_digest`、`context_digest` 或 refresh token。

## Next Phase Readiness

- 01-05 可复用 Argon2id 原语、稳定 error envelope 和 Service 事务装配实现登录、access/refresh 与 session family。
- 密码重置计划可复用同一 challenge policy 和 MailProvider，但必须使用独立 `purpose=password_reset` Service 协议。
- 无阻塞项。

## Self-Check: PASSED

- 17 个新增/修改文件均存在；新增 `notifications/`、`tests/auth/` 目录均有 README，父索引已同步。
- `3b0b460`、`289a103`、`6e47d74`、`68699e5` 均可从 Git 历史解析。
- 两个 RED gate 均真实失败，两个 GREEN gate 与完整 PostgreSQL/Mailpit 验收全部通过。

---
*Phase: 01-engineering-auth-foundation*
*Completed: 2026-08-27*
