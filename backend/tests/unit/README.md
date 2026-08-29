# Unit Tests

## 职责

`tests/unit/` 验证纯配置与业务行为，不启动 PostgreSQL、网络服务或 Docker。

## 允许依赖

- pytest、标准库和待测模块的公开接口。
- 可以使用 fake repository/provider；禁止连接真实数据库或外部 API。

## 文件索引

| 文件 | 职责 |
|---|---|
| `test_supply_chain.py` | 验证 Phase 2 新增依赖的版本化、fail-closed 供应链证据门 |
| `test_test_database_guards.py` | 证明测试数据库配置拒绝危险回退 |
| `test_runtime_foundation.py` | 验证版本化健康端点、Agent ledger/State 与 Graph→tool import 边界 |
| `test_nutrition.py` | 用内存 fake repository 锁定受控营养查询、Decimal 计算和确定性校验动作 |
| `test_eval_dataset.py` | 验证 Phase 2 冻结主路径语义、分类门与 append-only hash 链 |
