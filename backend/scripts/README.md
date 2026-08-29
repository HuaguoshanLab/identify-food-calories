# Backend Scripts

## 职责

`scripts/` 保存受版本控制的后端运维入口。它们只编排已有的公开初始化接口，不承载 HTTP 路由、业务规则或 ORM 模型。

## 允许依赖

- 可调用 `app.core.config` 的 fail-closed 配置 guard、Alembic 与既有命令行入口。
- 真实 PostgreSQL 动作只允许使用 `validate_test_database_configuration()` 返回的隔离测试 URL。
- 禁止读取或改写 `DATABASE_URL` 以把开发库伪装成测试库，禁止把密码写进错误输出。

## 文件索引

| 路径 | 职责 |
|---|---|
| `run_initialized_app.py` | 固定执行安全 schema reset → Alembic → Checkpointer setup → seed apply → Uvicorn；任一步失败即停止。 |
| `setup_checkpointer.py` | 只对 guard 验证后的 `TEST_DATABASE_URL` 显式执行一次 AsyncPostgresSaver schema setup。 |
