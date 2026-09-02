# Migrations

## 职责

`migrations/` 保存 Alembic 迁移脚本，使空 PostgreSQL 数据库可以可追溯地升级到当前 schema。本计划只验证 pgvector extension，不创建业务向量表。

## 允许依赖

- Alembic、SQLAlchemy metadata 和 `app.core.config` 的受控数据库 URL。
- 不允许通过 `create_all()` 替代生产 schema 迁移。
- migration 必须人工审查升级、约束、索引及可接受的降级行为。

## 文件索引

| 路径 | 职责 |
|---|---|
| `env.py` | 受 APP_ENV/TEST_DATABASE_URL 保护的在线迁移环境 |
| `script.py.mako` | 新 revision 的标准脚本模板 |
| `versions/` | 已审查的有序 schema revision（当前至 `0013` dashboard local-date attribution） |
