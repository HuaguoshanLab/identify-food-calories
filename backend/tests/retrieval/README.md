# Retrieval Service Tests

## 职责

本目录用 fake 记忆和检索 repository 验证三来源合成、偏好优先与安全 DTO 边界。

## 允许依赖

- 仅依赖 pytest、retrieval Service 和 fake adapter。
- 禁止真实数据库、向量服务、Provider 网络与直接 Graph checkpoint 操作。

## 文件索引

| 路径 | 职责 |
|---|---|
| `test_retrieval_service.py` | 三来源标注、当前偏好优先与零写入检索规则 |
