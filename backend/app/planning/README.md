# Diet Planning Domain

## 职责

`planning/` 拥有普通成年人单日饮食规划的版本化目标区间、健康拒绝和餐单校验规则。它只返回安全的行动和公共目标 DTO；不诊断疾病、不生成模型推理、不写入个人资料或长期偏好。

## 允许依赖

- 可依赖 Pydantic、`Decimal` 与本目录的 Protocol。
- Service 只通过 `PlanningRepository` 和 `PlanningNutritionPort` Protocol 获取未来的 profile、受控菜谱和营养数据。
- 禁止依赖 FastAPI、SQLAlchemy Session、ORM、LangGraph State、Provider DTO 或 Agent 图。

## 文件索引

| 文件 | 职责 |
|---|---|
| `__init__.py` | Python 包标识与公开领域模块边界 |
| `schemas.py` | 冻结的 profile、偏好、目标、菜谱与闭合结果 DTO |
| `ports.py` | 可替换的 profile/recipe/nutrition 数据 Protocol |
| `service.py` | `target-policy.v1`、健康 guard 和确定性校验入口 |
