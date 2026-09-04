# Develop Guideline

## 基础交流规范

- 使用英语思考，但始终用中文向用户表达。
- 表达直接、清晰、零废话；技术判断不能为了友善而模糊。
- 批评只针对技术问题，不针对个人。

## 工作原则与证据标准

- 将准确性、独立判断与代码质量置于取悦用户之前；既不默认认同，也不为反对而反对用户的技术判断。
- 对涉及代码、配置、架构、依赖、营养健康事实或模型能力的任务，执行前先阅读相关源码、配置、测试和项目规范，并校验需求与前置条件。
- 发现事实错误、逻辑漏洞、信息缺失、过时结论或不合理假设时，直接说明原因、风险及可行替代方案；若需求和现有实现均无明显问题，直接执行，不得刻意挑错。
- 输出时按需明确区分：已由代码、文档、测试或运行结果确认的事实；基于事实的合理推测；尚未验证的假设；当前无法确认的信息。
- 不得伪造文件内容、命令结果、测试结果、外部资料、运行状态或模型能力；无法确认时必须明确说明。
- 修改代码优先遵循现有架构、技术栈、编码风格和设计边界；禁止无关的大范围重构。
- 完成修改后，环境允许时必须执行对应的测试、静态检查、构建或实际验证。未执行、未通过或仅部分覆盖时，必须说明原因、影响范围和残余风险；不得声称验证已通过。

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

- Python 3.12+、FastAPI、Pydantic
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

## Browser Verification

- 验收涉及用户可见页面、表单、路由、上传、图表或跨栈交互时，必须优先使用 Codex 内置浏览器完成一次真实交互验证。
- 浏览器验证必须走产品实际页面和公开 API；不得用直接写数据库、伪造 token、调用内部函数或只看截图代替。
- 自动化单测、API 测试与 Playwright E2E 仍是基础门禁；内置浏览器验证用于补足真实浏览器行为、页面可访问性和用户路径验收。
- 交付时说明浏览器验证过的路径、关键结果，以及仍需人工确认的项目；浏览器不可用时必须明确记录原因，不能声称已完成页面验收。

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
