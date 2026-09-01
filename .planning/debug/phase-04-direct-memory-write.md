# Phase 4：用户直接表达未写入长期记忆

## 症状

用户在分析页输入“我不吃辣”并完成分析后，“我的 → 饮食偏好与记忆”仍为空。

## 根因

分析图只检索既有个人上下文，从未在用户明确表达偏好时调用长期记忆的写入服务。`MemoryService.create_direct()` 已能创建带 `user_statement` 来源的本地账本记录和 Provider 记录，但其唯一调用点是手动 `POST /api/v1/memories`；Agent/Graph/Tool 链路没有写入工具。

## 证据

- `backend/app/agent/graph.py` 仅在处理前和目录解析后读取个人上下文。
- `backend/app/agent/tools.py` 的 `retrieve_personal_context()` 只调用 `PersonalContextService.retrieve()`。
- `backend/app/memory/api.py` 的 `create_direct_memory()` 是 `create_direct()` 的唯一应用调用点。
- `backend/tests/unit/test_agent_memory_context.py` 仅覆盖预置记忆的读取，不覆盖输入直接表达后的创建。

## 修复方向

在 Agent 的窄工具层新增经过规则约束的“用户直接表达写入”操作；Graph 只调用该工具，不能直接访问 ORM/Repository。明确表达的忌口、目标和稳定偏好可自动保存；模型推测仍必须走确认流程。写入必须绑定用户和 run 的幂等标识，并补 Agent、真实 PostgreSQL API 与浏览器端到端测试。
