---
phase: 01-engineering-auth-foundation
plan: 05
subsystem: authentication-api
tags: [fastapi, pyjwt, argon2id, bearer, postgresql]

requires:
  - phase: 01-engineering-auth-foundation/01-04
    provides: 已验证 active 用户、Argon2id 密码摘要、稳定错误 envelope 与 Repository 事务边界
provides:
  - 仅允许已验证 active 用户登录的统一非枚举认证协议
  - 15 分钟最小 access JWT 与 30 天 opaque refresh token 摘要存储
  - 每次按 Bearer sub 重读 PostgreSQL 的数据库权威 `/api/v1/users/me`
affects: [01-06, 01-10, 01-11, 01-12, login-ui, refresh-rotation, rbac]

tech-stack:
  added: [PyJWT 2.13.0]
  patterns: [dummy Argon2 verification, fixed-algorithm JWT validation, DB-authoritative identity]

key-files:
  created: [backend/tests/auth/test_login_me_service.py, backend/tests/auth/test_login_me_api.py]
  modified: [backend/app/auth/security.py, backend/app/auth/service.py, backend/app/auth/api.py, backend/app/auth/schemas.py, backend/app/main.py, backend/pyproject.toml]

key-decisions:
  - "access token 固定 HS256、typ=JWT、issuer=food-agent-api、audience=food-agent-h5，并要求且校验 sub/role/iat/exp/jti/iss/aud。"
  - "JWT role 只用于令牌结构校验；/users/me 的 email、active 和最终 role 每次按 sub 从 PostgreSQL 重读。"
  - "refresh token 使用 256-bit opaque CSPRNG 原文交给 HttpOnly Cookie，数据库只保存 secret-scoped HMAC 摘要。"

patterns-established:
  - "统一登录失败：未知邮箱、错误密码、未验证和 inactive 均执行一次 Argon2 verify 并返回同一错误。"
  - "Bearer 边界：API 只提取 Header 和翻译 401，Service 调用安全原语后通过 Repository 获取权威用户。"

requirements-completed: [AUTH-01, AUTH-02, AUTH-03, ARC-02, ARC-03, ARC-07]

duration: 13 min
completed: 2026-08-27
---

# Phase 1 Plan 5: 登录与数据库权威身份 Summary

**Argon2id 非枚举登录、严格最小 JWT、opaque refresh Cookie 与 PostgreSQL 权威 `/users/me` 组成可撤销会话的安全入口。**

## Performance

- **Duration:** 13 min
- **Started:** 2026-08-27T07:10:53Z
- **Completed:** 2026-08-27T07:24:16Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- 未知邮箱使用 dummy Argon2 摘要，已知账号使用真实摘要；错误密码、未验证和 inactive 均不创建 session/refresh row，也不暴露账号状态。
- access JWT 仅含 `sub/role/iat/exp/jti/iss/aud`，固定 HS256 与 `typ=JWT`；Bearer 验证覆盖签名、算法、类型、issuer、audience、时间、UUID `sub/jti` 和角色类型。
- 登录 JSON 只返回短期 access token；256-bit opaque refresh token 只进入 `HttpOnly; SameSite=lax; Path=/api/v1/auth` Cookie，生产配置追加 `Secure`，数据库仅保存 HMAC 摘要。
- `/api/v1/users/me` 在每次请求验签后按 `sub` 查询 Repository，数据库中的 email、active 和 role 才是最终身份；缺失或停用用户稳定返回 401。

## Task Commits

1. **Task 1 RED: 固化登录与当前身份 Service 合约** - `4115df4` (test)
2. **Task 1 GREEN: 实现已验证账号登录与数据库权威身份 Service** - `4c13653` (feat)
3. **Task 2 RED: 固化 login 与 users/me HTTP 合约** - `fc07270` (test)
4. **Task 2 GREEN: 暴露 Cookie login 与 Bearer users/me** - `95a37e2` (feat)

## Files Created/Modified

- `backend/app/auth/security.py` - dummy Argon2 verify、最小 JWT 签发/严格验证、refresh CSPRNG 与 HMAC 摘要。
- `backend/app/auth/service.py` - 登录 session/refresh 事务，以及按 JWT sub 重读权威用户。
- `backend/app/auth/api.py` - `/auth/login`、独立 `/users/me` router、Cookie 和稳定 401 翻译。
- `backend/app/auth/schemas.py` - 登录请求、access 响应与独立当前用户公开 Schema。
- `backend/app/main.py` - 装配 authentication 与 users routers。
- `backend/pyproject.toml` - 精确锁定 PyJWT 2.13.0。
- `backend/tests/auth/test_login_me_service.py` - fake repository Service 协议和最小 token 证据。
- `backend/tests/auth/test_login_me_api.py` - HTTP/OpenAPI、严格 Bearer 和真实 PostgreSQL 权威身份证据。
- auth 与 tests/auth README - 同步职责、允许依赖和文件索引。

## Decisions Made

- 不把 email 放入 JWT，也不信任 JWT role 作为最终授权事实。`role` claim 仍保留用于最小 access 上下文，但 `/users/me` 和后续 RBAC 必须重读数据库。
- PyJWT decode 使用编译时固定的 `[HS256]` allow-list、严格单值 audience 与 required claims；为确定性测试注入时钟后，`iat/exp` 由安全边界显式比较，避免测试依赖墙钟。
- login 创建新 session family 和首枚 refresh row 后统一 commit；提交失败 rollback，不允许返回没有持久化撤销依据的 token。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical dependency] 补充并锁定窄 JWT 实现**
- **Found during:** Task 1 GREEN
- **Issue:** 计划要求签发和严格验证 access JWT，但现有运行依赖没有 JWT 实现。
- **Fix:** 使用 Phase 1 研究已标记 VERIFIED 的 PyJWT，并按官方 2.13.0 文档固定 algorithms、required claims、issuer、audience 与 strict audience 校验。
- **Files modified:** `backend/pyproject.toml`, `backend/app/auth/security.py`
- **Verification:** access claims/签名/算法/typ/iss/aud/iat/exp/sub/jti 测试与完整回归通过。
- **Committed in:** `4c13653`

---

**Total deviations:** 1 auto-fixed (1 Rule 2)。
**Impact on plan:** 该依赖是计划安全边界不可缺少的实现，不改变架构或产品范围。

## Issues Encountered

- 沙箱内首次访问本机 PostgreSQL 被系统拒绝；使用限定授权重跑相同测试命令后通过，没有修改测试或改用 SQLite。

## Authentication Gates

None.

## Known Stubs

None. session/refresh 的 `revoked_at=None`、`consumed_at=None` 和 `replaced_by_id=None` 是新会话的真实初始状态，后续 01-10 负责轮换与撤销，不是 UI 或业务占位。

## User Setup Required

None - 复用 01-01 的隔离 PostgreSQL test 容器，不需要外部账号或新增密钥。

## Verification Evidence

- Task 1 RED：pytest collection 因 `AuthenticationService` 合约不存在而按预期失败。
- Task 1 Service：`7 passed`，覆盖 dummy verify、verified/active gate、最小 JWT、opaque refresh 和 DB 状态重读。
- Task 2 RED：pytest collection 因 login/refresh Cookie API 合约不存在而按预期失败。
- Task 2 API + 真实 PostgreSQL：`15 passed`，覆盖 Cookie、稳定 401、签名/算法/type/issuer/audience/time/sub、missing/inactive、DB role 与 OpenAPI。
- 完整 backend pytest（真实 PostgreSQL + Mailpit）：`57 passed in 3.05s`，无 skip。
- `.venv/bin/python -m compileall -q app migrations tests`：通过。

## Next Phase Readiness

- 01-06 可直接消费稳定的 login/access/me 合约完成前端公开页与认证入口。
- 01-10 可复用 session family、opaque refresh HMAC 和 scoped Cookie 实现原子轮换、重放撤销与 logout。
- 01-12 RBAC 必须沿用本计划的数据库权威 role 模式，不能只信任 JWT claim。
- 无阻塞项。

## Self-Check: PASSED

- 两个新增测试文件和全部关键修改文件均存在，auth/tests/auth README 索引已同步。
- `4115df4`、`4c13653`、`fc07270`、`95a37e2` 均可从 Git 历史解析，RED → GREEN 顺序完整。
- 计划级 Service/API 验证与完整 PostgreSQL/Mailpit 回归全部通过；未发现阻塞目标的 stub 或计划外威胁面。

---
*Phase: 01-engineering-auth-foundation*
*Completed: 2026-08-27*
