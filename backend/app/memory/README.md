# Long-term Memory

## 职责

`memory/` 管理白名单饮食偏好的 Provider adapter、PostgreSQL 授权账本 CRUD，以及可取消的 provision/delete outbox。`PreferenceMemoryLedger` 是用户所有权与可见性的权威来源；Mem0 只是可删除的外部副本。

## 允许依赖

- 可依赖 `records.models` 的本地账本、SQLAlchemy、Pydantic 和 `core.config`；API 从 `auth.api.AuthenticatedPrincipal` 获取用户身份，不依赖 Agent API。
- Service 只依赖 `MemoryProvider` Protocol；真实 SDK 仅在 `providers.py`。直接表达先用 opaque request key 建本地 ledger/intent，再由 Provider 写入，避免把原句、run ID 或外部 ID 暴露给 DTO。Mem0 direct add 固定 `infer=False`，重试只可用同一用户下的 exact request-key resolver，绝不走语义搜索。
- 禁止传递完整对话、图片/base64、embedding、provider 响应体或模型推理过程。
- Fake 副本只在实例内存中。编辑通过账本授权后，仅在 Provider 明确报告 `MemoryReplicaMissing` 时重建副本并绑定新 UUID 编号；不能把超时或归属错误当作缺失，不能依赖 Fake 内存保存权威正文。

## 文件索引

| 路径 | 职责 |
|---|---|
| `__init__.py` | Python 包标识 |
| `ports.py` | 最小化的外部记忆 Provider Protocol 与 DTO |
| `providers.py` | Fake 与受配置控制的 Mem0 adapter；direct write 的 exact-key / `infer=False` 合同 |
| `repository.py` | tenant-filtered、flush-only ledger/provision/delete outbox adapter |
| `service.py` | 偏好 CRUD、来源审计、direct write intent 与删除重试 |
| `schemas.py` | 公开且无 external ID 的 HTTP DTO |
| `api.py` | Bearer 保护的记忆管理路由 |
