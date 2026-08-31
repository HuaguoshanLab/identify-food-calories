# Long-term Memory Service Tests

## 职责

本目录用 fake ledger repository 和 FakeMemoryProvider 验证长期偏好的授权、来源、隔离及删除 outbox 规则。

## 允许依赖

- 仅依赖 pytest、memory Service、ORM 构造器和 deterministic fake Provider。
- 禁止 Mem0 网络、真实数据库与 HTTP client；真实删除链属于 integration tests。

## 文件索引

| 路径 | 职责 |
|---|---|
| `test_memory_service.py` | ledger 授权、来源审计、删除立即不可见与重试测试 |
