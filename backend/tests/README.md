# Backend Tests

## 职责

`tests/` 提供后端配置、服务、Repository、migration 与 API 合约证据。任何需要数据库的测试都必须使用独立真实 PostgreSQL 测试库。

## 允许依赖

- pytest、HTTPX、FastAPI TestClient 与项目公开接口。
- Service 单测使用 fake repository；Repository/migration 测试使用 `postgres-test`。
- 禁止 SQLite、开发数据库回退，以及依赖测试执行顺序的共享状态。

## 文件索引

| 路径 | 职责 |
|---|---|
| `conftest.py` | 测试数据库保护、迁移与事务回滚 fixtures |
| `run_pg.py` | 只从显式 test env 文件载入变量、拒绝不安全测试目标后才启动 PostgreSQL child 的唯一 wrapper |
| `architecture/` | 顶级应用/业务模块 README 与架构边界的自动化合同；不检查逐子目录索引 |
| `unit/` | 不依赖外部服务的快速单元测试，包括 Records 公开 IANA 400/409 与 Dashboard current/history HTTP 安全契约；conftest 提供显式历史评测基线，不认证当前源码。 |
| `integration/` | 使用隔离真实 PostgreSQL 的 migration 与 Repository 合约测试；菜谱调整覆盖目录资格过滤、同菜品多菜谱与展示后禁用的两连接复核。 |
| `auth/` | 注册、验证码、登录与会话的 Service/API 安全协议测试 |
| `agent/` | Agent 安全流式阶段映射的契约测试；重量命令测试位于 `unit/test_weight_input.py`。 |
| `accounts/` | 密码恢复 Service/API、Mailpit 与 PostgreSQL 事务证据 |
| `records/` | 餐食快照 Service 的 fake repository 协议测试，包括统计时区确认的幂等、泛化冲突、竞争恢复与无写入拒绝。 |
| `memory/` | 长期偏好 ledger、Provider fake 与删除 outbox Service 测试 |
| `retrieval/` | 三来源上下文检索、偏好优先与安全 DTO Service 测试 |
| `planning/` | 规划目标政策、健康边界、餐单校验与最小 profile 的 fake-port Service 测试 |
| `dashboard/` | 看板 completion-target/`DashboardTimezoneReadPort`、preference-local current overview、已结束周复盘和 opaque cursor 的 fake-service 契约测试。 |
| `admin/` | 管理员 DB-RBAC、append-only 审计、catalog draft/revision/幂等与 CSV 批量导入导出的 fake-service 契约测试。 |
| `evals/` | 冻结、去标识化的 Agent 离线评测输入；只允许 fixture loader 与后续 Fake Provider 评测消费。 |
| `providers/` | Provider DTO、adapter 与 Fake 的运行时边界测试。 |

`integration/test_memory_direct_write_idempotency.py` 是 direct-memory provision worker 的真实 PostgreSQL 并发与恢复证据；必须通过 `run_pg.py` 运行，禁止用 SQLite 或开发库替代。

`integration/test_direct_memory_public_api.py` 必须在 `postgres-test` 与 Mailpit 已启动时通过 `run_pg.py` 运行；它固定使用 `SMTP_HOST=127.0.0.1`、`SMTP_PORT=1025` 与 `CORS_ORIGINS='["http://127.0.0.1:5178"]'`，不得用 token 伪造、依赖覆盖或数据库 seed 跳过公开认证链路。

- `planning/test_plan_archive.py` 与 `integration/test_diet_planning_agent_api.py`：正式日计划存档的 fake/真实 PostgreSQL 分层证据。
