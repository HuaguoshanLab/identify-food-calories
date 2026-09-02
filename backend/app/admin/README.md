# Admin Authorization Package

## 职责

`app/admin/` 提供仅后端可见的管理员 RBAC probe、数据库权威角色检查、显式 CLI 提升流程和管理员角色变更审计。它不包含后台页面、用户 H5 路由或前端权限判断。

## 允许依赖

- API 层只能处理 Bearer HTTP 语义，并调用认证与 admin Service。
- Service 只能通过 `AdminRepository` 读取用户、加锁和写入审计；它不依赖 FastAPI 或直接操作 Session。
- Repository 可以依赖 SQLAlchemy ORM；角色值以 `app.auth.models.UserRole` 为唯一枚举来源。

## 文件索引

| 路径 | 职责 |
|---|---|
| `__init__.py` | Python 包标识 |
| `models.py` | 角色提升与通用 append-only 审计 ORM 映射、数据库约束镜像 |
| `schemas.py` | probe 与最小审计 timeline 运行时契约 |
| `ports.py` | Service 所需持久化能力协议 |
| `repository.py` | SQLAlchemy 查询、锁、flush-only 审计与 keyset adapter |
| `service.py` | 数据库权威 RBAC、原子角色提升、命令审计与 cursor 投影策略 |
| `api.py` | `/api/v1/admin/probe` 与只读 `/audit` HTTP 翻译 |
| `cli.py` | 显式管理员 bootstrap/promote 命令 |
