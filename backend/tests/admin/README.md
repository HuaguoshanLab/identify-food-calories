# Admin Tests

## 职责

`tests/admin/` 固定管理员服务层的数据库权威 RBAC、命令与通用不可变审计语义；它不替代真实 PostgreSQL 或 HTTP 合约测试。

## 允许依赖

- pytest、fake `AdminRepository` 与 `app.admin` 的公开 Service/Schema。
- 不连接 SQLite、开发数据库、真实邮件或模型 Provider。

## 文件索引

| 路径 | 职责 |
|---|---|
| `test_admin_rbac_audit_service.py` | 当前 active role 读取和命令审计原子性契约。 |
| `test_admin_audit_service.py` | 审计白名单、筛选和稳定 cursor 的 Service 契约。 |
| `test_catalog_csv.py` | CSV 编码/列校验、错误行号、边界、防公式执行、导入幂等与逐行审计、授权拒绝。 |
