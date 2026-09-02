# Dashboard Domain

## 职责

`dashboard/` 提供用户看板的严格读模型：聚合已确认餐食快照，并通过窄完成计划资格 Port 读取目标区间。它不读取规划资料、健康详情、Agent State 或 Provider 数据。

## 允许依赖

- 仅可依赖规划模块公开的、最小化资格 Port 和运行时 DTO；SQL 只读取本用户未软删且已有持久化 `consumed_local_date` 的餐食快照。
- 不得导入 `PlanningProfile` ORM，也不得通过 profile 推导目标。

## 文件索引

| 文件 | 职责 |
|---|---|
| `__init__.py` | Python 包标识。 |
| `ports.py` | 看板对完成计划资格的窄读取 Protocol。 |
| `schemas.py` | `extra=forbid` 的 overview/history 公共 DTO 与私有 cursor 位置。 |
| `repository.py` | tenant-filtered 的 SQL 聚合与 keyset 分页 adapter。 |
| `service.py` | overview/history 用例、目标 Port 注入和签名 opaque cursor。 |
| `api.py` | `/api/v1/dashboard` HTTP 路由与输入边界。 |
