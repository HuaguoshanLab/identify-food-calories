# Frontend E2E Tests

`h5-visual.spec.ts`新增独立资料流程：缺资料禁用生成→我的首次保存→计划摘要与偏好复核；使用隔离账号与公开API，不调用模型。

## 职责

`tests/e2e/` 通过真实浏览器验证 Vite 页面与 FastAPI API 的跨栈契约。Playwright 配置负责启动依赖、等待 readiness，并在测试结束时清理其拥有的应用进程。

## 允许依赖

- 只使用 `@playwright/test` 和公开 HTTP 合约。
- 基础设施限定为 `postgres-test` 与 Mailpit；不得连接开发数据库或外部服务。
- 禁止固定 `sleep`；所有等待必须基于 HTTP readiness 或可观察页面状态。

## 文件索引

| 文件 | 职责 |
|---|---|
| `health.spec.ts` | Vite、FastAPI 与版本化健康端点的最小全栈证明 |
| `auth-helpers.ts` | 仅通过页面与公开 Mailpit HTTP 创建、验证、登录和恢复隔离测试账号的复用夹具 |
| `auth-skeleton.spec.ts` | 从 Mailpit 取真实验证码的注册、恢复、会话撤销与登出浏览器证据 |
| `h5-visual.spec.ts` | 430px 八张历史视觉基线及图片/文字candidate；框架用例自行注册隔离账号，可单独回归320px/桌面、键盘、历史和滚动边界；改版未覆盖旧快照 |
| `h5-visual.spec.ts-snapshots/` | Git 维护的八张 H5 视觉基线与其安全更新合同 |
| `agent.spec.ts` | 真实注册登录后的文字 Agent 纵向报告、SSE 公开路径、刷新同线程恢复、图片 multipart 估算，以及“我不吃辣”自动记忆的查看、编辑、确认删除和 320px 空态回归。 |
| `safe-stream-progress.spec.ts` | 真实认证用户的分析/规划安全阶段、无内部泄露和键盘焦点路径。 |
| `records-weekly-review.spec.ts` | 真实注册登录后 Records 的低覆盖周复盘；current 请求不携带浏览器 `week_start`/时区范围，公开 DTO 不泄露 Provider 细节。 |
| `records-dashboard.spec.ts` | 专属空库 runner 中：页面注册/邮箱验证、受审计首位管理员 CLI、admin Guard 200 与 RuntimeConfig POST 201；Shanghai/Los Angeles 普通用户走分析保存与 Records 四项投影，确认先于读取、`today` 属于服务端本周；同账号换到相反时区 fresh login 必须安全 409 且零 dashboard read。 |

E2E 的前端与 CORS origin 固定为 `http://127.0.0.1:5178`；账号只可经过页面注册、Mailpit 公开 HTTP 读取验证码和页面登录获得身份，禁止 seed 数据库或注入 token。

Records runner 可用 `E2E_FRONTEND_PORT`、`E2E_BACKEND_PORT` 和 `E2E_RECORDS_ADMIN_FRONTEND_PORT`（默认 5178/8000/5185）覆盖端口。每次运行只经 `run_pg.py` 允许的 `food_agent_test` 清库、迁移及受控种子重建；它不复用 06-28 的进程、账号、数据库或 RuntimeConfig。首位管理员 CLI 只写审计角色提升，运行配置必须由 admin SPA 的公开 `POST /api/v1/admin/runtime-config` 创建；禁止 DB 直写、token/cookie 注入、内部调用、固定 sleep 与真实模型。

- `plans.spec.ts`：通过公开后台准备运行配置，并验证时区确认、生成存档、刷新恢复、调整版本、历史与删除；使用 runner 的独立端口，不复用本地开发服务。
