# 管理后台端到端测试

## 职责

`tests/e2e/` 保存管理员可见路径的 Playwright 跨栈测试：登录与无权限安全失败、受保护路由、数据维护确认和审计可见性都必须通过实际后台页面及公开 `/api/v1/admin/*` API 验证。

## 允许依赖

- 可依赖 Playwright、项目受控的测试服务器和隔离测试数据库。
- 测试只能经真实浏览器 UI、公开认证流程和公开 HTTP API 建立状态与断言。
- 禁止直写数据库、伪造/复制 token、调用内部函数、读取浏览器持久化存储、调用真实模型/云服务，或依赖未受控的本地进程。

## 文件索引

| 路径 | 职责 |
| --- | --- |
| `README.md` | 端到端测试职责、允许依赖与文件索引。 |
| `admin-management.spec.ts` | 空隔离库的管理员认证/配置、管理员晋升/降权与保留普通会话、目录生命周期、CSV/批量治理及普通用户拒绝；不清空共享 Mailpit 邮件。 |

## 隔离运行合同

`admin-management.spec.ts` 固定使用 backend `8003`、用户 SPA `5183` 与独立后台 SPA `5184`；只允许分别用 `E2E_ADMIN_BACKEND_PORT`、`E2E_ADMIN_USER_FRONTEND_PORT`、`E2E_ADMIN_FRONTEND_PORT` 覆盖。runner 每次经仓库根 `docker compose up -d --wait postgres-test mailpit`、`backend/tests/run_pg.py` 与 `backend/scripts/run_initialized_app.py` 启动，后者只会 reset 受 guard 保护的 `food_agent_test`、迁移和受控 seed；不复用本地服务，所有 server 均以 HTTP readiness、`reuseExistingServer: false` 和 SIGTERM cleanup 管理。

严格顺序是：浏览器注册并通过 Mailpit 公共 HTTP 读取验证码完成验证 → 受 `run_pg.py` 包装的 audited `app.admin.cli bootstrap` 写入首位角色 → admin SPA 登录并观察 Bearer probe 200 → RuntimeConfig 页面以 If-Match 0 和 Idempotency-Key 的公开 POST 201 创建启用 policy → 目录草稿、服务器 diff、审核、发布、失格与审计 → 完整刷新后 refresh 200 并保留目录 → 普通用户独立浏览器会话 probe 403 → 管理员退出后再刷新仍为登录页。

CLI 只允许首位管理员角色 bootstrap：它不会创建 RuntimeConfig，也不能取代 Guard 或业务 API 的 PostgreSQL RBAC。`/users/me` 仅建立活动身份；probe 与每个 `/api/v1/admin/*` 端点才是授权证据。不得通过数据库写入、token/cookie 注入、浏览器存储、fixture、内部 service/repository 或真实模型建立成功状态。
