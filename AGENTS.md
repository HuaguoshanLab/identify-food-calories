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

历史规划资料：

- `.planning/PROJECT.md`
- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`

`.planning/` 自 2026-09-15 起冻结为历史规划与验证档案，可用于追溯旧决策，但不再作为强制工作流或当前进度状态机。当前事实以源码、测试、迁移、三个应用的 README/ARCHITECTURE 和本文件为准。

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

- 学习文档按功能组织，不按 Phase 新增阶段教程。只有新增用户能力、改变后端关键链路或原文已不再成立时，才更新 `docs/learning/`；局部重构、样式和机械修复不要制造教学文档工作。
- `docs/learning/README.md` 是统一入口，列出功能、简短介绍和可点击链接；新增、调整或移动功能文档时同步更新。
- 每篇先概述功能，再依次说明：核心能力（解决什么问题、实现什么效果）、业务背景（具体场景与设计理由）、整体执行流程（输入 → 处理 → 输出，可用简单流程图）、关键代码、难懂语法和验证方法。
- 讲解使用通俗中文，侧重 AI 与后端；专业术语先解释用途，前端只交代必要入口和交互。标明真实代码路径与关键函数，只贴简短主逻辑，删减代码必须标注，难懂语法单独解释。
- 以当前源码、测试与运行结果为依据，区分模型理解、工具计算、状态管理和业务存储；不得把规划目标或未接入的模型能力写成已实现，也不得虚构验证通过。
- `docs/after/`、`.planning/phases/` 和 `.planning/quick/` 是冻结的历史快照；除敏感信息、断链或会导致破坏性操作的严重错误外，不因当前实现变化而追溯重写。
- 验证方法说明对应测试、已执行结果、未验证部分与常见错误。
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
- 只有新建顶级应用或业务模块根目录时必须新增 `README.md`。`api/`、`components/`、`tests/`、`data/` 等约定俗成的子目录不强制单独 README；只有存在非显然安全边界、依赖例外或运维流程时才创建。
- README 只维护稳定职责和关键入口，不手工复制可由文件系统直接得到的逐文件索引。普通文件增删不要连锁修改多级 README。
- 数据库 schema 变更必须通过 Alembic migration。
- API、模型输出、工具参数和 Graph State 必须经过运行时校验。
- 模型、提示词、工具、目录和计算规则都有版本标识。
- 依赖密钥只能通过未提交的环境变量提供。
- 未经冻结评测和安全测试，不得在简历或 README 中声称达到某项指标。

## Change Workflow

后续开发不使用 GSD，不再新建或更新 GSD Phase、Quick、Plan、Summary、State 或其他工作流产物。现有产物只作历史查询。

变更按风险分级：

- **S 级**：文案、样式、明确小 Bug、机械重构和文档事实修正。直接确认范围、修改、运行定向验证。
- **M 级**：新页面、现有领域的新 API、筛选或普通后台操作。先写简短实施清单，再实现、测试和验收。
- **L 级**：认证、权限、数据库核心模型、图片安全、Agent 状态机、营养计算、Provider 费用或长期记忆隔离。在实现前明确威胁、失败模式、回滚和验证清单，但不依赖 GSD 文件。

文档影响遵循最小化原则：产品边界只改根 README；强制规则只改 AGENTS；代码落点或依赖方向只改 ARCHITECTURE；启动、构建、测试或配置只改对应应用 README；用户可见能力或关键后端链路变化才更新 `docs/learning/`。一项普通变更不应为了同步状态而修改五份文档。
