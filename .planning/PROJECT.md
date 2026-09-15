# 基于 LangGraph 的多模态饮食健康智能 Agent

> **历史快照：** 本文件保留截至 2026-09-15 的项目目标与决策。项目后续不再使用 GSD，本文件不再承担实时进度管理。

## What This Is

一个完整的多模态饮食健康 Agent 项目。用户可以上传一张餐食图片，Agent 通过视觉模型识别多道食物，在信息不足时主动追问菜名或份量，调用受控营养工具计算热量与三大营养素，校验异常结果，并把确认后的餐食记录保存到用户账户。

项目还提供饮食规划子图：用户输入身体数据、减脂或增肌目标、忌口和偏好后，Agent 生成并校验一日餐单，接受用户反馈后继续调整。短期会话状态由 LangGraph Checkpoint 保存，长期偏好由 Mem0 管理，权威业务数据始终保存在 PostgreSQL。

项目面向真实上线和求职展示：不仅演示模型调用，还完整呈现状态图、工具边界、Human-in-the-loop、失败恢复、身份认证、长期记忆、评测、安全、后台管理和 Docker 部署。

## Core Value

让用户通过图片或自然语言得到可追问、可校验、可追溯、能记住个人偏好的饮食分析与规划结果。

## Target Users

- 普通用户：拍照了解一餐的热量与宏量营养素。
- 减脂或增肌用户：获得受目标约束、可反复调整的餐单建议。
- 管理员：维护菜品、营养来源、数据版本、模型配置与审核状态。
- 学习者/面试官：可以从代码、测试和文档中追踪一条 Agent 请求的完整生命周期。

## Delivery Status

截至 2026-09-12，Phase 1–06.3 的 129 个计划均已有完成摘要。下列产品与架构能力已实现；“已实现”不等于“已生产发布”。Phase 2 的阶段实现已由用户手动接受，但其保留的 Spearman 发布报告仍为 `FAIL`；Phase 5 的代码与组件证据已完成，真实调整闭环仍有人工 E2E 复验项；Phase 7 的统一安全、CI 和上线门禁尚未开始。

- [x] 邮箱注册、验证码激活、登录、刷新、退出、密码重置和基于角色的权限控制。
- [x] LangGraph 主图包含餐食分析子图和饮食规划子图。
- [x] 图片识别失败、菜品模糊或份量缺失时，Agent 可以中断并追问用户，收到回复后从 Checkpoint 恢复。
- [x] 营养查询、热量计算和异常校验均为确定性工具，模型不得自由生成最终营养数值。
- [x] DeepSeek 用于文本推理和工具选择，Qwen-VL 用于视觉理解；两者通过 Provider 接口可替换。
- [x] PostgreSQL 保存用户、餐食、营养目录、Agent 运行和审计信息；pgvector 支持语义检索。
- [x] Mem0 只保存经过筛选的长期偏好，不替代业务数据库。
- [x] 用户可查看餐食历史、热量趋势和饮食复盘。
- [x] 管理员可维护菜品、营养来源、数据版本、模型配置与审核状态。
- [x] 已按功能维护 `docs/learning/` 中文学习文档及总目录。

## Out of Scope for v1

- 医疗诊断、疾病治疗和处方级营养建议。
- 让大模型自由决定或编造热量、宏量营养素和用户身体指标。
- 微服务、Kafka、Kubernetes 和分布式 Agent 集群；未有规模证据前保持模块化单体。
- 训练自有视觉基础模型；v1 使用模型 Provider 与冻结评测集比较供应商效果。
- 长期保存原始餐食图片；默认分析完成后删除。
- 用万相图像生成模型承担食物识别。万相可作为未来生成餐盘示意图的独立能力，但不进入识别链路。

## Approved Technology Stack

### Frontend

- React、TypeScript、Vite、React Router、TanStack Query
- Tailwind CSS、shadcn/ui Base UI、Lucide
- React Hook Form、Zod
- Vitest、Testing Library、MSW、Playwright

### Backend and Agent

- Python 3.12+、FastAPI、Pydantic
- LangGraph、PostgreSQL Checkpointer
- SQLAlchemy 2、Alembic、PostgreSQL、pgvector
- Mem0（长期偏好阶段接入）
- pytest、pytest-asyncio、HTTPX

### Model Providers

- `ReasoningModelProvider`：默认 DeepSeek，负责文本推理、规划和工具调用。
- `VisionModelProvider`：默认阿里云百炼 Qwen-VL，负责食物图片理解。
- Provider 必须支持测试替身、超时、重试、结构化输出校验、成本记录和替换供应商。

## Architecture Decisions

| Decision | Rationale |
|---|---|
| 一个主图、两个子图 | 共享状态与审计边界清晰，避免多 Agent 互相对话导致不可控循环 |
| 确定性工具是营养真相来源 | 降低幻觉并支持复现、测试与数据治理 |
| PostgreSQL 是权威数据源 | 用户、餐食、营养、运行记录和权限需要关系完整性与事务 |
| LangGraph Checkpoint 管短期状态 | 支持追问中断、恢复、重试和故障续跑 |
| Mem0 只管长期偏好 | 防止自然语言记忆覆盖权威业务事实 |
| DeepSeek + Qwen-VL 分工 | DeepSeek 当前适合文本/工具调用；Qwen-VL 负责图像理解 |
| 前后端分离模块化单体 | 满足后端学习与真实工程边界，同时避免过早微服务化 |
| 后台管理使用独立前端项目 | `admin-frontend/` 与 `frontend/`、`backend/` 同级，独立构建部署；共用 FastAPI `/api/v1/admin/*` 与后端 RBAC |
| 教学材料作为交付物 | 代码要能解释架构选择、请求链路、测试策略和失败模式 |
| 分层目录自文档化 | 根目录、`frontend/`、`backend/` 以及 Phase 6 创建的 `admin-frontend/` 分别维护 README 与 AGENTS；新增目录与职责/依赖/文件索引 README 同次提交 |

## Product and Safety Constraints

- 所有健康建议必须标明“普通饮食参考，不替代医疗建议”。
- Agent 图必须配置最大循环次数、最大工具调用次数、超时和费用上限。
- 图片上传执行 MIME、大小、像素、解码与元数据检查，处理完成后删除原图。
- 用户可查看、删除自己的餐食历史、Agent 会话和长期记忆。
- 管理员操作必须审计；普通用户不能访问后台 API。
- 模型输入输出、提示词、工具参数、数据版本和计算规则必须可追溯。
- 生产密钥只来自服务端环境变量，永不进入前端构建或 Git。

## Learning Contract

- 学习文档按功能组织，不按 Phase 新增阶段教程。每个后端阶段或功能变更完成后，更新 `docs/learning/` 中受影响的功能文档；只有出现新功能时才新增 `feature-<功能名>.md`。
- `docs/learning/README.md` 是统一入口，列出功能、简短介绍和可点击链接；新增、调整或移动功能文档时同步更新。
- 每篇先概述功能，再依次说明：核心能力（解决什么问题、实现什么效果）、业务背景（具体场景与设计理由）、整体执行流程（输入 → 处理 → 输出，可用简单流程图）、关键代码、难懂语法和验证方法。
- 讲解使用通俗中文，侧重 AI 与后端；专业术语先解释用途，前端只交代必要入口和交互。标明真实代码路径与关键函数，只贴简短主逻辑，删减代码必须标注，难懂语法单独解释。
- 以当前源码、测试与运行结果为依据，区分模型理解、工具计算、状态管理和业务存储；不得把规划目标或未接入的模型能力写成已实现，也不得虚构验证通过。
- `docs/after/` 仅存放原有阶段及补充专题资料，保留历史用途；新功能教学和后续维护统一进入 `docs/learning/`，不恢复旧阶段文件作为教学交付物。
- 代码注释只解释非显然设计与安全原因，不给每行翻译语法。
- Service 使用 fake repository 单测；Repository 使用真实 PostgreSQL 集成测试；Agent 图使用确定性模型替身测试路由与循环。
- README 提供架构图、时序图、运行命令、调试方法和面试深挖题。

## Evolution

该文档在每个阶段完成后更新。新增模型、记忆或后台能力必须保持 Provider、工具和权限边界，不得绕过确定性营养计算与审计。

---
*Last updated: 2026-09-15 after delivery-status reconciliation against source, plans, summaries, and verification reports*
