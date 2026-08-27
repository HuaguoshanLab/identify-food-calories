# Develop Guideline

## 基础交流规范

- 使用英语思考，但始终用中文向用户表达。
- 表达直接、清晰、零废话；技术判断不能为了友善而模糊。
- 批评只针对技术问题，不针对个人。

## Project

**基于 LangGraph 的多模态饮食健康智能 Agent**

用户通过图片或文字描述饮食，Agent 在信息不足时主动追问，调用受控营养工具计算并校验结果，保存用户确认的餐食；饮食规划子图结合目标和长期偏好生成可调整餐单。项目包含登录注册、长期记忆、用户看板、后台管理、评测和 Docker 部署。

**Core Value:** 让用户获得可追问、可校验、可追溯、能记住个人偏好的饮食分析与规划结果。

权威资料：

- `.planning/PROJECT.md`
- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`

## Approved Stack

### Frontend

- React、TypeScript、Vite、React Router、TanStack Query
- Tailwind CSS、shadcn/ui Base UI、React Hook Form、Zod
- Vitest、Testing Library、MSW、Playwright

### Backend and Agent

- Python 3.11+、FastAPI、Pydantic
- LangGraph + PostgreSQL Checkpointer
- SQLAlchemy 2、Alembic、PostgreSQL、pgvector
- Mem0（仅长期偏好，不是权威业务存储）
- pytest、HTTPX

### Models

- DeepSeek：文本推理、规划和工具选择。
- Qwen-VL：食物图片理解。
- 万相是图像生成/编辑模型，不用于食物识别。
- 所有模型必须通过 Provider 接口调用，并有 Fake Provider 供测试。

## Architecture Rules

- 保持独立 `frontend/` 和 `backend/`；Phase 6 新增同级独立 `admin-frontend/`；不得改为 Next.js 单体，也不得把后台页面塞进用户 H5。
- v1 使用模块化单体，不引入微服务、Kafka 或 Kubernetes。
- LangGraph 使用一个主图和两个子图：餐食分析、饮食规划。
- Agent 编排层只能通过工具调用领域服务，不得直接查询数据库。
- 后端依赖方向：API → Application/Service → Repository → Model；Schema、LangGraph State 和 Provider DTO 必须分离。
- 营养查询、热量计算、目标计算和结果校验必须是确定性工具；模型不得成为数值真相来源。
- PostgreSQL 保存权威业务数据；Checkpoint 保存短期图状态；Mem0 保存白名单长期偏好。
- 每个图必须有最大循环、最大工具调用、超时、成本和终止条件。
- 后台 API 必须在后端执行 RBAC，不能只靠前端隐藏菜单。
- 不记录原图、base64、密钥、完整模型思维链或不必要的敏感信息。

## Authentication and Security

- 邮箱密码认证；密码强哈希。
- 短期 access token 与 HttpOnly refresh token 分离；刷新令牌轮换、哈希保存、可撤销。
- 角色至少包含 `user`、`admin`；管理员操作写入审计日志。
- 图片必须通过 MIME、大小、像素和真实解码检查，剥离元数据并按策略删除。
- 所有健康建议是普通饮食参考，不提供医疗诊断或治疗。

## Teaching Contract

- 每个后端阶段在 `docs/learning/` 写中文教学文档。
- 解释设计理由、请求链路、数据流、测试方法和常见错误。
- 代码注释解释“为什么”，不要逐行翻译“做什么”。
- Service 使用 fake repository 单测；Repository 使用真实 PostgreSQL 集成测试；Agent 图使用 Fake Provider 测试路由、interrupt/resume 与循环终止。
- README 最终必须包含架构图、状态图、时序图、启动/调试命令和面试深挖题。

## Conventions

- 仓库根目录、`frontend/` 与 `backend/` 必须各自维护 `README.md` 和 `AGENTS.md`；Phase 6 创建 `admin-frontend/` 时同样适用；子级 `AGENTS.md` 只能细化、不能放宽上级规则。
- 新增任何目录时，必须在同一次提交新增该目录的 `README.md`，写明目录职责、允许依赖和文件索引；目录文件变化时同步更新索引。
- 数据库 schema 变更必须通过 Alembic migration。
- API、模型输出、工具参数和 Graph State 必须经过运行时校验。
- 模型、提示词、工具、目录和计算规则都有版本标识。
- 依赖密钥只能通过未提交的环境变量提供。
- 未经冻结评测和安全测试，不得在简历或 README 中声称达到某项指标。

## GSD Workflow Enforcement

- `$gsd-discuss-phase`：阶段上下文
- `$gsd-plan-phase`：可执行计划
- `$gsd-execute-phase`：执行已验证计划
- `$gsd-verify-work`：人工验收
- `$gsd-secure-phase`：威胁缓解审计
- `$gsd-eval-review`：Agent 评测覆盖审计

除非用户明确要求绕过，否则不要脱离 GSD 工作流实施计划内功能。
