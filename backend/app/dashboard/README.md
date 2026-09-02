# Dashboard Domain

## 职责

`dashboard/` 定义用户看板消费的最小完成计划资格边界。它不读取规划资料、健康详情、Agent State 或 Provider 数据。

## 允许依赖

- 仅可依赖规划模块公开的、最小化资格 Port 和运行时 DTO。
- 不得导入 `PlanningProfile` ORM，也不得通过 profile 推导目标。

## 文件索引

| 文件 | 职责 |
|---|---|
| `__init__.py` | Python 包标识。 |
| `ports.py` | 看板对完成计划资格的窄读取 Protocol。 |
