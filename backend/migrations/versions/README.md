# Migration Versions

## 职责

`migrations/versions/` 保存按 revision 排序、可审查且可往返的 PostgreSQL schema 变更。这里的脚本是生产 schema 的唯一创建入口。

## 允许依赖

- Alembic operations 与 SQLAlchemy schema primitives。
- PostgreSQL 支持的约束、外键和索引；禁止运行 ORM `create_all()`。
- downgrade 只能反向本 revision 的对象，不得删除无关数据结构。

## 文件索引

| 文件 | 职责 |
|---|---|
| `0001_auth_foundation.py` | 用户、验证码、会话与 refresh token 权威 schema |
| `0002_login_attempts.py` | HMAC-only 登录失败 bucket、窗口与封禁 schema |
