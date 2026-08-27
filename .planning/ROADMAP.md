# Roadmap: 多模态饮食健康智能 Agent

## Overview

路线图按可演示的垂直切片推进。先建立身份、权限和正式工程骨架，再交付一个文字可追问的 LangGraph Agent，随后接入 Qwen-VL 图片感知、长期记忆、饮食规划、用户看板与后台管理，最后通过评测、安全和部署门禁形成可上线、可写简历的完整项目。

DeepSeek 与 Qwen-VL 通过 Provider 分工；营养事实始终来自确定性工具和受控数据库。LangGraph Checkpoint 管理短期执行状态，Mem0 管理跨会话偏好，PostgreSQL 保存权威业务记录。

## Phases

- [ ] **Phase 1: 工程、身份与权限基座** — 建立 React/FastAPI/PostgreSQL、注册登录、会话轮换、RBAC 和教学规范。
- [ ] **Phase 2: 可追问的 Agent 核心** — 建立 LangGraph 主图、餐食分析子图、确定性营养工具、Checkpoint 和有界循环。
- [ ] **Phase 3: 多模态餐食分析闭环** — 接入安全图片上传与 Qwen-VL，多菜识别、份量追问、校验和最终报告。
- [ ] **Phase 4: 餐食记录与长期记忆** — 保存餐食历史，接入 Mem0 与 pgvector，并提供记忆查看和删除。
- [ ] **Phase 5: 饮食规划子图** — 根据身体目标生成并校验餐单，支持用户反馈后的 Human-in-the-loop 调整。
- [ ] **Phase 6: 用户看板与后台管理** — 完成趋势分析、周复盘、营养目录管理、模型配置、运行审计与 RBAC 管理界面。
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

### Phase 2: 可追问的 Agent 核心

**Goal:** 用户通过文字描述一餐时，Agent 能使用确定性工具补齐信息、计算营养并在中断后恢复。
**Mode:** mvp
**Depends on:** Phase 1
**Requirements:** AGT-01, AGT-02, AGT-03, AGT-04, AGT-05, AGT-06, AGT-07, NUT-01, NUT-02, NUT-03, NUT-04, NUT-05, ARC-05, ARC-06, QLT-02
**Success Criteria:**

1. LangGraph State、节点和条件边有显式类型，主图可路由到餐食分析子图。
2. 缺少菜名或克数时通过 interrupt 追问；相同 thread 恢复后继续执行，不重复已完成工具。
3. 菜品查询、营养计算和异常校验均调用领域工具，模型不能直接写最终营养数值。
4. 最大循环、工具调用、超时和错误终止均有确定性状态图测试。
5. DeepSeek Provider 与 Fake Provider 可互换；测试和本地演示不强制消耗付费 API。

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
| 1. 工程、身份与权限基座 | 3/14 | In Progress|  |
| 2. 可追问的 Agent 核心 | Pending | 0/TBD | - |
| 3. 多模态餐食分析闭环 | Pending | 0/TBD | - |
| 4. 餐食记录与长期记忆 | Pending | 0/TBD | - |
| 5. 饮食规划子图 | Pending | 0/TBD | - |
| 6. 用户看板与后台管理 | Pending | 0/TBD | - |
| 7. 评测、安全与上线 | Pending | 0/TBD | - |
