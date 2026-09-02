# Dashboard Tests

## 职责

`tests/dashboard/` 验证看板只能消费可撤销的完成计划资格，不得从个人资料推测目标。

## 允许依赖

- 使用 fake planning Port 与公开 DTO；数据库行为由 `tests/integration/` 的真实 PostgreSQL 证据覆盖。
- 不得连接 SQLite、开发数据库或通过私有 ORM 查询替代看板 Port。

## 文件索引

| 文件 | 职责 |
|---|---|
| `__init__.py` | Python 测试包标识。 |
| `test_dashboard_target_port.py` | 窄目标资格 Port 的 unavailable、撤销和租户隔离契约。 |
| `test_dashboard_service.py` | fake repository 下 overview 七日槽位、目标 Port 和 history cursor 契约。 |
