# Walking Skeleton — 基于 LangGraph 的多模态饮食健康智能 Agent

**Phase:** 1  
**Generated:** 2026-08-27  
**Plan topology:** 14 sequential executable plans

## Capability Proven End-to-End

> 用户从 React 公开落地页注册，FastAPI 把 Argon2id 密码摘要和验证码摘要写入真实 PostgreSQL，Mailpit 捕获本地验证邮件；用户输入 6 位码激活后登录，刷新页面通过 HttpOnly refresh token 恢复 access token，再由 `GET /api/v1/users/me` 从数据库读取当前邮箱和角色，最终可管理并撤销自己的登录会话。

Walking Skeleton 分段完成：01/02 建立 Compose、Mailpit 和可运行全栈壳；03/04 建立验证 challenge 与注册激活；05/06 建立登录、`/users/me`、真实 PG 限流；07/08 建立真实 CSS/shadcn 构建；09 完成公开认证 UI；10/11 完成会话后端与 AuthProvider；12 完成后端 RBAC/CLI 审计；13 完成密码恢复；14 以 Mailpit E2E 和安全门禁收口。

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Framework | React + TypeScript + Vite；FastAPI + Python 3.11 | 前后端独立，适合后端学习与后续 LangGraph Python 生态 |
| Data layer | 固定 pgvector/PostgreSQL + SQLAlchemy 2 sync + Psycopg 3 + Alembic | 身份、验证码、会话和审计均由真实事务约束；vector 仅验证运行时 |
| Registration | `/register` → `/register/verify` → `/login` | 账号先未激活；6 位码摘要、10 分钟、5 次、60 秒、单次消费由后端执行 |
| Local mail | 固定官方 `axllent/mailpit`，SMTP 1025/UI 8025 | 本地可演示和 E2E；生产通过 MailProvider，不绑定云厂商 |
| Auth | Argon2id；短时 JWT；opaque rotating refresh；数据库权威 `/users/me` | token claims 不承担邮箱、active 或最终角色真相 |
| Authorization | backend `/api/v1/admin/probe` + auditable CLI | admin 变更写 actor/target/before/after/time/reason；用户 H5 无后台页面 |
| Frontend routes | `/`、auth、privacy/terms 公开；`/app` 登录后访问 | returnTo 只允许同源、已登记的受保护相对路径，不提供游客分析 |
| Admin frontend | Phase 6 创建同级 `admin-frontend/` | Phase 1 不创建空项目，也不把 `/admin` 塞入用户 H5 |
| Directory contract | 根、frontend、backend 及每个新增目录维护 README；三处维护 AGENTS | 职责、允许依赖和索引在创建/变更时同步 |

## Stack Touched in Phase 1

- [ ] React/Vite、FastAPI、lint/type/test runner
- [ ] PostgreSQL/pgvector dev+test 与 Mailpit
- [ ] 注册验证、登录、刷新、`/users/me`、会话与密码恢复
- [ ] 后端 RBAC、admin probe、可审计 CLI
- [ ] 官方 shadcn/Base UI、Tailwind、公开与受保护路由
- [ ] 中文教学、OpenAPI、安全和 Playwright E2E 证据

## Out of Scope

- LangGraph、DeepSeek、确定性营养工具与 interrupt/resume（Phase 2）
- Qwen-VL 与安全图片链（Phase 3）
- Mem0、业务 pgvector 与餐食历史（Phase 4）
- 饮食规划子图（Phase 5）
- 用户趋势看板与独立 `admin-frontend/` 完整后台（Phase 6）
- 冻结评测、全量攻击测试、CI/发布门禁（Phase 7）

## Subsequent Slice Plan

- Phase 2: 登录用户通过文字请求进入可追问 Agent 图
- Phase 3: Qwen-VL 图片感知进入同一餐食分析子图
- Phase 4: 权威餐食记录、Checkpoint、Mem0 与受过滤 pgvector
- Phase 5: 可校验、可恢复的饮食规划子图
- Phase 6: 用户看板与独立管理后台
- Phase 7: 评测、安全、CI 和部署证据闭环
