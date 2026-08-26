# Develop Guideline

## 基础交流规范

- 使用英语思考，但始终用中文向用户表达。
- 表达直接、清晰、零废话；技术判断不能为了友善而模糊。
- 批评只针对技术问题，不针对个人。

## Project

**中式外卖热量识别**

这是一个移动端优先、免登录的网站。用户拍照或上传中式外卖套餐图片后，系统分别识别多种菜品，估算克数与热量，展示整餐中心估值和合理区间，并允许用户修正菜名、克数或删除误识别项。

首版聚焦约 100 道高频中式外卖菜，不承诺覆盖所有食物或达到称重级、医疗级精度。

**Core Value:** 让普通用户在约 10 秒内得到一份可信且可修正的中式外卖整餐热量估算。

权威项目资料：

- `.planning/PROJECT.md`
- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `.planning/STATE.md`

## Approved Technology Stack

### Frontend

- React
- TypeScript
- Vite
- React Router
- TanStack Query
- Tailwind CSS
- Vitest、Testing Library、Playwright

### Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy 2
- Alembic
- PostgreSQL
- pytest

### Local Development

- `frontend/` 与 `backend/` 是独立项目。
- 使用 Docker Compose 启动 PostgreSQL 和必要的本地依赖。
- 前后端通过版本化 REST/OpenAPI 契约协作。

## Architecture Rules

- 不得改回 Next.js 单体；该方案已经被用户明确否决。
- 首版保持一个前端、一个 FastAPI 后端和一个 PostgreSQL 数据库。
- 未经真实延迟或可靠性数据证明，不引入微服务、消息队列或分布式任务系统。
- 视觉模型只输出受控菜品候选、克数和识别元数据；不得把模型生成的热量作为最终数据。
- 热量必须由受控菜品目录和营养数据确定性计算。
- PostgreSQL 保存菜品、别名、营养版本、匿名结构化分析结果和用户修正。
- 原始图片只用于当次分析，完成后删除，不长期保存。
- 前后端共享契约和计算规则时应保证单一事实来源，禁止复制后产生公式漂移。

## Product Constraints

- 菜名 Top-1 ≥ 85%，Top-3 ≥ 95%。
- 单项克数估算中位相对误差 ≤ 25%。
- 真实整餐热量落入合理区间的比例 ≥ 80%，且必须限制区间宽度。
- 90% 的有效请求应在目标移动网络下于 10 秒内返回。
- 用户从上传图片到理解结果不超过 3 次操作。
- 营养数据必须保留来源、授权和版本；授权未关闭时不得公开上线。

## Conventions

- 具体代码约定在 Phase 1 建立，并随实现更新本文件。
- 数据库 schema 变更必须通过 Alembic migration，不得手改生产结构。
- API 输入、输出和模型响应必须经过运行时校验。
- 不记录原图、base64、完整模型响应或其他不必要的敏感内容。
- 质量指标必须由冻结评测集生成，不以演示样本或主观观察代替。

## GSD Workflow Enforcement

修改文件前应通过合适的 GSD 工作流启动工作，使规划状态与代码保持同步：

- `$gsd-quick`：小型、独立修改
- `$gsd-debug`：调查和修复缺陷
- `$gsd-discuss-phase`：澄清阶段实现上下文
- `$gsd-plan-phase`：生成阶段计划
- `$gsd-execute-phase`：执行已批准的阶段计划
- `$gsd-verify-work`：用户验收和验证

除非用户明确要求绕过，否则不要脱离 GSD 工作流直接实施计划内功能。
