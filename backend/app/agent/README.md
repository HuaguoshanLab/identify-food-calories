# Agent Runtime

## 职责

`agent/` 保存 Agent 的权威业务 ledger、JSON-safe Graph State、领域工具适配器、公开 HTTP 合同和图运行时合同。业务表负责用户归属、幂等、事件和租约；LangGraph Checkpointer 只保存短期 State，不能替代 ledger。

## 允许依赖

- 可依赖 Pydantic、LangGraph 类型、已批准的 Provider Port，以及下游领域 Service 的窄 Port。
- `graph.py` 只能依赖 `tools.py` 的 adapter 和 State；禁止导入 SQLAlchemy、`models.py` 或 `repository.py`。
- `service.py` 只依赖自己的 ledger Port 和 planning 的 completion-writer Port；Repository 只依赖 SQLAlchemy Model 并且只能 flush，不能 commit 或决定 HTTP/Graph 语义。

## 文件索引

| 文件 | 职责 |
|---|---|
| `__init__.py` | Python 包标识 |
| `models.py` | thread/run/event/invocation/lease/deletion-intent，以及图片/视觉调用最小 metadata 的权威 ledger ORM |
| `ports.py` | Agent Service 的持久化 Protocol |
| `repository.py` | flush-only SQLAlchemy Agent ledger adapter |
| `service.py` | 所有权、命令幂等、事件、调用、图片/视觉 invocation、validated planning completion projection 与 D-18 期限选择事务边界 |
| `retention.py` | FastAPI lifespan 驱动的 PostgreSQL advisory-lease 保留 Worker；按最早图片过期、7d/30d/删除期限唤醒，并处理记忆删除 outbox 的安全计数 |
| `state.py` | 版本化、受限、JSON-safe 的 MealAgentState 与独立 DietPlanningState；规划恢复只保存 opaque replay marker。 |
| `weight.py` | 独立用户重量命令解析；完整识别受支持单位，Decimal 换算克数后校验范围，不推断营养或模糊份量。 |
| `tools.py` | Graph 到确定性 Nutrition/Planning Service、显式偏好捕获及安全个人上下文检索的唯一工具适配器。 |
| `graph.py` | 主图路由、受限餐食/规划子图、槽位局部替换和 FastAPI lifespan runtime 合同。 |
| `supervisor.py` | 领取 PostgreSQL run lease，并在同一生命周期启动/停止 retention Worker |
| `schemas.py` | 与 ORM、Graph State、Provider DTO 分离的公开 Agent HTTP 请求/响应 schema |
| `api.py` | Bearer-protected Agent operation 的稳定 OpenAPI 合同；认证 Principal 由 `auth.api` 统一提供。包含 owned planning same-thread adjustment、图片上传、受限解码与幂等 Vision 路径；快照只含安全 recovery code，删除操作持久化 D-18 intent 后唤醒 lifecycle Worker。 |
