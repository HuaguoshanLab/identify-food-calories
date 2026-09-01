# Diet Planning Service Tests

## 职责

本目录使用内存 fake port 验证规划领域的版本化目标政策、资料确认、健康边界、闭合校验动作与 profile Service 事务边界。

## 允许依赖

- 仅可依赖 pytest、`app.planning` 的公开 DTO/Service 与内存 fake port。
- 禁止网络、真实数据库、FastAPI client、Provider 输出和真实健康资料。
- 集成级资料隔离、删除链与公开 API 证据属于后续独立测试。

## 文件索引

| 路径 | 职责 |
|---|---|
| `test_planning_service.py` | `target-policy.v1`、确认守卫、健康拒绝和目标/计划校验合同 |
| `test_planning_profile_service.py` | fake profile repository 下的显式保存、更新、软删除与 rollback 合同 |
