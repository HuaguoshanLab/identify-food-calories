# Phase 4：餐食记录与长期记忆

## 设计理由

餐食只有在用户点击“确认并保存”后才成为记录。后端从完成 Agent 报告复制营养快照与版本，客户端不能提交热量。长期记忆以 PostgreSQL ledger 为授权真相；Mem0 只是可替换副本。

## 请求链路

浏览器通过 Bearer 请求 `/api/v1/meal-records` 或 `/api/v1/memories`。API 只处理 HTTP，Service 负责用户边界、幂等、时间与事务，Repository 在 SQL 内限定 `user_id` 和 active/deleted 状态，Model 由 Alembic 创建。

明确的一人称偏好不经过模型猜测。文本分析的 fresh 输入先由 Graph 调用唯一的 typed `capture_explicit_preferences` 工具；Graph 只接收 `category + canonical_text` 的安全摘要，checkpoint 只保存“本 run 已尝试”的 marker。工具适配器才创建 `MemoryService`，后者以 user/run/category/canonical digest 生成稳定 request key，并在 PostgreSQL ledger 与 provisioning outbox 中先提交本地真相。生命周期 worker 再通过 `infer=False` 的 Provider 调用创建远端副本；超时只能按 request key resolve，不能盲目第二次 create。

模型解析、图片识别、历史回放和等待态恢复都不走这条写入路径。它们可以提出需要确认的内容，却不能把猜测升级为长期偏好。

## 数据流

完成报告 → 显式确认 → `MealRecord`/items 快照。直接偏好 → Graph typed tool → ledger/outbox → `infer=False` 的最小 canonical text 到 Mem0。删除先停用 ledger 并写 outbox，外部失败只会重试，绝不能使内容重新可见；即使删除发生在 provision claim、远端 create 或本地 bind 之间，删除 intent 也必须最终清理远端副本。检索把 preference、meal history、nutrition knowledge 分来源返回；数值仍只由 Nutrition Service 决定。

公开验收链路也必须保持同一信任边界：A/B 各自 `register → Mailpit 6 位验证码 → register/verify（同源 cookie + Origin）→ login`，只使用 login 响应的 Bearer token。测试固定 `SMTP_HOST=127.0.0.1`、`SMTP_PORT=1025`、`CORS_ORIGINS='["http://127.0.0.1:5178"]'`；B 对 A 的 GET/PATCH/DELETE 都返回不可用。A 删除后，再以公开 Agent API 分析，`context_references` 必须为空。

## 测试方法

Service 使用 fake repository/provider；API 使用 HTTP contract；集成测试使用真实 PostgreSQL、Alembic、pgvector、PostgreSQL Checkpointer 与 Mailpit。前端 Playwright 以及内置浏览器走“分析输入 `米饭 100 克，我不吃辣` → 我的 → 饮食偏好与记忆 → 编辑 → 确认删除 → 刷新空态”路径，并检查历史、320px 无横向溢出和页面不出现 provider ID/request key/分数。

## 常见错误

- 让前端提交 totals：这会把模型或客户端变成数值真相。
- 先按向量召回再在 Python 过滤用户：这会产生跨租户风险。
- 删除时只调用 Mem0：外部失败会让已删除偏好复活。
- 修改历史后重算目录：会悄悄改写已经确认的快照。
- Graph 直接 import ORM 或 Repository：会打破图只能经窄工具边界访问领域服务的架构。
- 用语义相似度做直接写入去重：不同表达会不可审计地合并；直接写入必须按稳定 request key 幂等。
- 在 API 测试中伪造 JWT、override principal 或 seed 用户：这跳过了 cookie、Origin、验证码和登录边界，不能证明产品链路。
- 删除后只查记忆 list：还必须通过公开 Agent 分析确认 retrieval context 已经为空。
