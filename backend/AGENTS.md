# Backend Develop Guideline

本文件只细化根级 `AGENTS.md`，不能放宽其架构、安全、教学或目录文档规则。

## 架构

- 使用 Python 3.12+、FastAPI、Pydantic v2、SQLAlchemy 2 同步 Session 与 PostgreSQL。
- 保持 API → Application/Service → Repository → Model 依赖方向；路由只处理 HTTP 语义和响应映射。
- Repository 不决定密码规则、权限或 HTTP 状态码；Service 负责业务规则与多步骤事务边界。
- Schema、ORM Model、LangGraph State、Provider DTO 必须分离。
- `ARCHITECTURE.md` 是后端目录、新代码落点和跨模块依赖的强制合同。不得创建无所有者的全局 `services/`、`repositories/`、`models/`、`schemas/` 或 `utils/` 目录。
- 业务 API 默认隔离；受保护资源路由只从 `auth.api` 获取 `AuthenticatedPrincipal`，不得导入其他业务模块的 `api.py`。Agent 图只能通过 `agent/tools.py` 调用领域能力。

## 安全

- 配置必须 fail closed；禁止测试自动回退到开发库或 SQLite。
- 密钥、密码、令牌、原图/base64、完整模型思维链不得写入代码、日志或响应。
- 生产环境必须使用强随机密钥、Secure Cookie、显式 CORS 源和真实邮件 Provider。
- 数据库 schema 变化只能通过 Alembic migration。

## 测试与文档

- Service 使用 fake repository 单测；Repository 使用独立真实 PostgreSQL；API 使用 HTTPX 合约测试。
- 注释解释架构意图或安全原因，不逐行翻译代码。
- 新增目录时同步创建含“职责/允许依赖/文件索引”的 README；目录内容变化时更新其索引及直接父级索引。
