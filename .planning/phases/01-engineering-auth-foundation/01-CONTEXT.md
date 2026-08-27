# Phase 1: 工程、身份与权限基座 - Context

**Gathered:** 2026-08-27
**Status:** Ready for planning

<domain>
## Phase Boundary

本阶段交付可运行的 React/Vite 前端、FastAPI 后端、PostgreSQL 数据库和完整身份基座。用户可以注册、登录、刷新、退出和管理登录会话；系统具备 `user`/`admin` RBAC。阶段同时建立后续 LangGraph、模型 Provider、长期记忆和后台管理必须遵守的分层、测试与教学规范，但本阶段不实现 Agent 图、图片识别、Mem0、饮食规划或完整后台页面。

</domain>

<decisions>
## Implementation Decisions

### 产品转向与工程边界

- **D-01:** 原“单菜搜索 + 克数 + 热量表单”Phase 1 正式废弃；旧计划只保留在 Git 历史，不再作为实现输入。
- **D-02:** 项目名称改为“基于 LangGraph 的多模态饮食健康智能 Agent”，目标是可上线、可写简历并能经受面试深挖。
- **D-03:** 保持前后端分离：`frontend/` 使用 React + TypeScript + Vite，`backend/` 使用 FastAPI + Python 3.11+。
- **D-04:** 后端继续采用模块化单体，不为“看起来高级”引入微服务、队列或 Kubernetes。
- **D-05:** 当前未提交的 FastAPI 配置与测试库 guard 可评估复用，但必须由新计划逐文件验证，不能默认视为完成。

### 注册、登录与会话

- **D-06:** v1 使用邮箱 + 密码注册登录；邮箱做规范化并建立唯一约束。
- **D-07:** 密码使用 Argon2id 或经研究确认的同等级强哈希；任何日志、Schema 和模型都不能返回密码哈希。
- **D-08:** access token 短时有效，由前端保存在内存；refresh token 通过 `HttpOnly`、`Secure`（生产）、`SameSite` Cookie 提交。
- **D-09:** refresh token 只保存服务端哈希，采用 token family 轮换；重复使用旧 token 时撤销整个 family。
- **D-10:** 用户可以列出并撤销自己的登录会话；退出撤销当前会话，而不是只让浏览器丢 token。
- **D-11:** 认证失败返回统一信息，避免通过响应判断邮箱是否注册。
- **D-12:** 邮箱验证和密码重置使用 Mail Provider 接口；本地用安全开发实现，真实邮件供应商不锁死在 Phase 1。

### 权限与后台准备

- **D-13:** 角色先固定为 `user`、`admin`，权限由后端依赖/策略强制执行。
- **D-14:** 前端隐藏后台入口只改善体验，不是安全边界；普通用户访问 `/api/v1/admin/*` 必须稳定返回 403。
- **D-15:** Phase 1 只交付最小受保护的 admin probe/API 契约证明 RBAC；完整后台管理在 Phase 6。
- **D-16:** 管理员账号通过显式 CLI/seed 命令创建，公开注册永远不能选择 `admin` 角色。
- **D-17:** 为后续后台审计预留统一 actor/user 标识，但本阶段不实现完整业务审计页面。

### 后端学习深度

- **D-18:** 后端依赖方向为 API → Application/Service → Repository → SQLAlchemy Model；Pydantic Schema 与 ORM Model 分离。
- **D-19:** FastAPI 路由只处理 HTTP 语义、依赖和响应映射；密码规则、令牌轮换与权限判断放在应用服务。
- **D-20:** Service 单测使用 fake repository；Repository 与 migration 测试使用独立真实 PostgreSQL，禁止用 SQLite 冒充。
- **D-21:** API 合约测试覆盖状态码、Cookie 属性、错误 Schema、令牌轮换、越权和 OpenAPI。
- **D-22:** `docs/learning/01-auth-and-backend-foundation.md` 必须用中文解释完整请求链、依赖注入、事务、密码哈希、JWT/refresh 轮换、RBAC 和测试分层。
- **D-23:** 代码注释解释设计理由与安全原因，不逐行翻译 Python 语法；教学重点放在可运行示例、测试和文档。
- **D-24:** README 提供前后端分开启动、迁移、创建管理员、测试与常见调试命令。

### 为 Agent 预留但不提前实现

- **D-25:** 后续文本推理默认 DeepSeek，视觉理解默认 Qwen-VL；二者通过独立 Provider 接口接入。
- **D-26:** 万相属于图像生成/编辑能力，不作为食物识别 Provider。
- **D-27:** LangGraph 主图、Postgres Checkpointer、SSE、Mem0 和 pgvector 均在后续阶段实现；Phase 1 只保证用户身份和数据库边界可以承载它们。
- **D-28:** 后续 Agent 使用一个主图和餐食分析/饮食规划两个子图，不实现互相自由对话的多 Agent 网络。

### the agent's Discretion

- 选择符合上述安全约束的 JWT 库、Argon2 库、UUID 类型、Repository 接口与依赖注入细节。
- 选择数据库表名、索引与 migration 拆分，只要会话轮换、撤销和 RBAC 能被明确测试。
- 设计登录注册页面的具体视觉细节，保持移动端优先、浅色、Slate + Teal 与 8px 圆角设计语言。

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product and roadmap

- `.planning/PROJECT.md` — Agent 产品定位、完整技术栈、模型分工与教学契约。
- `.planning/REQUIREMENTS.md` — Phase 1 的 AUTH、ARC 和 EDU 正式需求。
- `.planning/ROADMAP.md` — 七阶段边界与 Phase 1 成功条件。
- `.planning/STATE.md` — 当前重规划状态和未提交代码提醒。
- `AGENTS.md` — 强制架构、安全、测试与教学规则。

### External official references

- DeepSeek API documentation — text reasoning/tool provider; current API does not accept image inputs.
- Alibaba Cloud Model Studio visual understanding documentation — Qwen-VL image provider boundary.
- Alibaba Cloud Model Studio image generation documentation — Wan/Wanx is excluded from food recognition.
- LangGraph persistence and interrupt documentation — informs later checkpoint and Human-in-the-loop phases, not Phase 1 implementation.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `backend/pyproject.toml` — interrupted old executor created a Python project skeleton; planner must audit dependencies against auth scope.
- `backend/app/core/config.py` — environment settings skeleton may be reusable.
- `backend/app/core/database.py` — SQLAlchemy engine/session skeleton may be reusable.
- `backend/tests/conftest.py` and `backend/tests/unit/test_test_database_guards.py` — fail-closed test database ideas remain valid if tests pass under the new schema.

### Established Patterns

- Python 3.11.16 is installed and available as `python3.11`.
- GSD worktrees are disabled because Codex agents share the main workspace; execution must be sequential.
- No frontend code or committed product implementation exists yet.

### Integration Points

- New auth modules connect to FastAPI `/api/v1/auth`, SQLAlchemy repositories and React Router pages.
- RBAC must be expressed as a reusable backend dependency/policy for future `/api/v1/admin` routes.
- User IDs created here become LangGraph thread ownership and Mem0 namespace keys in later phases.

</code_context>

<specifics>
## Specific Ideas

- 用户是前端开发者，只了解部分后端；实现需要边写边教，但不降低工程质量。
- 简历项目必须能用实际测试、运行截图、评测报告和文档证明每条能力，而不是堆“LangGraph、Mem0、向量库”等关键词。
- 最终 README 应能回答：State 存什么、何时追问、如何恢复、防止死循环、短期与长期记忆如何分工、视觉识别错了如何纠正、营养库查不到如何降级。

</specifics>

<deferred>
## Deferred Ideas

- LangGraph 主图、DeepSeek Provider、营养工具和 interrupt/resume — Phase 2。
- Qwen-VL 图片识别与安全上传 — Phase 3。
- Mem0、pgvector 与餐食历史 — Phase 4。
- 饮食规划子图 — Phase 5。
- 用户数据看板与完整后台管理系统 — Phase 6。
- 冻结评测、安全攻击测试和部署门禁 — Phase 7。

</deferred>

---
*Phase: 1-工程、身份与权限基座*
*Context gathered: 2026-08-27*
