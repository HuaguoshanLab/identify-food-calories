# Phase 4：餐食记录与长期记忆

## 设计理由

餐食只有在用户点击“确认并保存”后才成为记录。后端从完成 Agent 报告复制营养快照与版本，客户端不能提交热量。长期记忆以 PostgreSQL ledger 为授权真相；Mem0 只是可替换副本。

## 请求链路

浏览器通过 Bearer 请求 `/api/v1/meal-records` 或 `/api/v1/memories`。API 只处理 HTTP，Service 负责用户边界、幂等、时间与事务，Repository 在 SQL 内限定 `user_id` 和 active/deleted 状态，Model 由 Alembic 创建。

## 数据流

完成报告 → 显式确认 → `MealRecord`/items 快照。直接偏好 → ledger → 最小 canonical text 到 Mem0。删除先停用 ledger 并写 outbox，外部失败只会重试，绝不能使内容重新可见。检索把 preference、meal history、nutrition knowledge 分来源返回；数值仍只由 Nutrition Service 决定。

## 测试方法

Service 使用 fake repository/provider；API 使用 HTTP contract；集成测试使用真实 PostgreSQL、Alembic、pgvector 与 PostgreSQL Checkpointer。前端通过组件测试和真实浏览器走分析→保存→详情→编辑→删除路径。

## 常见错误

- 让前端提交 totals：这会把模型或客户端变成数值真相。
- 先按向量召回再在 Python 过滤用户：这会产生跨租户风险。
- 删除时只调用 Mem0：外部失败会让已删除偏好复活。
- 修改历史后重算目录：会悄悄改写已经确认的快照。
