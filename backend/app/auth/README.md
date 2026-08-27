# Auth Module

## 职责

`auth/` 定义用户、邮箱验证、数据库权威登录限流、登录会话和 refresh token 的权威数据边界。refresh 原文只在 HttpOnly Cookie 与短暂 Service 返回值中存在，数据库只保存 HMAC digest；消费行锁、successor 与 replay family revoke 在同一事务内完成。ORM 只描述持久化结构，Pydantic Schema 只描述运行时公开数据，Service 执行业务协议，Repository port 隔离应用服务与 SQLAlchemy。

## 允许依赖

- `models.py` 只依赖 SQLAlchemy；不得依赖 FastAPI 或公开 Schema。
- `schemas.py` 只依赖 Pydantic 和标准库；不得暴露密码摘要、验证码摘要或 refresh token 摘要。
- `ports.py` 可以引用 ORM 实体来定义应用层所需的持久化能力，不得引用 SQLAlchemy `Session`。
- `repository.py` 实现 port，可执行 SQLAlchemy query、`SELECT FOR UPDATE`、受 user_id 约束的撤销和 `flush()`；事务提交或回滚由 Service/调用方负责。
- `service.py` 只能依赖 port、Schema 和安全原语；不得导入 FastAPI 或直接查询数据库。
- `security.py` 封装 Argon2id、固定 HS256 access JWT 校验与 HMAC/CSPRNG 原语，不决定会话生命周期。
- `api.py` 只装配 port、管理 HttpOnly context/refresh Cookie、提取 Bearer，并映射稳定 HTTP envelope。

## 文件索引

| 文件 | 职责 |
|---|---|
| `__init__.py` | Auth Python 包标识 |
| `models.py` | 用户、验证码、opaque 登录失败 bucket、会话与 refresh token ORM 模型 |
| `schemas.py` | 注册、验证、登录 access 响应、用户和会话（含 `is_current`）的公开运行时合约 |
| `ports.py` | 应用服务依赖的 Repository Protocol |
| `repository.py` | 同步 SQLAlchemy Repository adapter、PostgreSQL 原子登录失败累计与 refresh family revoke |
| `security.py` | Argon2id 密码校验、session-bound access JWT、验证码/refresh CSPRNG 与 HMAC 摘要原语 |
| `service.py` | 注册验证码协议、HMAC 限流、登录、refresh rotation/replay revoke、会话管理和数据库权威身份读取 |
| `api.py` | 注册、登录、refresh/logout/session、Bearer `/users/me`、Cookie、CSRF Origin/Referer 和安全错误映射 |
