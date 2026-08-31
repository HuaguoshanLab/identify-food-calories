# Retrieval

## 职责

`retrieval/` 为当前偏好、同用户餐食历史和受控营养知识提供来源分离的上下文检索。个人用户过滤在 SQL 中完成；模型、API 和图不会接触向量或相似度分数。

## 允许依赖

- 可依赖 SQLAlchemy、`records`/`nutrition` ORM 和 `memory` 的 Service 窄接口。
- 只允许将安全文本摘要和来源标签返回给上层。
- 禁止在 Python 端做跨租户过滤、向上返回 embedding/score，或修改记忆账本。

## 文件索引

| 路径 | 职责 |
|---|---|
| `__init__.py` | Python 包标识 |
| `models.py` | 历史餐食与受控知识 embedding metadata ORM |
| `ports.py` | 安全检索 DTO 和 Repository Protocol |
| `repository.py` | SQL tenant/status/version-filtered exact retrieval adapter |
| `service.py` | 三来源组合与当前偏好优先级 |
