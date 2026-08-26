# Phase 1: 受控数据与可运行薄切片 - Context

**Gathered:** 2026-08-26
**Status:** Ready for planning

<domain>
## Phase Boundary

本阶段交付第一个真实可运行的垂直薄切片：开发者可以分别启动 React/Vite 前端、FastAPI 后端和 Docker 中的 PostgreSQL；用户从受控目录中选择一道菜、确认或修改克数、点击按钮，并得到由数据库营养数据确定性计算的热量。图片上传与识别、误差区间、结果修正闭环、匿名分析记录和生产发布保护不属于本阶段。

</domain>

<decisions>
## Implementation Decisions

### 首个可运行流程

- **D-01:** 第一条用户路径固定为“选择一道菜 → 输入克数 → 点击计算热量 → 查看结果”，本阶段不支持手动组合多道菜。
- **D-02:** 菜品选择使用可搜索下拉框，支持中文标准菜名和别名匹配；不能使用约 100 项的普通原生下拉框。
- **D-03:** 选择菜品后自动填入该菜的常见外卖份量，用户可以精确修改克数。
- **D-04:** 克数变化不会自动请求后端；用户点击明确的“计算热量”按钮后才调用 FastAPI。
- **D-05:** 第一阶段前端只突出菜名、克数和计算后的热量，不显示误差区间或营养数据来源。
- **D-06:** 营养来源和授权信息必须保存在数据库中并由 API 返回，但前端第一阶段不展示。

### 首批菜品数据

- **D-07:** 先用 15 道代表菜验证 schema、迁移、别名搜索、种子导入和热量计算；数据结构稳定后在本阶段结束前扩充到约 100 道。
- **D-08:** 首批 15 道为：白米饭、蛋炒饭、炒面、番茄炒蛋、宫保鸡丁、鱼香肉丝、青椒肉丝、红烧肉、回锅肉、麻婆豆腐、土豆烧牛肉、清炒时蔬、酸辣土豆丝、红烧茄子、炸鸡排。
- **D-09:** 每道菜第一阶段只保留一套标准外卖配方；数据库设计可为未来多配方预留关系，但本阶段不实现多配方行为。
- **D-10:** 每道菜至少保存稳定 `dishId`、标准菜名、别名、每 100g 热量、常见份量克数、来源、授权状态和数据版本。
- **D-11:** 允许明确标记为 `demo_only` 的研究或人工整理值用于本地开发学习；只有 `production_approved` 数据可以进入公开生产环境。
- **D-12:** 应建立可自动验证的生产阻断，不能只靠文档提醒避免 `demo_only` 数据上线。

### 后端学习深度

- **D-13:** API 从第一阶段使用 `/api/v1` 路径前缀，并保留 FastAPI `/docs` 和 `/openapi.json`。
- **D-14:** 后端严格拆分 API、Service、Repository、Schema 和 Model：API 处理 HTTP，Service 执行业务规则，Repository 负责持久化，Schema 定义 Pydantic 契约，Model 定义 SQLAlchemy 映射。
- **D-15:** API 不得直接调用 SQLAlchemy 查询；Pydantic Schema 与 SQLAlchemy Model 必须分离，公共 API 不能直接暴露 ORM Model。
- **D-16:** Service 单元测试使用假的 Repository，不连接数据库。
- **D-17:** Repository 集成测试连接独立 PostgreSQL 测试库，不用 SQLite 替代 PostgreSQL。
- **D-18:** API 测试验证状态码、请求/响应 Schema 和结构化错误响应。
- **D-19:** 根目录 `README.md` 说明项目结构和完整启动顺序；`backend/README.md` 说明分层职责、依赖方向、环境变量、迁移和测试命令。
- **D-20:** 文档包含 FastAPI 自动文档入口、查询菜品/计算热量/错误响应的 `curl` 示例，以及一张简洁数据流图；不编写大段理论教程。

### 本地启动体验

- **D-21:** Docker Compose 默认只启动 PostgreSQL，不把 pgAdmin 或其他数据库 GUI 作为项目依赖。
- **D-22:** 文档可以使用 DBeaver Community 作为图形化数据库查看示例，但开发者也可使用 DataGrip、VS Code PostgreSQL 扩展或 `psql`。
- **D-23:** 前端和后端分别维护 `.env.example`；真实 `.env` 必须被 Git 忽略，前端环境只暴露允许公开的配置。
- **D-24:** Alembic migration 和菜品种子导入使用独立、显式命令；FastAPI 启动时不得自动建表、迁移或灌数据。
- **D-25:** 本地默认端口固定为 Vite `5173`、FastAPI `8000`、PostgreSQL `5432`。
- **D-26:** 开发环境 CORS 只允许 `http://localhost:5173`，不得使用 `*`。
- **D-27:** 前端与后端分别在独立终端启动，日志分开查看；不要求一条命令隐藏所有启动步骤。

### the agent's Discretion

- 在已批准分层内确定具体 Python 包路径、类名、函数名和依赖注入写法。
- 确定数据库表名、字段名、索引和约束，只要完整支持上述数据与授权规则。
- 确定热量显示的合理取整方式、表单校验细节和第一阶段的视觉样式。
- 选择符合批准技术栈的包管理器、lint/format 工具和测试目录结构，并在 README 中给出明确命令。

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product and scope

- `.planning/PROJECT.md` — 产品定位、核心价值、约束及已批准技术栈。
- `.planning/REQUIREMENTS.md` — Phase 1 映射的 ARCH-01..06、DATA-01、DATA-04 和 CAL-01 正式需求。
- `.planning/ROADMAP.md` — Phase 1 边界、依赖和成功标准。
- `.planning/STATE.md` — 当前阶段、项目阻断项和会话状态。

### Repository guidance

- `AGENTS.md` — 强制技术栈、架构规则、开发规范和 GSD 工作流要求。

No external specs or ADRs were referenced during this discussion.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- None — 当前仓库是 greenfield，仅有规划文件，没有可复用前端、后端或数据库代码。

### Established Patterns

- 规划层已锁定 `frontend/` React/Vite、`backend/` FastAPI 和 PostgreSQL 的前后端分离结构。
- `AGENTS.md` 已禁止改回 Next.js 单体、引入微服务或让模型生成最终热量。

### Integration Points

- 新代码从仓库根目录创建 `frontend/`、`backend/`、Docker Compose 和根 README。
- 前端通过 `/api/v1` OpenAPI 契约连接 FastAPI；FastAPI 通过 Repository 访问 PostgreSQL。

</code_context>

<specifics>
## Specific Ideas

- 用户希望通过项目系统学习 FastAPI、数据库关系建模、Alembic migration、分层依赖、测试和 API 文档，因此代码可读性与边界清晰度优先于最少文件数量。
- 第一条完整示例应让用户搜索“宫保”等别名片段、选择菜品、看到默认常见份量、修改克数并点击“计算热量”。
- `demo_only` 与 `production_approved` 必须是可执行的发布边界，而不是注释或约定。

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 1-受控数据与可运行薄切片*
*Context gathered: 2026-08-26*
