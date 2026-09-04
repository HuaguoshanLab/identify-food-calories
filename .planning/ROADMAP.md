# Roadmap: 多模态饮食健康智能 Agent

## Overview

路线图按可演示的垂直切片推进。先建立身份、权限和正式工程骨架，再交付一个文字可追问的 LangGraph Agent，随后接入 Qwen-VL 图片感知、长期记忆、饮食规划、用户看板与后台管理，最后通过评测、安全和部署门禁形成可上线、可写简历的完整项目。

DeepSeek 与 Qwen-VL 通过 Provider 分工；营养事实始终来自确定性工具和受控数据库。LangGraph Checkpoint 管理短期执行状态，Mem0 管理跨会话偏好，PostgreSQL 保存权威业务记录。

## Phases

- [x] **Phase 1: 工程、身份与权限基座** — 建立 React/FastAPI/PostgreSQL、注册登录、会话轮换、RBAC 和教学规范。（阶段验收已完成）
- [x] **Phase 2: 可追问的 Agent 核心** — 建立 LangGraph 主图、餐食分析子图、确定性营养工具、Checkpoint 和有界循环。（用户手动接受阶段完成；发布报告仍为 FAIL）
- [x] **Phase 3: 多模态餐食分析闭环** — 接入安全图片上传与 Qwen-VL，多菜识别、份量追问、校验和最终报告。（发布证据已批准，UAT 4/4 通过）
- [x] **Phase 4: 餐食记录与长期记忆** — 保存餐食历史，接入 Mem0 与 pgvector，并提供记忆查看和删除。 (completed 2026-09-01)
- [x] **Phase 5: 饮食规划子图** — 根据身体目标生成并校验餐单，支持用户反馈后的 Human-in-the-loop 调整。 (completed 2026-09-02)
- [x] **Phase 6: 用户看板与后台管理** — 完成趋势分析、周复盘、营养目录管理、模型配置、运行审计与 RBAC 管理界面。 (completed 2026-09-04)
- [ ] **Phase 7: 评测、安全与上线** — 冻结评测、攻击测试、成本和延迟门禁、CI 与 Docker 演示闭环。

## Phase Details

### Phase 1: 工程、身份与权限基座

**Goal:** 用户可以安全注册、登录和退出；开发者能运行独立前后端与 PostgreSQL，并从文档理解完整认证链路。
**Mode:** mvp
**Depends on:** Nothing
**Requirements:** AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06, ARC-01, ARC-02, ARC-03, ARC-04, ARC-07, EDU-01
**Success Criteria:**

1. Docker Compose 启动 PostgreSQL；React/Vite 与 FastAPI 分别运行并通过 `/api/v1` 通信。
2. 邮箱注册、登录、access token、HttpOnly refresh token 轮换、退出和会话撤销通过自动化测试。
   注册必须经过邮箱验证码激活，本地邮件由 Docker Mailpit 捕获。

3. `user` 与 `admin` 权限在后端强制执行；普通用户请求后台 API 返回统一 403。
4. SQLAlchemy、Pydantic、Repository、Service 和 API 边界清晰，Alembic 可从空库重建结构。
5. `docs/learning/01-auth-and-backend-foundation.md` 能解释密码哈希、令牌轮换、依赖注入、数据库事务和测试分层。
6. 根目录、`frontend/` 与 `backend/` 均包含本级 `README.md` 和 `AGENTS.md`；本阶段新增的每个目录均有同次提交的职责、允许依赖和文件索引说明。

### Phase 01.1: H5 UI 基座与现有页面迁移 (INSERTED)

**Goal:** 用户能在统一、移动端优先的 H5 页面壳中完成既有公开认证与账号会话流程，并通过四个独立 Tab、明确详情层级和可审查视觉基线获得稳定、可访问的导航体验。
**Requirements:** None（阶段专属 UX 合同；本阶段不完成或认领 UI-01）
**Depends on:** Phase 1
**Plans:** 10/10 plans complete

**Success Criteria:**

1. 首页、全部认证/法律页面、四个 Tab 和两个“我的”详情页使用统一 MobileFrame，并在 320px 至桌面设备容器中保持单滚动、安全区和无横向溢出。
2. `/app` replace 到 `/app/me`；四个 Tab 使用独立路径和普通 history push；未开放页面只显示标题与“功能即将开放”。
3. “我的”只链接到只读账号资料与登录会话详情；退出当前设备、撤销其他会话、refresh/returnTo 和真实认证协议保持 Phase 1 行为。
4. 新页面只使用 shadcn 语义 token，`.dark` 仅预留，不新增主题开关、UI 库、后端 API、数据库或未来饮食业务。
5. 组件/路由测试、真实 FastAPI/PostgreSQL/Mailpit Playwright 流程、八张 430×932 Git 基线、320/desktop 布局检查和 Codex 内置浏览器验收通过；基线经人工审查后批准。

Plans:

- [x] 01.1-01-PLAN.md — 同步占位页合同，建立语义主题和精确受保护路径表
- [x] 01.1-02-PLAN.md — 建立 MobileFrame、公开页壳、Tab 壳、详情壳与四项导航
- [x] 01.1-03-PLAN.md — 实现诚实占位页、“我的”根页和账号/会话详情内容
- [x] 01.1-04-PLAN.md — 迁移真实会话列表、退出和撤销确认状态
- [x] 01.1-05-PLAN.md — 迁移首页、隐私和条款公开页面
- [x] 01.1-06-PLAN.md — 迁移登录、注册、验证和密码恢复表单
- [x] 01.1-07-PLAN.md — 接线统一认证守卫、嵌套路由、深链和浏览器历史
- [x] 01.1-08-PLAN.md — 建立真实跨栈 E2E、响应式门禁、视觉基线和内置浏览器验收
- [x] 01.1-09-PLAN.md — 人工审查并批准八张 430px Git 视觉基线
- [x] 01.1-10-PLAN.md — 定向修复认证错误恢复与受保护路由标题焦点

### Phase 2: 可追问的 Agent 核心

**Goal:** 用户通过文字描述一餐时，Agent 能使用确定性工具补齐信息、计算营养并在中断后恢复。
**Mode:** mvp
**Depends on:** Phase 01.1
**Requirements:** AGT-01, AGT-02, AGT-03, AGT-04, AGT-05, AGT-06, AGT-07, NUT-01, NUT-02, NUT-03, NUT-04, NUT-05, ARC-05, ARC-06, QLT-02
**Success Criteria:**

1. LangGraph State、节点和条件边有显式类型，主图可路由到餐食分析子图。
2. 缺少菜名或克数时通过 interrupt 追问；相同 thread 恢复后继续执行，不重复已完成工具。
3. 菜品查询、营养计算和异常校验均调用领域工具，模型不能直接写最终营养数值。
4. 最大循环、工具调用、超时和错误终止均有确定性状态图测试。
5. DeepSeek Provider 与 Fake Provider 可互换；测试和本地演示不强制消耗付费 API。

**Plans:** 18/18 plans executed; **Phase status:** 用户于 2026-08-31 手动接受完成；**Release:** FAIL（保留当前 Spearman 合同；真实专家/Judge 配对分数为常数，Spearman 未定义；内置浏览器认证矩阵未完成）

**Wave 1**

- [x] 02-01-PLAN.md — 建立供应链证据门、hash-complete 依赖锁与实际执行环境
- [x] 02-03-PLAN.md — 建立 Reasoning Provider DTO、端口、Fake 与测试工厂

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-02-PLAN.md — 建立 PostgreSQL 测试环境、初始化启动器与 Playwright 安全链
- [x] 02-04-PLAN.md — 建立 Agent H5 feature 骨架、SSE 解析依赖与目录合同
- [x] 02-06-PLAN.md — 建立营养领域模型、Repository、Service 与确定性工具

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 02-07-PLAN.md — 建立 Agent 账本、Graph State、工具与持久化基础

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 02-05-PLAN.md — 建立无业务 seed 的迁移与首批冻结评测案例

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 02-08-PLAN.md — 建立 Checkpointer、FDC seed 与幂等初始化链

**Wave 6** *(blocked on Wave 5 completion)*

- [x] 02-09-PLAN.md — 建立完整 Agent API 哨兵合同与 OpenAPI 跨栈生成门

**Wave 7** *(blocked on Wave 6 completion)*

- [x] 02-10-PLAN.md — 交付登录用户文字餐食分析的首个真实纵向 GREEN

**Wave 8** *(blocked on Wave 7 completion)*

- [x] 02-11-PLAN.md — 交付集中追问、消歧、partial 与定向修正

**Wave 9** *(blocked on Wave 8 completion)*

- [x] 02-12-PLAN.md — 交付崩溃恢复、SSE 重连、有界自治与最终 24-case 数据集

**Wave 10** *(blocked on Wave 9 completion)*

- [x] 02-13-PLAN.md — 接入 DeepSeek、运行时依赖锁与 Phoenix 真实调用观测

**Wave 11** *(blocked on Wave 10 completion)*

- [x] 02-14-PLAN.md — 实现 D-18 自动保留、租约与 24h/7d/30d 清理

**Wave 12** *(blocked on Wave 11 completion)*

- [x] 02-15-PLAN.md — 交付用户删除入口与候选视觉基线

**Wave 13** *(blocked on Wave 12 completion)*

- [x] 02-16-PLAN.md — 生成 24-case 机器评测与专家、Promptfoo 发布合同

**Wave 14** *(blocked on Wave 13 completion)*

- [x] 02-17-PLAN.md — 执行专家、费用与视觉人工审批门

**Wave 15** *(blocked on Wave 14 completion)*

- [x] 02-18-PLAN.md — 已生成发布报告、晋升批准视觉并补齐教学文档；发布门禁为 FAIL，但 Phase 由用户手动接受完成

### Phase 3: 多模态餐食分析闭环

**Goal:** 用户上传餐食图片后，Qwen-VL 感知结果进入 Agent 图，并在必要追问后输出可信的多菜营养报告。
**Mode:** mvp
**Depends on:** Phase 2
**Requirements:** VIS-01, VIS-02, VIS-03, VIS-04, VIS-05, VIS-06, NUT-06, NUT-07, UI-01, QLT-01
**Success Criteria:**

1. 图片安全校验、元数据剥离、临时存储和删除链经过测试。
2. Qwen-VL Provider 返回经过 Pydantic 校验的多菜候选、置信度和份量线索。
3. 模糊菜名、目录外菜品与份量不足会触发追问；模型失败不会重复计费。
4. 结果页显示逐项营养与整餐汇总，并允许用户确认或修正。
5. 冻结样本报告识别、归一化与估重基线，不能只展示成功案例。

**Plans:** 5/5 plans complete

### Phase 4: 餐食记录与长期记忆

**Goal:** 用户的确认餐食与稳定偏好可以跨会话使用，同时保持权威数据、自然语言记忆和用户隔离。
**Mode:** mvp
**Depends on:** Phase 3
**Requirements:** MEM-01, MEM-02, MEM-03, MEM-04, MEM-05, MEM-06
**Success Criteria:**

1. 餐食记录、营养结果和确认状态保存到 PostgreSQL，支持用户级访问控制。
2. LangGraph Postgres Checkpointer 保存短期线程；Mem0 只保存白名单长期偏好。
3. pgvector 检索结合 `user_id` 和业务过滤，绝不跨用户召回。
4. 用户可查看、修改和删除记忆与餐食；删除链具有集成测试。

### Phase 5: 饮食规划子图

**Goal:** Agent 根据用户目标和偏好生成可校验、可交互调整的一日三餐方案。
**Mode:** mvp
**Depends on:** Phase 4
**Requirements:** PLN-01, PLN-02, PLN-03, PLN-04, PLN-05, PLN-06
**Plans:** 11/11 plans complete

Plans:
- [x] 05-01-PLAN.md — 冻结并测试 `target-policy.v1` 与首轮确认合同
- [x] 05-07-PLAN.md — 最小化、显式保存的个人资料持久化
- [x] 05-08-PLAN.md — 审核、许可明确且可重算的受控菜谱
- [x] 05-02-PLAN.md — 受限饮食规划子图与严格启动命令
- [x] 05-03-PLAN.md — H5 transient 首轮资料/偏好复核表单
- [x] 05-04-PLAN.md — 同线程的安全局部调整与记忆捕获
- [x] 05-05-PLAN.md — 个人资料详情路由、编辑与删除
- [x] 05-09-PLAN.md — H5 首次计划结果与安全状态呈现
- [x] 05-10-PLAN.md — H5 调整、放宽、上限和拒绝状态
- [x] 05-06-PLAN.md — 跨层回归、浏览器验收与中文教学文档
- [x] 05-11-PLAN.md — 修复单餐调整完成后的无障碍通知滚动劫持
**Success Criteria:**

1. 身体数据与目标经确定性公式生成每日能量和宏量营养约束。
2. 规划子图检索受控菜谱，生成餐单并用工具校验总量、比例、忌口和重复度。
3. 不合格方案仅在有限次数内重排，之后给出可解释失败结果。
4. 用户反馈“换清淡”“不吃某菜”后，保留其他约束并恢复图继续规划。
5. 输出明确声明非医疗建议，并拒绝高风险健康请求。

### Phase 6: 用户看板与后台管理

**Goal:** 用户看懂历史摄入趋势，管理员可以安全维护 Agent 所依赖的数据和配置。
**Mode:** mvp
**Depends on:** Phase 5
**Requirements:** UI-02, UI-03, ADM-01, ADM-02, ADM-03, ADM-04, ADM-05, ARC-08, EDU-02, EDU-03
**Plans:** 25/25 plans complete

Plans:

- [x] 06-01-PLAN.md — 冻结餐食统计时区事实
- [x] 06-02-PLAN.md — Dashboard 读 API 与完成计划投影
- [x] 06-03-PLAN.md — 可撤销的完成计划权威投影
- [x] 06-04-PLAN.md — Records 页看板接入与四 Tab 约束
- [x] 06-05-PLAN.md — Agent 流的安全业务阶段映射
- [x] 06-06-PLAN.md — H5 流式安全进度呈现
- [x] 06-07-PLAN.md — Facts-first 周复盘存储、缓存与复用
- [x] 06-08-PLAN.md — 版本化、去标识化周复盘评测输入
- [x] 06-09-PLAN.md — 周复盘 API 与 H5 呈现
- [x] 06-10-PLAN.md — 独立管理员 SPA 供应链与构建边界
- [x] 06-11-PLAN.md — Admin DB-RBAC 与审计查询
- [x] 06-12-PLAN.md — 营养目录草稿后端工作流
- [x] 06-13-PLAN.md — 营养目录草稿后台 UI
- [x] 06-14-PLAN.md — 目录审核、发布与失格事务协议
- [x] 06-15-PLAN.md — 目录审核、发布与失格后台 UI
- [x] 06-16-PLAN.md — 非密钥运行配置与准入后端
- [x] 06-17-PLAN.md — 后台认证壳与模型配置 UI
- [x] 06-18-PLAN.md — 运行指标与最小化查询 API
- [x] 06-19-PLAN.md — 后台 runs/audit UI
- [x] 06-20-PLAN.md — 跨栈真实路径回归与内置浏览器验收
- [x] 06-21-PLAN.md — Phase 6 文档与中文教学
- [x] 06-22-PLAN.md — 后台登录、会话壳与 overview
- [x] 06-23-PLAN.md — 受限周复盘 Graph、Provider adapter 与冻结评测
- [x] 06-24-PLAN.md — 管理员后台运行时入口、Provider tree 与样式
- [x] 06-25-PLAN.md — 剩余后台目录 README 与父索引
**Success Criteria:**

1. 用户可查看今日、本周摄入、历史餐食、趋势图与周复盘。
2. 独立 `admin-frontend/` 项目调用 `/api/v1/admin/*`；普通用户无法读取或修改后台数据，用户 H5 不包含后台页面。
3. 管理员可维护菜品、营养、来源、授权和版本，并查看完整审计差异。
4. 管理员可查看模型运行、失败节点、工具耗时和费用，不暴露原图、密钥或思维链。
5. README 包含最终架构图、状态图、时序图、调试方式和面试深挖题。

### Phase 7: 评测、安全与上线

**Goal:** 项目具备可重复的质量证据、安全边界、成本控制和一键演示环境。
**Mode:** mvp
**Depends on:** Phase 6
**Requirements:** QLT-03, QLT-04, QLT-05
**Success Criteria:**

1. CI 通过前后端 lint、类型、单元、真实 PostgreSQL 集成、API 合约和 Playwright E2E。
2. 冻结评测覆盖视觉识别、Agent 路由、营养校验、规划约束与记忆召回。
3. 越权、提示注入、危险图片、记忆泄漏、无限循环、费用上限和删除链测试通过。
4. Docker 环境按文档一键启动可演示系统，密钥与生产数据不进入镜像或 Git。
5. 简历项目描述中的每一项能力都能在代码、测试、截图或评测报告中找到证据。

## Progress

| Phase | Status | Plans | Completed |
|---|---|---|---|
| 1. 工程、身份与权限基座 | 14/14 | Completed | 2026-08-28 |
| 01.1. H5 UI 基座与现有页面迁移 | 10/10 | Complete   | 2026-08-28 |
| 2. 可追问的 Agent 核心 | 17/18 | In Progress|  |
| 3. 多模态餐食分析闭环 | 5/5 | Complete   | 2026-09-01 |
| 4. 餐食记录与长期记忆 | 7/7 | Complete    | 2026-09-01 |
| 5. 饮食规划子图 | 11/11 | Complete   | 2026-09-02 |
| 6. 用户看板与后台管理 | 25/25 | Complete   | 2026-09-04 |
| 7. 评测、安全与上线 | Pending | 0/TBD | - |
