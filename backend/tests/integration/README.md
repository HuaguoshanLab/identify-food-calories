# Integration Tests

## 职责

`tests/integration/` 使用独立真实 PostgreSQL 验证 Alembic、Repository、约束和事务行为。测试必须能从空 schema 重建，不能用 ORM `create_all()` 或 SQLite 伪造迁移证据。

## 允许依赖

- pytest、SQLAlchemy、Alembic CLI 和后端公开 Repository/ORM 合约。
- 数据库连接只能来自通过 `validate_test_database_configuration` 校验的 `TEST_DATABASE_URL`。
- 测试可以 downgrade 隔离测试库，但不得连接或修改开发库。

## 文件索引

| 文件 | 职责 |
|---|---|
| `test_auth_migration.py` | 0001 空库往返、约束与 Repository flush-only 合约 |
