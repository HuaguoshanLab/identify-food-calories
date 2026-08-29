# Application Package

## 职责

`app/` 是 FastAPI 应用包。当前提供应用入口和核心运行配置；后续模块按 API、应用服务、领域、基础设施、Schema 与 Provider 边界扩展。

## 允许依赖

- 可以依赖 FastAPI、Pydantic 以及本包内更低层抽象。
- API 层只能调用 Application/Service，不能直接查询 SQLAlchemy Model。
- Agent 编排层只能通过受控工具调用领域服务。

## 文件索引

| 路径 | 职责 |
|---|---|
| `__init__.py` | Python 包标识 |
| `main.py` | FastAPI 应用工厂与健康端点 |
| `core/` | 配置、数据库等跨模块基础设施 |
| `auth/` | 认证 ORM、运行时 Schema、Service、Repository port 与 SQLAlchemy adapter |
| `admin/` | 后端 RBAC probe、数据库权威角色提升与审计模块 |
| `accounts/` | 密码恢复 Service、Repository port 与 HTTP 契约 |
| `notifications/` | 可替换邮件 Provider port 与本地 SMTP adapter |
| `providers/` | 外部模型 Provider 的独立 Port、DTO、Adapter 与测试替身 |
