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
| `test_auth_migration.py` | auth migration head 空库重建、约束与 Repository flush-only 合约 |
| `test_auth_database_protocols.py` | 0001→0002 往返、约束/savepoint 与并发登录限流的真实 PostgreSQL 证据 |
| `test_refresh_concurrency.py` | 两个独立 PostgreSQL 事务的 refresh 单赢家、replay family revoke 与失败 rollback 证据 |
| `test_admin_audit.py` | 真实 PostgreSQL admin RBAC、角色审计和事务回滚证据 |
