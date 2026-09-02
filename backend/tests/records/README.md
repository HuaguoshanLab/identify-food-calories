# Meal Record Service Tests

## 职责

本目录用内存 fake repository 验证餐食记录 Service 的显式确认、tenant 隔离、幂等、时间和删除规则。

## 允许依赖

- 仅可依赖 pytest、领域 Service、ORM 构造器和 fake repository。
- 禁止网络、真实数据库和 FastAPI HTTP client；这些证据属于 `tests/integration/` 与 `tests/unit/`。

## 文件索引

| 路径 | 职责 |
|---|---|
| `test_record_service.py` | 餐食快照、IANA 本地日冻结与确认回填 Service 协议测试 |
