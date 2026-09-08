# Learning

## 职责

`docs/learning/` 将可运行代码解释为可追踪的学习材料：从 React 交互到 FastAPI、服务事务、数据库与测试证据。

## 允许依赖

- 只链接仓库内真实存在的代码路径和可重复执行的命令。
- 解释安全设计理由与调试线索，不暴露可用于登录的值。
- 不把规划中的未来能力写成已经交付的事实。

## 文件索引

| 文件 | 职责 |
|---|---|
| `01-auth-and-backend-foundation.md` | Phase 1 认证、权限、事务和测试链教学指南 |
| `02-phase-1-code-walkthrough.md` | 从 React 页面追踪到 FastAPI、Service、Repository 与 PostgreSQL 的 Phase 1 代码导读 |
| `phase-02-agent-core.md` | Phase 2 文字餐食 Agent 的认证→API→ledger→LangGraph→确定性营养工具→PostgreSQL/SSE 链路、测试证据、失败发布门与常见错误。 |
| `phase-03-multimodal-meal-analysis.md` | Phase 3 图片安全、Qwen/Fake Vision Provider、图与确定性营养边界、删除链、冻结评测、浏览器证据和常见错误。 |
| `04-meal-records-and-long-term-memory.md` | Phase 4 显式餐食保存、Graph typed tool 直接偏好写入、ledger/outbox 删除竞争、来源分离检索、公开 Mailpit/CORS A/B 与浏览器验收教学。 |
| `05-diet-planning-adjustments.md` | Phase 5 规划同线程局部替换、显式记忆捕获、safe SSE 投影、RELAX 边界和三次恢复上限。 |
| `05-diet-planning-subgraph.md` | Phase 5 资料复核、确定性目标、受控三餐、独立 checkpoint、个人资料删除、Phase 4 偏好权威性、安全 SSE 与跨层测试教学。 |
| `phase-06-dashboard-read-api.md` | Phase 6 以餐食快照、窄完成计划投影、签名 cursor 和真实 PostgreSQL 证据构建 dashboard 读 API 的教学说明。 |
| `06-dashboard-admin.md` | Phase 6 统计窗口、受控周复盘、独立后台，以及目录表格与 CSV 原子导入/幂等/导出的教学说明。 |
| `06.1-recipe-candidate-pool.md` | 菜谱候选与营养目录的职责边界、CSV 导入/审计、候选轮换、可选加餐及跨层验证。 |
| `meal-weight-input.md` | 独立重量解析、单位转换、输入拒绝与同会话追问恢复的中文教学。 |
| `meal-slot-records.md` | 餐次确认、时间补录、历史兼容、请求链路与跨层测试教学。 |

| `daily-plan-archive.md` | 今日计划正式存档、事务与并发、历史版本、日期、删除与跨层验证。 |
