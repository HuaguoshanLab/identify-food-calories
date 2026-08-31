# Long-term Memory

## 职责

`memory/` 管理白名单饮食偏好的 Provider adapter、PostgreSQL 授权账本 CRUD 和删除 outbox。`PreferenceMemoryLedger` 是用户所有权与可见性的权威来源；Mem0 只是可删除的外部副本。

## 允许依赖

- 可依赖 `records.models` 的本地账本、SQLAlchemy、Pydantic 和 `core.config`。
- Service 只依赖 `MemoryProvider` Protocol；真实 SDK 仅在 `providers.py`。
- 禁止传递完整对话、图片/base64、embedding、provider 响应体或模型推理过程。

## 文件索引

| 路径 | 职责 |
|---|---|
| `__init__.py` | Python 包标识 |
| `ports.py` | 最小化的外部记忆 Provider Protocol 与 DTO |
| `providers.py` | Fake 与受配置控制的 Mem0 adapter |
| `repository.py` | tenant-filtered、flush-only ledger/outbox adapter |
| `service.py` | 偏好 CRUD、来源审计与删除重试 |
| `schemas.py` | 公开且无 external ID 的 HTTP DTO |
| `api.py` | Bearer 保护的记忆管理路由 |
