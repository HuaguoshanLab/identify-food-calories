# Phase 5：安全局部调整与有界恢复

## 设计理由

规划调整不是重新运行一个不受约束的模型任务。`DietPlanningGraph` 只接受经过闭合校验的反馈意图和早餐、午餐、晚餐三个槽位；图通过 `PlanningToolAdapter` 调用领域服务，不能读取 Repository、ORM 或 MemoryService。这样“午餐换清淡一些”只能影响午餐，不能意外改写其他餐次或已确认忌口。

## 请求链路与数据流

1. 用户向同一 `/api/v1/agent/threads/{thread_id}/input` 提交调整文字。
2. API 按最新 run 的 graph version 选择 planning checkpoint namespace，并把文本转成窄的 `feedback` 或 `slot` resume payload。
3. `DietPlanningGraph` 确定受影响槽位；歧义反馈只返回三餐 choice，非法 resume 不改变 checkpoint。
4. 明确偏好只通过 `capture_explicit_preferences` typed tool 写入 Phase 4 的 owner-scoped、delete-aware ledger。state 保存 SHA-256 replay marker，不保存原始反馈、ledger ID 或 Provider 内容。
5. `SessionNutritionToolAdapter` 让 `PlanningService` 排除旧菜谱后选择审核候选，只替换目标槽位，并保留其余 immutable slots。
6. 图把安全的 changed slot、范围状态，以及必要时 energy/macro 放宽详情投影到 report/SSE；排除项和 health boundary 不在可放宽集合中。

## 有界性与安全投影

- `replan_count` 持久化在 planning state，最多为 3；第四个命令直接返回 `LIMIT_REACHED`，不触发 composition。
- 只有显式、allowlisted 的偏好文本可被 capture；重放命中 marker 时不会重复写入。
- SSE 只回放业务摘要，绝不含原始反馈、provider/tool 输出、ledger ID、候选排序或推理内容。

## 测试方法

```bash
cd backend
uv run pytest tests/unit/test_diet_planning_graph.py tests/integration/test_diet_planning_agent_api.py -q
uv run ruff check app/agent app/planning/service.py tests/unit/test_diet_planning_graph.py tests/integration/test_diet_planning_agent_api.py
```

单元测试使用 fake planning adapter 断言单槽 identity、closed choice、replay marker、RELAX safe projection 与第三次上限。集成测试使用真实 PostgreSQL、公开认证 API 和 SSE，验证 owner-scoped same-thread 调整与 memory ledger 写入。

## 常见错误

- 在 graph 中直接查询菜谱或 memory ledger：破坏 Agent → tools → service 边界。
- 把原始 feedback 或 ledger/provider ID 写进 state 或 SSE：会泄露用户数据和内部实现。
- 用全餐重新组合伪装“局部替换”：会违反未受影响餐次保持不变的合同。
- 将忌口、明确排除或健康安全规则纳入 RELAX：这是安全漏洞，不是体验优化。
