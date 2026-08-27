# Auth Module

## 职责

`auth/` 定义用户、邮箱验证、登录会话和 refresh token 的权威数据边界。ORM 只描述持久化结构，Pydantic Schema 只描述运行时公开数据，Repository port 隔离应用服务与 SQLAlchemy。

## 允许依赖

- `models.py` 只依赖 SQLAlchemy；不得依赖 FastAPI 或公开 Schema。
- `schemas.py` 只依赖 Pydantic 和标准库；不得暴露密码摘要、验证码摘要或 refresh token 摘要。
- `ports.py` 可以引用 ORM 实体来定义应用层所需的持久化能力，不得引用 SQLAlchemy `Session`。
- `repository.py` 实现 port，可执行 SQLAlchemy query 和 `flush()`；事务提交或回滚由 Service/调用方负责。

## 文件索引

| 文件 | 职责 |
|---|---|
| `__init__.py` | Auth Python 包标识 |
| `models.py` | 用户、验证码、会话与 refresh token ORM 模型 |
| `schemas.py` | 注册、验证、用户和会话的公开运行时合约 |
| `ports.py` | 应用服务依赖的 Repository Protocol |
| `repository.py` | 同步 SQLAlchemy Repository adapter |
