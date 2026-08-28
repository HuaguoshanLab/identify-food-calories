# Phase 1：从前端走进认证后端的代码导读

这不是一份 FastAPI 或 SQLAlchemy 的语法手册，而是一张“读代码地图”。你已经会 React；这一篇的目标是让你能从一个页面按钮出发，追到 API、业务服务、PostgreSQL 和测试，并能说清每一层为什么存在。

先明确边界：Phase 1 已完成注册、验证码、登录、会话管理、找回密码和后端 RBAC。LangGraph、食物图片识别、营养计算和管理后台 UI 还没有实现；它们会建立在这套身份与权限基座上。

## 先建立全局地图

```text
React 页面
  -> frontend/src/auth/api.ts        浏览器请求适配器
  -> FastAPI api.py                  HTTP、Cookie、依赖注入、错误码
  -> service.py                      认证规则与事务边界
  -> repository.py                   SQLAlchemy 查询/写入
  -> models.py + Alembic migration   PostgreSQL 表与约束
```

这五层不是为了“看起来专业”而拆的。

| 层 | 应该负责 | 不应该负责 |
|---|---|---|
| 页面组件 | 表单、加载态、用户提示、跳转 | 拼 JWT、写 SQL、决定账号是否可登录 |
| `api.ts` | 调用后端、发送 Bearer token、解析统一错误 | 保存 refresh token、偷偷修改业务规则 |
| FastAPI 路由 | 请求/响应、Cookie、依赖注入、HTTP 状态码 | 多步数据库业务、散落 ORM 查询 |
| Service | 登录、验证码、轮换、撤销等业务规则与 commit/rollback | 理解 React 路由或 HTTP 的细节 |
| Repository | 有边界的数据访问、`flush`、锁定查询 | 判断“验证码是否应该过期”这种业务规则 |

如果把这些混在一个 `router.py` 里，初期写得快，后面测试、事务和安全规则会全部缠死。这个项目的分层就是为了避免那种垃圾结构。

## 推荐阅读顺序

不要一上来读完整个后端。按下面顺序读，每读完一段就跑对应测试：

1. [`frontend/src/auth/RegisterPage.tsx`](../../frontend/src/auth/RegisterPage.tsx)：从你最熟悉的表单开始。
2. [`frontend/src/auth/api.ts`](../../frontend/src/auth/api.ts)：看页面真正请求了哪个 URL、是否带 Cookie。
3. [`backend/app/auth/api.py`](../../backend/app/auth/api.py)：先只读 endpoint 和依赖函数，不要钻进实现。
4. [`backend/app/auth/service.py`](../../backend/app/auth/service.py)：这是认证规则的核心。
5. [`backend/app/auth/repository.py`](../../backend/app/auth/repository.py) 与 [`models.py`](../../backend/app/auth/models.py)：最后看数据库读写和数据结构。
6. `backend/tests/auth/` 与 `backend/tests/integration/`：用测试反过来验证自己有没有读懂。

阅读后端时先问三个问题：输入从哪里来？状态最终写到哪里？异常由哪一层翻译给用户？能答出来就不是“看过代码”，而是真的理解了链路。

## 链路一：注册与邮箱验证码

### 1. React 表单为什么不能成为最终校验

在 [`RegisterPage.tsx`](../../frontend/src/auth/RegisterPage.tsx) 中，React Hook Form + Zod 会先校验邮箱、密码和确认密码。这只是提升体验：用户少等一次网络请求。

真正的边界在后端的 [`RegisterRequest`](../../backend/app/auth/schemas.py)。任何人都能绕开你的前端，直接发 HTTP 请求；所以“前端已校验”不是安全措施。

### 2. 请求如何进入后端

```text
点击“发送验证码”
  -> registerAccount()
  -> POST /api/v1/auth/register
  -> auth.api.register()
  -> RegistrationService.register()
  -> user + verification_challenge 写入 PostgreSQL
  -> SMTP 发送邮件到 Mailpit（本地）
```

看 [`backend/app/auth/api.py`](../../backend/app/auth/api.py) 的 `register()`：路由函数很短，只把 `RegisterRequest` 交给 `RegistrationService`，并写入 `registration_context` Cookie。不要把完整注册规则塞回这个函数；否则以后换 CLI、任务队列或测试调用时都会被 HTTP 细节绑住。

接着读 `RegistrationService.register()`。这里有三个你必须理解的点：

- 密码由 [`security.py`](../../backend/app/auth/security.py) 的 Argon2 逻辑处理，数据库不保存明文密码。
- 验证码和注册上下文只保存摘要或可验证上下文，React 拿不到 `HttpOnly` Cookie 的原值。
- Service 统一决定 `commit()` 或 `rollback()`；创建用户、创建验证码、发送失败时的回滚必须被当作一个业务操作思考。

### 3. 验证码页面为什么要先读 context

`RegisterVerifyPage` 不从 URL 或 Local Storage 读取验证码上下文，而是请求 `GET /api/v1/auth/register/context`。浏览器会自动携带 `HttpOnly` Cookie，后端只返回脱敏邮箱。

然后验证码提交到 `POST /api/v1/auth/register/verify`。这个端点会检查 Origin/Referer，再交给 `RegistrationService.verify()`。验证成功后，后端删除注册上下文 Cookie；账号被激活，但不会顺便签发登录 token。这样“邮箱验证”和“登录”是两个独立安全动作。

### 动手验证

```bash
docker compose up -d --wait postgres postgres-test mailpit
cd backend
APP_ENV=test DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev \
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test \
.venv/bin/python -m pytest tests/auth/test_registration_verification.py -q
```

测试通过后，在浏览器打开 <http://127.0.0.1:8025> 看本地 Mailpit 邮件。它是本地收件箱，不是生产邮件服务。

## 链路二：登录、access token 与 refresh token

先读 [`LoginPage.tsx`](../../frontend/src/auth/LoginPage.tsx)，然后跳到 `api.ts` 的登录函数。这里最关键的设计是：**access token 与 refresh token 不放在同一个地方。**

```text
POST /auth/login
  -> AuthenticationService.login()
  -> 创建 AuthSession
  -> 创建 RefreshToken（数据库仅保存 digest）
  -> 响应体返回短期 access token
  -> Set-Cookie 写入长期、HttpOnly refresh token
```

- access token：短期 JWT，只放在 `AuthProvider` 的运行时内存，随刷新页面消失。
- refresh token：随机 opaque 值，只存在 `HttpOnly` Cookie。前端 JavaScript 无法读取，所以 XSS 不能直接把它偷走。
- 登录后调用 `GET /api/v1/users/me`：不是多余请求。JWT 只能证明它曾被签发；`/me` 会重新读取 PostgreSQL，确认用户仍 active、角色仍有效、会话没撤销。

对应代码入口：

- [`frontend/src/auth/AuthProvider.tsx`](../../frontend/src/auth/AuthProvider.tsx)：应用启动时执行“refresh，再 `/me`”的恢复流程。
- [`frontend/src/auth/refreshCoordinator.ts`](../../frontend/src/auth/refreshCoordinator.ts)：多个组件同时恢复身份时协调 refresh，避免同一个 refresh token 被并发使用后触发重放保护。
- [`backend/app/auth/service.py`](../../backend/app/auth/service.py) 的 `AuthenticationService.login()` 和 `refresh()`：创建会话、轮换 token、处理重放。

### 为什么 refresh 必须轮换

每次 `/auth/refresh` 都会消费旧 refresh token，创建新 token。旧 token 再出现，服务会撤销整个 session family。这叫重放检测：它不能保证攻击永远不会发生，但能让“同一 token 被两处使用”变成可终止的异常，而不是无限有效的凭证。

读 `AuthenticationService.refresh()` 时重点找四步：`get_refresh_token_for_update()`、校验 session、消费旧 token、创建 successor。`FOR UPDATE` 不是装饰：它让并发 refresh 在数据库层串行化。

## 链路三：账号页为什么能撤销其他设备

页面在 [`SessionList.tsx`](../../frontend/src/auth/SessionList.tsx) 拉取：

```text
GET /api/v1/auth/sessions
  -> AuthenticationService.list_sessions()
  -> SqlAlchemyAuthRepository.list_sessions_for_user()
  -> 只返回当前用户且 revoked_at 为 null 的会话
```

点击远端“撤销会话”后，确认弹窗在 [`RevokeSessionDialog.tsx`](../../frontend/src/auth/RevokeSessionDialog.tsx)，再调用 `DELETE /api/v1/auth/sessions/{session_id}`。当前设备不能走这个接口，必须走 `/auth/logout`；这能避免用户在同一个界面里把当前认证状态搞成不清晰的半失效状态。

这里正好有一个真实的后端调试教训：如果 Repository 查询没有加 `revoked_at IS NULL`，数据库虽然已经标记撤销成功，列表却仍会把已撤销记录返回给前端，用户会看到第二次“撤销会话”。前端刷新缓存不是根治；根因是后端返回了不该返回的数据。对应集成测试在 [`test_auth_database_protocols.py`](../../backend/tests/integration/test_auth_database_protocols.py)。

这个案例要记住：**UI 是后端响应的投影。先确认 API 合约是否正确，再怀疑 React 缓存。**

## 链路四：找回密码与权限

### 找回密码

找回密码在 `accounts/` 模块，不硬塞进 `auth/`：

```text
ForgotPasswordPage
  -> POST /api/v1/auth/password-recovery/forgot
  -> RecoveryService.request_reset()
  -> 邮箱验证码 + HttpOnly recovery context
  -> POST /verify
  -> POST /reset
  -> 更新密码、消费验证码、撤销该用户所有 session family
```

请对照 [`backend/app/accounts/api.py`](../../backend/app/accounts/api.py) 和 [`backend/app/accounts/service.py`](../../backend/app/accounts/service.py) 阅读。最后一步必须是同一事务：如果密码改了但旧 session 没撤销，攻击者仍可能拿旧 refresh token 留在账号里。

### RBAC

用户 H5 不含后台入口不等于有权限控制。真正的权限在后端：[`backend/app/admin/api.py`](../../backend/app/admin/api.py) 的 `/api/v1/admin/probe` 会验证会话，再从数据库读取当前角色。普通用户即使手写请求，仍应收到 403。

这就是“前端隐藏按钮”和“后端授权”之间的区别：前者是体验，后者才是安全。

## 用测试确认自己读懂了

| 你想验证什么 | 从哪里开始 |
|---|---|
| 表单校验、错误提示、路由守卫 | `frontend/src/auth/*.test.tsx` |
| 注册、登录、refresh、Cookie 错误码 | `backend/tests/auth/` |
| PostgreSQL 约束、迁移、行锁、会话筛选 | `backend/tests/integration/` |
| 浏览器 + FastAPI + Mailpit 真实链路 | `frontend/tests/e2e/auth-skeleton.spec.ts` |

推荐执行顺序：

```bash
# 前端：静态检查、单测、构建
cd frontend
npm run lint && npm run typecheck && npm run test -- --run && npm run build

# 后端：真实 PostgreSQL 测试库
cd ../backend
APP_ENV=test DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev \
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test \
.venv/bin/python -m pytest -q
```

看失败时不要只盯着测试结果：先根据失败所属层定位。表单断言失败看 React；401/403 和 Cookie 看 API；并发或迁移失败看真实 PostgreSQL 集成测试。跨层乱查，只会浪费时间。

## 面试时你应该能讲清楚什么

完成本篇后，你至少应能用自己的话回答：

1. 为什么密码用 Argon2，而验证码与 refresh token 存 digest？
2. 为什么 access token 放内存、refresh token 放 HttpOnly Cookie？
3. 为什么 refresh token 必须轮换，重放时为什么要撤销整个 family？
4. 为什么路由不直接写 SQL，事务为什么由 Service 控制？
5. 为什么隐藏后台按钮不能算权限控制？
6. 撤销会话后 UI 仍显示记录时，如何判断是缓存问题还是 API 合约问题？

如果其中任何一题只能背名词，回到对应链路，打开测试，再跟一次调用。你的目标不是把后端术语背出来，而是能够解释项目里每个选择解决了什么具体问题。

## 下一篇会学什么

Phase 2 才会进入 LangGraph：状态、节点、工具调用、追问、有限循环与 checkpoint。到那时会新增 `03-agent-core-walkthrough.md`，并仍然沿用“前端操作 → API → Agent 状态图 → 工具 → 测试”的读法。
