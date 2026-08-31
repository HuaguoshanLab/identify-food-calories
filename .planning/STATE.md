---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: release_blocked
stopped_at: Plan 02-18 executed; Phase 02 release gate blocked by undefined Spearman and incomplete authenticated browser matrix
last_updated: "2026-08-31T00:00:00Z"
last_activity: 2026-08-31
progress:
  total_phases: 8
  completed_phases: 2
  total_plans: 42
  completed_plans: 42
  percent: 25
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-26)

**Core value:** 让用户通过图片或自然语言得到可追问、可校验、可追溯、能记住个人偏好的饮食分析与规划结果。
**Current focus:** Phase 02 — agent

## Current Position

Phase: 02 (agent) — RELEASE BLOCKED
Plan: 18 of 18 executed
Status: 发布门禁未通过；不得标记 Phase 02 完成或启动依赖它的 Phase 03 实现
Last activity: 2026-08-31

Progress: [██████████] 100% plans executed; release blocked

## Performance Metrics

**Velocity:**

- Total plans completed: 14
- Average duration: 13 min
- Total execution time: 2.9 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 14 | 176 min | 13 min |

**Recent Trend:**

- Last 5 plans: 13 min, 10 min, 12 min, 9 min, 14 min
- Trend: stable, 13 min average

*Updated after each plan completion*
| Phase 01 P02 | 23 min | 2 tasks | 14 files |
| Phase 01 P03 | 12 min | 2 tasks | 18 files |
| Phase 01 P04 | 15 min | 2 tasks | 17 files |
| Phase 01 P05 | 13 min | 2 tasks | 10 files |
| Phase 01 P06 | 19 min | 2 tasks | 15 files |
| Phase 01 P07 | 13 min | 2 tasks | 17 files |
| Phase 01 P08 | 8 min | 2 tasks | 16 files |
| Phase 01 P09 | 15 min | 2 tasks | 15 files |
| Phase 01 P10 | 13 min | 2 tasks | 13 files |
| Phase 01 P11 | 10 min | 2 tasks | 17 files |
| Phase 01 P12 | 12 min | 2 tasks | 17 files |
| Phase 01 P13 | 9 min | 2 tasks | 14 files |
| Phase 01 P14 | 14 min | 2 tasks | 22 files |
| Phase 01.1 P01 | 5 min | 3 tasks | 6 files |
| Phase 01.1 P02 | 5 min | 3 tasks | 10 files |
| Phase 01.1 P03 | 10 min | 3 tasks | 8 files |
| Phase 01.1 P04 | 9 min | 2 tasks | 3 files |
| Phase 01.1 P05 | 6min | 2 tasks | 4 files |
| Phase 01.1 P06 | 6min | 3 tasks | 7 files |
| Phase 01.1 P07 | 8 min | 3 tasks | 9 files |
| Phase 01.1 P08 | 42 min | 3 tasks | 14 files |
| Phase 01.1 P09 | 13min | 1 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Phase 1]: 正式架构为 React + TypeScript + Vite 前端与 FastAPI + SQLAlchemy 2 + Alembic 后端。
- [Phase 1]: PostgreSQL 持久化受控菜品、匿名结构化分析和用户修正；原图不长期保存。
- [All phases]: 采用垂直 MVP，不引入微服务、消息队列或未被真实数据证明必要的异步基础设施。
- [Phase 1]: 项目重构为 LangGraph 多模态饮食健康 Agent，并加入邮箱认证、RBAC、长期记忆和后台管理路线。 — 用户要求项目可上线、可写简历并支持后端学习。
- [Phase all]: DeepSeek 负责文本推理，Qwen-VL 负责视觉理解；所有模型通过 Provider 解耦，万相不用于识别。 — 当前 DeepSeek API 不支持图片输入，万相属于图像生成，Qwen-VL 才是视觉理解模型。
- [Phase 01]: 本地基础设施固定 pgvector 0.8.6/PostgreSQL 16 与 Mailpit 1.30.6，并只绑定回环地址。 — 保证可复现并避免浮动镜像遗漏安全修复。
- [Phase 01]: production 必须满足强密钥、Secure Cookie、显式 CORS 和完整 SMTP 凭据。 — 不允许本地 Mailpit 或开发默认值静默进入生产。
- [Phase 01]: 前端依赖只允许来自 Phase 1 研究的 VERIFIED 清单，并对 28 个直接依赖执行精确版本与 integrity 核对。
- [Phase 01]: Playwright 使用固定端口、reuseExistingServer=false、HTTP readiness 和 SIGTERM 清理，拒绝复用未知本地进程造成假绿。
- [Phase 01]: 验证码当前性由 user_id + purpose 的 PostgreSQL partial unique index 强制，终态由 consumed_at/invalidated_at 互斥约束表达。
- [Phase 01]: Repository 只 query/add/flush，Service 保留多步骤认证协议的 commit/rollback 事务边界。
- [Phase 01]: APP_ENV=test 的 Alembic 环境只使用经过隔离 guard 验证的 TEST_DATABASE_URL。
- [Phase 01]: 验证码使用 6 位 ASCII CSPRNG，并按高熵 context 作用域做 HMAC；数据库只保存摘要。
- [Phase 01]: registration context 由服务端密钥与 challenge UUID 可重建，再以摘要落库，兼顾冷却期非枚举与 digest-only。
- [Phase 01]: 邮箱验证只激活账号并要求登录，不自动创建 session 或签发 token。
- [Phase 01]: access token 固定 HS256/typ/issuer/audience，并严格校验最小 claims。
- [Phase 01]: /users/me 的 email、active 和最终 role 每次按 JWT sub 从 PostgreSQL 重读。
- [Phase 01]: refresh token 使用 256-bit opaque 原文进 HttpOnly Cookie，数据库只保存 HMAC 摘要。
- [Phase 01]: 登录限流同时累计规范化 principal 与 source 的 secret-scoped HMAC v1 bucket，数据库不保存 raw 邮箱或网络来源。
- [Phase 01]: 登录失败阈值固定为 5 次/5 分钟并封禁 5 分钟；窗口与 retry_after 由注入时钟确定。
- [Phase 01]: PostgreSQL 原子 upsert 负责跨 worker 失败累计，Service 负责失败提交、成功 bucket 复位与 session 事务边界。
- [Phase 01]: Vite 统一承载 React、Tailwind CSS v4 与 Vitest 配置，避免 build/test alias 漂移。
- [Phase 01]: shadcn 固定官方 base-nova/Base UI registry，cn 位于 components/ui，不创建无职责 lib 目录。
- [Phase 01]: 九个 UI-SPEC 原语一律由官方 shadcn Base UI registry 生成；Button/Badge 的 variants 依赖 class-variance-authority 0.7.1 作为直接生产依赖。
- [Phase 01]: Fast Refresh 的 variants 导出例外仅限官方 src/components/ui 原语，业务组件仍执行完整规则。
- [Phase 01]: 用户 H5 只保留公开认证与受保护 /app 入口，不注册 /admin、后台导航或 admin probe；独立后台延后 Phase 6。
- [Phase 01]: 密码恢复后端 API 未交付前，前端只提供安全 shell，不伪造网络端点或持久化 pending context。
- [Phase 01]: refresh 原文只存在于 HttpOnly Cookie 和一次性 Service 返回值；数据库仅保存 HMAC digest，已消费 refresh 的 replay 原子撤销 session family。 — 防止 token 泄露、竞争双签发和 replay 后 successor 继续有效。
- [Phase 01]: access JWT 的既有 jti 绑定 auth session，当前会话只能 logout，其他会话的列表/撤销必须 user_id 作用域。 — 使会话管理无需暴露 refresh 原文且不产生当前 access token 的模糊状态。
- [Phase 01]: 浏览器身份必须 refresh 后经 /users/me 建立，access token 仅留在运行时内存。 — 阻断 JWT claims 冒充最终身份与浏览器 token 持久化。
- [Phase 01]: returnTo 仅允许已登记的 /app 相对路径，当前会话只退出而远端会话必须确认撤销。 — 阻断开放跳转/admin 表面并保留清晰会话语义。
- [Phase 01]: admin probe 先沿用既有 session-bound Bearer 验证，再按 subject 从 PostgreSQL 读取 active role；JWT role claim 不参与最终授权。
- [Phase 01]: 首次 bootstrap 使用 system:bootstrap actor；后续提升只接受已验证、active 的现有 admin actor，拒绝自我提升和空 reason。
- [Phase 01]: 角色提升和 audit 在同一 Session transaction 提交；事务级 PostgreSQL advisory lock 串行化首次管理员的 check-then-promote 判定。
- [Phase 01]: 密码重置在一个数据库事务内完成密码哈希更新、验证码消费与用户全部 session/refresh family 撤销；恢复外部 envelope 必须包含未知账号的 signed decoy context，避免二次枚举。 — 真实 PostgreSQL 并发与 rollback 测试已验证。
- [Phase 01]: Playwright 每次只清空 `food_agent_test`，显式从 0001 迁移到 head，且 E2E FastAPI 只连接隔离数据库。 — 防止迁移/应用指向不同数据库造成假绿。
- [Phase 01]: 密码恢复浏览器端仅使用公开 API 与 HttpOnly recovery context，不把验证码、context 或 token 放进 React 持久状态。 — 与后端的非枚举和摘要策略保持一致。
- [Phase 01]: README 合同从 Git 已跟踪源文件推导目录，自动检查三段式 README 和父目录索引。 — 防止生成目录影响审计且让新增模块文档可验证。
- [Phase 01.1]: 在 Agent 核心之前插入 H5 UI 基座与现有页面迁移阶段。 — 先统一页面壳、四 Tab 目标信息架构、滚动、安全区和语义 token，再承载 Agent 页面。
- [Phase 01.1]: H5 视口、唯一主滚动区与底部导航统一由 layouts/ 管理，业务页面不得重复创建全屏或滚动根。
- [Phase 01.1]: 四 Tab active 状态从 routePaths 与 NavLink 推导，认证与详情返回使用确定路径，不依赖浏览器历史。
- [Phase 01.1]: 未开放 Tab 仅通过锁定标题与状态说明呈现；账号详情只读映射 AuthProvider，会话详情复用 SessionList 作为唯一 Query 所有者。 — 避免假功能、身份数据重复披露和会话缓存分叉。
- [Phase 01.1]: 完全空的会话 API 响应是异常可恢复状态；只有存在当前会话且无其他会话时才显示正常空态。 — 避免将身份/服务异常错误呈现为用户只有当前设备在线。
- [Phase 01.1]: 认证步骤进度由共享 AuthEntryPage 在标题前渲染；验证码与恢复 context 继续只由公开 API 和 HttpOnly Cookie 管理。 — 符合已冻结 UI-SPEC，并避免在 React 持久状态复制敏感认证上下文。
- [Phase 01.1]: 所有 /app 子路由只经过一个 pathless RequireAuthentication；/app index replace 到 /app/me，四个 Tab 保持默认 push 历史。 — 统一深链身份恢复与浏览器历史语义。
- [Phase 01.1]: 视觉基线只固定 430×932；320px 和桌面使用布局、滚动、键盘与历史断言，避免截图矩阵失控。 — 八张 Git 基线由后续人工 Plan 09 审查。
- [Phase 01.1]: 内置浏览器验收只通过真实页面与公开 Mailpit HTTP 走认证/会话链，不直接写数据库、复制 token 或读取浏览器存储。 — 让视觉与交互证据保持同一真实信任边界。
- [Phase 01.1]: 八张 430×932 H5 基线经用户人工批准；首页仅接受 CTA 语义修复导致的文本渲染更新。 — 自动视觉测试不能代替人工设计批准。
- [Phase 02]: 24-case 双专家签署必须绑定稳定 pseudonym、role、rubric、dataset 与 code-eval hashes；同一 reviewer 可跨 case 审核，但同 case 同角色不得重复。
- [Phase 02]: Promptfoo 正式 Judge 采用 phase02-judge-json-thinking-disabled.v4，串行 36-call、无缓存、零重试、JSON object 与 thinking.disabled 合同均安全绑定；实际 36/36 完成并以 usage 记账。
- [Phase 02]: visual candidate 仅以精确 SHA 获批；official baseline 不因 Plan 02-17 而晋升。
- [Phase 02]: Plan 02-18 的发布报告精确绑定数据集、code-eval、双角色签署和 Promptfoo 证据；当前真实评分序列导致 Spearman 未定义，发布结论为 FAIL，不能以相同分数或重试刷绿。

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 02]: 发布门禁仍阻断：当前 24-case code-eval 已更新为 `a4736596…`，但旧专家签署、Judge 与发布报告不再绑定该 SHA；仍需真实复审、重新授权 Judge、以及认证成功/错误/空态的内置浏览器矩阵。Spearman 不得通过改分或重试刷绿。
- [Phase 3]: Qwen-VL 第三方图片处理地区、留存和删除承诺需在接入前核实。
- [Phase 4]: Mem0 长期记忆必须验证用户隔离、可审计写入和删除链。

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Architecture | 微服务、消息队列、分布式任务系统 | Out of scope for v1 | Roadmap creation |
| Product | 账号、历史记录、宏量营养素与扩展菜品 | Deferred to v2 | Roadmap creation |

## Session Continuity

Last session: 2026-08-31T00:00:00Z
Stopped at: 02-18-PLAN.md 已人工收尾；Phase 02 处于 release_blocked。
Resume file: .planning/phases/02-agent/02-18-SUMMARY.md
