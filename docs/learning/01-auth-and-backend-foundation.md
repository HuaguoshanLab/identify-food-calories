# Phase 1：认证与后端基础教学指南

这份文档给熟悉 React、但刚接触 FastAPI、SQLAlchemy 和 PostgreSQL 的开发者使用。目标不是背 API，而是能从一个按钮一路追到数据库，并知道每个安全边界为什么存在。

## 一次注册到登录的真实链路

```text
RegisterPage (React Hook Form + Zod)
  -> frontend/src/auth/api.ts: registerAccount()
  -> POST /api/v1/auth/register
  -> app.auth.api:get_registration_service()
  -> RegistrationService.register() [一个事务]
  -> SqlAlchemyAuthRepository + PostgreSQL
  -> SMTP provider -> Mailpit（仅本地测试）
  -> 浏览器持有 HttpOnly registration_context cookie
```

1. 用户在 [`frontend/src/auth/RegisterPage.tsx`](../../frontend/src/auth/RegisterPage.tsx) 提交邮箱和密码。前端校验的目的只是尽早反馈，服务端的 [`backend/app/auth/schemas.py`](../../backend/app/auth/schemas.py) 才是输入真相。
2. [`frontend/src/auth/api.ts`](../../frontend/src/auth/api.ts) 用 `credentials: 'include'` 请求 `/auth/register`。浏览器会接收 HttpOnly 的注册上下文 Cookie，React 代码读不到它，避免把一次性上下文暴露给脚本。
3. [`backend/app/auth/api.py`](../../backend/app/auth/api.py) 只做 HTTP 翻译：取 schema、组装依赖、映射稳定错误码。它不能自己写 ORM 查询，否则 API → Service → Repository 的边界会立即烂掉。
4. `RegistrationService` 在提交前创建用户、验证码记录和发送所需状态；失败会调用 rollback。Repository 负责 SQLAlchemy 的数据访问，不决定“密码是否合法”或“验证码能否重放”。这就是事务边界应在 Service 而不是路由的原因：业务步骤必须一起成功或一起失败。
5. 本地 Mailpit 接收 SMTP 邮件。浏览器 E2E 通过 Mailpit test API 读取刚发送的邮件并提取验证码，然后仍然调用公开的 `/auth/register/verify`；它没有伪造验证码，也没有越过产品 API。

排查注册失败时，先看浏览器 Network 的稳定 `error.code`，再看后端请求对应的 `request_id`。不要把密码或验证码打到日志。Mailpit UI 在 <http://127.0.0.1:8025>，只用于本地观察；自动化使用 API，避免依赖人工点击。

## 为什么密码和验证码不是同一种“哈希”

密码在 [`backend/app/auth/security.py`](../../backend/app/auth/security.py) 用 Argon2（通过 `pwdlib`）慢哈希。密码熵低，攻击者拿到数据库后会离线猜测；慢哈希故意让每次猜测昂贵，并为每个密码生成盐。

验证码和 opaque refresh token 则是短、随机、服务器生成的高熵值。它们保存 HMAC digest，而不是 Argon2：服务器需要快速等值匹配、可索引地定位记录，并且原始值不应落库。两者共同点是“数据库泄露后不能直接登录”，差别是威胁模型和查询需要不同。把验证码明文、digest、access token 或 refresh token写进日志都是信息泄露，不是调试。

## access、refresh 与 `/users/me`

登录由 [`backend/app/auth/api.py`](../../backend/app/auth/api.py) 的 `/login` 进入 `AuthenticationService.login()`：

- access token 是短期 Bearer JWT，前端只保存在运行时内存；[`frontend/src/auth/api.ts`](../../frontend/src/auth/api.ts) 把它放进 `Authorization` 请求头。
- refresh token 是随机 opaque 值，只经 `HttpOnly`、受限 Path、SameSite Cookie 往返。前端不会也不能读取它。
- `/auth/refresh` 轮换 refresh token。旧 token 被重放时，服务撤销该 family；并发轮换由数据库协议测试覆盖。
- `GET /users/me` 不相信 JWT 里的 role 或 active 状态作为最终事实。它先验签，再从 PostgreSQL 重载用户，所以被禁用账号、被删账号或已变更角色会立刻被拒绝。

这解释了“刷新后为什么还要调 `/users/me`”：refresh 证明浏览器拥有一个仍可用的会话，`/me` 证明该会话对应的当前数据库身份仍被允许使用。前端的 [`frontend/src/auth/RouteGuards.tsx`](../../frontend/src/auth/RouteGuards.tsx) 负责把未认证访问安全地带回 `/login`，并只保留同源 `returnTo`，不能把用户重定向到攻击者 URL。

## RBAC 与管理员审计

用户 H5 没有 `/admin` 页面或角色编辑表单。管理员 API 在 [`backend/app/admin/api.py`](../../backend/app/admin/api.py) 内由后端 RBAC 守卫，即使有人手工构造 HTTP 请求，普通用户仍得到 403。管理员创建/提升只能走 [`backend/app/admin/cli.py`](../../backend/app/admin/cli.py)：

- bootstrap 要求已有、已验证、active 的账号，并以 `system:bootstrap` 作为审计 actor；
- promote 要求一个已验证、active 的现有管理员、非空 reason，拒绝自我提升；
- 角色变更和 `admin_role_audit` 在同一个事务提交，避免“角色已改但没有审计”这种不可追责的坏状态。

用 `uv run python -m app.admin.cli --help` 看参数。实际操作前必须设置生产环境变量；本地演示使用 Mailpit 和本地 PostgreSQL，不能冒充生产审批。

## 测试分层：哪里该测什么

| 层级 | 位置 | 证明什么 | 不该做什么 |
|---|---|---|---|
| Service 单测 | `backend/tests/auth/` | 规则、稳定错误、时钟、token family 行为 | 连真实库或网络 |
| Repository/迁移集成测 | `backend/tests/integration/` | 真 PostgreSQL、锁、事务、Alembic | 回退 SQLite |
| API 合约测 | `backend/tests/auth/` | HTTP、Cookie、OpenAPI、RBAC 映射 | 断言内部私有实现 |
| React 单测 | `frontend/src/**/*.test.tsx` | 用户可见表单和路由行为 | 读服务端密钥 |
| Playwright E2E | `frontend/tests/e2e/` | Vite + FastAPI + Mailpit 的真实浏览器协议 | 伪造 code/token 或调用私有服务 |

后端最小调试循环：

```bash
docker compose up -d --wait postgres postgres-test mailpit
cd backend
APP_ENV=test DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev \
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test \
uv run pytest tests/auth/test_login_me_api.py -q
uv run ruff check . && uv run mypy app
```

前端与完整链路：

```bash
cd frontend
npm run test -- --runInBand
npm run test:e2e -- --grep "full-stack auth"
```

E2E 失败先打开 Playwright trace，再看 Mailpit 的邮件是否送达，再看 FastAPI 的稳定错误码；不要通过增加 `sleep` 掩盖启动或事务问题。`320px`、仅键盘和 200% 缩放属于同一用户旅程的可访问性证据，不是装饰性截图。

## 当前边界和下一步

Phase 1 已交付认证、会话、用户身份和后端 RBAC 基座。`admin-frontend/` 按 ARC-08 明确延后到 Phase 6：后台前端必须是同级独立项目，不能塞进用户 H5。LangGraph、图片识别、营养计算、长期偏好和饮食规划也不是本阶段交付；不要因为 README 里出现项目愿景就假设这些能力已经可用。
