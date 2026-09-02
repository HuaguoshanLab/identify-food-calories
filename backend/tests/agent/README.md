# Agent Stage-Mapping Tests

## 职责

本目录验证餐食分析图的内部生命周期只会映射为冻结的用户可见 SSE 阶段。

## 允许依赖

- pytest 与 `app.agent` 的公开、无状态映射接口。
- 禁止数据库、网络、Provider 原文、LangGraph Checkpoint 或真实用户输入。

## 文件索引

| 路径 | 职责 |
|---|---|
| `__init__.py` | 为同名阶段映射测试提供独立 Python package namespace。 |
| `test_safe_stream_stage_mapping.py` | 餐食分析阶段、interrupt/resume 与稳定失败结果映射。 |
