# 基于 LangGraph 的多模态饮食健康智能 Agent

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

## Active Requirements

- [ ] 邮箱注册、登录、刷新、退出和基于角色的权限控制。
- [ ] LangGraph 主图包含餐食分析子图和饮食规划子图。
- [ ] 图片识别失败、菜品模糊或份量缺失时，Agent 可以中断并追问用户，收到回复后从 Checkpoint 恢复。
- [ ] 营养查询、热量计算和异常校验均为确定性工具，模型不得自由生成最终营养数值。
- [ ] DeepSeek 用于文本推理和工具选择，Qwen-VL 用于视觉理解；两者通过 Provider 接口可替换。
- [ ] PostgreSQL 保存用户、餐食、营养目录、Agent 运行和审计信息；pgvector 支持语义检索。
- [ ] Mem0 只保存经过筛选的长期偏好，不替代业务数据库。
- [ ] 用户可查看餐食历史、热量趋势和饮食复盘。
- [ ] 管理员可维护菜品、营养来源、数据版本、模型配置与审核状态。
- [ ] 每个后端阶段同步提供教学文档、数据流说明、测试示例和常见面试问题。

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

- Python 3.11+、FastAPI、Pydantic
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
| 后台管理复用同一 React 应用 | `/admin` 由 RBAC 保护，减少重复工程和权限漂移 |
| 教学材料作为交付物 | 代码要能解释架构选择、请求链路、测试策略和失败模式 |

## Product and Safety Constraints

- 所有健康建议必须标明“普通饮食参考，不替代医疗建议”。
- Agent 图必须配置最大循环次数、最大工具调用次数、超时和费用上限。
- 图片上传执行 MIME、大小、像素、解码与元数据检查，处理完成后删除原图。
- 用户可查看、删除自己的餐食历史、Agent 会话和长期记忆。
- 管理员操作必须审计；普通用户不能访问后台 API。
- 模型输入输出、提示词、工具参数、数据版本和计算规则必须可追溯。
- 生产密钥只来自服务端环境变量，永不进入前端构建或 Git。

## Learning Contract

- 每个后端阶段在 `docs/learning/` 增加一篇中文教学文档。
- 关键模块解释“为什么这样分层、请求如何流动、哪里容易写错”。
- 代码注释只解释非显然设计与安全原因，不给每行翻译语法。
- Service 使用 fake repository 单测；Repository 使用真实 PostgreSQL 集成测试；Agent 图使用确定性模型替身测试路由与循环。
- README 提供架构图、时序图、运行命令、调试方法和面试深挖题。

## Evolution

该文档在每个阶段完成后更新。新增模型、记忆或后台能力必须保持 Provider、工具和权限边界，不得绕过确定性营养计算与审计。

---
*Last updated: 2026-08-27 after Agent redesign*
