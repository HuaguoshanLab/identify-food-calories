# Integration Tests

## 职责

`tests/integration/` 使用独立真实 PostgreSQL 验证 Alembic、Repository、约束和事务行为。测试必须能从空 schema 重建，不能用 ORM `create_all()` 或 SQLite 伪造迁移证据。

## 允许依赖

- pytest、SQLAlchemy、Alembic CLI 和后端公开 Repository/ORM 合约。
- 数据库连接只能来自通过 `validate_test_database_configuration` 校验的 `TEST_DATABASE_URL`。
- 测试可以 downgrade 隔离测试库，但不得连接或修改开发库。

## 文件索引

- `test_catalog_draft_repository.py`：草稿审计持久化、LIKE 字面筛选、稳定分页与 CSV 第二行失败时整批回滚。

| 文件 | 职责 |
|---|---|
| `test_auth_migration.py` | auth migration head 空库重建、约束与 Repository flush-only 合约 |
| `test_agent_migration.py` | 0003↔0006 往返、Agent/Nutrition metadata（含 catalog hash、图片与视觉调用 metadata）逐表约束与零 seed 的真实 PostgreSQL 证据 |
| `test_auth_database_protocols.py` | 0001→0002 往返、约束/savepoint 与并发登录限流的真实 PostgreSQL 证据 |
| `test_refresh_concurrency.py` | 两个独立 PostgreSQL 事务的 refresh 单赢家、replay family revoke 与失败 rollback 证据 |
| `test_admin_audit.py` | 真实 PostgreSQL admin RBAC、账号列表、角色审计、降权即时生效但保留用户会话、受限本地固定管理员初始化及事务回滚证据 |
| `test_agent_bootstrap.py` | 真实 PostgreSQL 的 migration → checkpoint setup → FDC seed 幂等初始化链 |
| `test_agent_vertical.py` | 真实 PostgreSQL 的认证 Agent 纵向链、SSE、安全重量拒绝不改变快照、同线程 checkpoint 恢复与单位化定向修正证据。 |
| `test_agent_checkpoint.py` | 预算在下一次调用前终止、瞬时 Provider 仅重试一次及恢复边界的回归证据。 |
| `test_agent_retention.py` | FastAPI 生命周期中的 PostgreSQL retention lease、24h 用户删除、7d checkpoint/SSE 与 30d 最小审计的精确边界和跨租户证明。 |
| `test_meal_records.py` | 真实 Agent 完成报告到餐食保存、时间修改、隔离与删除的竖向证据。 |
| `test_record_local_time_attribution.py` | 真实 PostgreSQL 证明用户确认的统计时区仅回填本人历史餐食的本地日。 |
| `test_memory_deletion_chain.py` | 真实 PostgreSQL 证明删除后立即不可检索，外部清理失败仅进入安全重试。 |
| `test_memory_direct_write_idempotency.py` | 真实 PostgreSQL 证明直接偏好 capture 并发单例、outcome-unknown 重启仅按 request key resolve，及删除/用户隔离。 |
| `test_direct_memory_public_api.py` | 仅经公开注册、Mailpit 验证、同源 Cookie 与登录 Bearer token 验证 Agent 直接忌口、A/B memory API 隔离、编辑/删除及删除后 context 为空。 |
| `test_retrieval_isolation.py` | 真实 pgvector metadata 检索的 tenant、active/deleted 与受控知识版本过滤证据。 |
| `test_planning_profile_api.py` | 仅经公开认证链验证最小化规划资料的 owner CRUD、422 闭合输入、软删除与删除后不可读取。 |
| `test_planning_completion_projection.py` | 真实 PostgreSQL 证明完成计划投影的 owner/run/thread 外键与撤销约束。 |
| `test_dashboard_repository.py` | 真实 PostgreSQL 证明本地日聚合、软删/租户过滤及三元 keyset cursor 不漏不重。 |
| `test_dashboard_overview_projection.py` | 真实 PostgreSQL 快照与窄完成计划资格 Port 组合的 overview 降级证据。 |
| `test_weekly_review_cache_repository.py` | 周复盘 cache key 的最小化持久化契约。 |
| `test_hybrid_food_search.py` | 真实 PostgreSQL 检查 schema、`pg_trgm`/cosine 三通道、当前资格与确认 reread、1024 维隔离 vector space、受控关系撤销、有限 job，以及 build/activation hash evidence。 |
| `test_catalog_embedding_jobs.py` | 发布时的 canonical/alias × active vector space job 入队、仅安全字段的聚合状态，以及 publication 级失败重试的并发幂等证据。 |

- `test_diet_planning_agent_api.py`：补充正式餐单公开读删、版本、运行清理、注入故障回滚及并发连接验证。
