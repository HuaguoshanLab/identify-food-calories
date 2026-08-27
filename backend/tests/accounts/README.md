# Account Recovery Tests

## 职责

`tests/accounts/` 证明密码恢复的 service、HTTP 契约、SMTP/Mailpit 投递和真实 PostgreSQL 并发/事务语义。

## 允许依赖

- Service 测试使用进程内 fake Port 和可控时钟。
- 集成测试只能使用 `conftest.py` 提供的隔离 PostgreSQL，禁止 SQLite。
- HTTP 测试可使用 FastAPI TestClient；SMTP 证据只指向本地 Mailpit。

## 文件索引

| 文件 | 职责 |
|---|---|
| `test_account_recovery.py` | 恢复协议、API、Mailpit、并发与 rollback 证据 |
