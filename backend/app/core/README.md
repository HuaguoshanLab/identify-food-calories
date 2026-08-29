# Core

## 职责

`core/` 管理跨模块运行时基础设施：环境配置验证、数据库 Engine/Session 生命周期以及后续安全原语。这里不放业务规则。

## 允许依赖

- Pydantic Settings 用于运行时输入与环境校验。
- SQLAlchemy 2 与 Psycopg 3 用于同步 PostgreSQL 连接。
- OpenTelemetry/Phoenix collector 仅用于 allowlist 后的运行指标，不启动本地 Phoenix UI。
- 不依赖 API 路由、应用服务、领域模块或具体业务 Model。

## 文件索引

| 文件 | 职责 |
|---|---|
| `__init__.py` | Core 包标识 |
| `config.py` | fail-closed 运行配置与测试数据库保护 |
| `database.py` | 应用 Engine、Session factory 与请求依赖 |
| `tracing.py` | fail-closed Phoenix/OTel collector 生命周期、HMAC scope 与属性 allowlist |
