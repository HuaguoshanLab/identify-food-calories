---
phase: 01-engineering-auth-foundation
plan: 10
subsystem: authentication-session-security
tags: [fastapi, postgresql, sqlalchemy, refresh-token, csrf, concurrency]

requires:
  - phase: 01-engineering-auth-foundation/01-06
    provides: PostgreSQL auth repository transaction boundary and opaque refresh-token schema
provides:
  - Opaque refresh rotation with one-time consumption and successor linking
  - Atomic replay detection that revokes the complete session family
  - CSRF-protected logout and user-scoped session management APIs
  - Real PostgreSQL concurrency and rollback evidence
affects: [frontend-auth, deployment, security-audit, admin-rbac]

tech-stack:
  added: []
  patterns: [refresh digest-only persistence, token row lock, session-bound JWT JTI, exact-origin cookie mutation]

key-files:
  created: [backend/tests/auth/test_refresh_service.py, backend/tests/auth/test_refresh_api.py, backend/tests/integration/test_refresh_concurrency.py]
  modified: [backend/app/auth/api.py, backend/app/auth/service.py, backend/app/auth/repository.py, backend/app/auth/security.py, backend/app/auth/ports.py, backend/app/auth/schemas.py]

key-decisions:
  - "refresh 原文仅存在于 HttpOnly Cookie 和单次 Service 返回值；数据库只保存 secret-scoped HMAC digest。"
  - "refresh 行先用 SELECT FOR UPDATE 串行化；已消费 token 的再次提交在同一事务撤销整个 session family。"
  - "access JWT 的既有 jti 绑定 auth session id，使 logout/session API 无需暴露或读取 refresh 原文。"
  - "当前 session 不允许通过 DELETE 撤销，必须走 logout；所有会话查询和撤销都带 user_id 边界。"

patterns-established:
  - "Cookie 变更端点要求精确 Origin，或将 Referer 解析为精确配置 origin；缺失/伪造来源一律拒绝。"
  - "并发安全主张必须由独立 PostgreSQL Session 与同步 barrier 验证，禁止 SQLite、in-memory fake 和 sleep。"

requirements-completed: [AUTH-01, AUTH-03, AUTH-04, ARC-02, ARC-04, ARC-07]

duration: 13min
completed: 2026-08-27
---

# Phase 1 Plan 10: Refresh 轮换、重放检测与会话协议 Summary

**基于 HMAC digest、PostgreSQL 行锁和全 family revoke 的 refresh 轮换协议，配套 CSRF 保护的退出/会话管理 API 与真实并发证据。**

## Performance

- **Duration:** 13 min
- **Started:** 2026-08-27T09:26:45Z
- **Completed:** 2026-08-27T09:39:32Z
- **Tasks:** 2
- **Files modified:** 13

## Accomplishments

- refresh 原文从不落库、记录日志或生成 OpenAPI；每次 refresh 消费旧 digest、创建一个 successor，并在同一事务记录替代关系。
- 同一旧 token 的第二次提交必定触发 replay 路径，原子撤销该 session 的所有 refresh token 与 session 本身；撤销后不再接受 token。
- 提供 refresh、logout、GET sessions、DELETE own session；JWT JTI 绑定 session，列表/撤销以 user_id 约束，当前 session 必须 logout。
- Cookie 变更严格校验 Origin 或 Referer 的精确 CORS origin；真实 PostgreSQL 的独立连接竞争只产生一个轮换赢家，并证明事务失败会完整 rollback。

## Task Commits

1. **Task 1 RED: 定义 refresh/session 协议测试** - `f5e453a` (test)
2. **Task 1 GREEN: 实现 refresh rotation 与会话管理** - `6fb931c` (feat)
3. **Task 2: 真实 PostgreSQL refresh 并发证据** - `dd7a465` (test)
4. **Security fix: 强制精确 CSRF origin** - `7b4b906` (fix)

## Files Created/Modified

- `backend/app/auth/api.py` - refresh/logout/session endpoints、HttpOnly Cookie 生命周期、精确 Origin/Referer CSRF 验证和稳定错误。
- `backend/app/auth/service.py` - 单次 refresh consume/successor、replay family revoke、session-bound bearer 和 user-scoped 会话规则。
- `backend/app/auth/repository.py` - refresh/session `SELECT FOR UPDATE` 与 family/user scoped 更新。
- `backend/app/auth/security.py` - session id 绑定到已验证 access JWT JTI，不增加公开 refresh 合约。
- `backend/app/auth/ports.py`、`schemas.py` - 持久化能力边界与会话公开响应的 `is_current` 字段。
- `backend/tests/auth/test_refresh_service.py`、`test_refresh_api.py` - Service/HTTP 的 rotation、replay、Cookie、OpenAPI、ownership 和 CSRF 合约。
- `backend/tests/integration/test_refresh_concurrency.py` - 独立 PostgreSQL 连接的竞争和失败 rollback 证据。
- auth 与 integration README - 同步职责、允许依赖和文件索引。

## Decisions Made

- refresh family 等同于一个 `AuthSession`；replay revoke 同时标记 session 和该 session 全部 refresh rows，避免只撤销旧 token 留下 successor 可用。
- 保留 access JWT claim 集合不扩展，通过现有 `jti` 写入 session id，避免协议漂移并为 session management 提供受签名身份。
- 当前 session 的 DELETE 返回 `CURRENT_SESSION_REQUIRES_LOGOUT`，避免客户端删掉当前会话后仍持有一个短期 access token 的模糊状态。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Framework contract] 修复 FastAPI 204 response model 冲突**
- **Found during:** Task 1 GREEN
- **Issue:** `Response | JSONResponse` 的路由注解与 204 声明冲突，FastAPI 在导入时拒绝启动应用。
- **Fix:** logout 与 DELETE session 明确 `response_model=None`，保留统一错误 JSON 与成功 204 空响应。
- **Files modified:** `backend/app/auth/api.py`
- **Verification:** refresh/session API 契约 11 passed；完整后端回归 77 passed。
- **Committed in:** `6fb931c`

**2. [Rule 2 - Missing critical CSRF boundary] 拒绝缺失或前缀伪造的来源**
- **Found during:** Task 2 后安全复核
- **Issue:** 初版会接受没有 Origin/Referer 的 Cookie mutation；Referer 不应靠字符串前缀判断。
- **Fix:** 缺失来源返回 `CSRF_ORIGIN_INVALID`，Referer 经 URL 解析后必须等于配置 CORS origin。
- **Files modified:** `backend/app/auth/api.py`, `backend/tests/auth/test_refresh_api.py`
- **Verification:** exact Origin、合法 Referer、缺失来源、前缀攻击均有 HTTP 合约；完整回归 77 passed。
- **Committed in:** `7b4b906`

---

**Total deviations:** 2 auto-fixed (1 Rule 1, 1 Rule 2)。
**Impact on plan:** 均是框架可运行性和 Cookie 防 CSRF 的必要修复，没有扩展产品范围。

## Issues Encountered

- 默认 Python 3.11 没有 pytest；使用项目已提交约定的 `backend/.venv/bin/python` 运行测试，未安装或替换依赖。
- 沙箱默认禁止 Docker socket 与回环 PostgreSQL；使用受限授权重跑相同命令后完成真实 PG 验证，未改用 SQLite 或测试替身。

## Authentication Gates

None.

## Known Stubs

None. 所有 `None` 值均是 ORM 的实际未消费/未撤销状态，未作为 UI placeholder 或业务假值使用。

## Threat Flags

None. 新增认证路由、Cookie mutation 与 refresh 数据库流程均已由计划 T-10-01 至 T-10-SC 覆盖并实施对应缓解。

## Verification Evidence

- Task 1 RED：新增测试因 `CurrentSessionCannotBeRevoked` 不存在按预期 collection 失败；随后 GREEN 通过 11 项 Service/API 合约和 `compileall`。
- Task 2：`docker compose up -d --wait postgres-test` 后，真实 `postgresql+psycopg` `test_refresh_concurrency.py` 为 `2 passed`，无 SQLite、in-memory fake 或 sleep。
- 完整 backend 回归：`77 passed in 5.91s`，无 skip；仅有 TestClient per-request Cookie 的第三方弃用警告。

## Next Phase Readiness

- 前端可安全调用 refresh/logout/session API；refresh cookie 未出现在 OpenAPI，access token 继续仅经 JSON 返回。
- 部署与安全审计应保留 `Cookie Secure` production 强制设置及精确 CORS origin 配置。
- 无阻塞项。

## Self-Check: PASSED

- 三份新增 refresh 测试文件和全部关键实现文件均存在。
- `f5e453a`、`6fb931c`、`dd7a465`、`7b4b906` 均在 Git 历史中可解析。
- 目标 Service/API、真实 PostgreSQL 并发/rollback 与完整 backend 回归均通过；没有阻塞目标的 stub 或未登记 threat surface。

---
*Phase: 01-engineering-auth-foundation*
*Completed: 2026-08-27*
