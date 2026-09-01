# Diet Planning Domain

## 职责

`planning/` 拥有普通成年人单日饮食规划的版本化目标区间、健康拒绝和餐单校验规则，以及唯一、最小化的身体资料与目标持久化边界。偏好仍只属于 `memory/`；本模块不诊断疾病、不生成模型推理。

## 允许依赖

- Domain Service 只通过 `PlanningRepository` 和 `PlanningNutritionPort` Protocol 获取资料、受控菜谱和营养数据。
- Profile API 只可依赖 `auth.api.AuthenticatedPrincipal`、Profile Service 与 request-scoped SQLAlchemy adapter；不得接受客户端 `user_id`。
- Profile Service 只通过 `PlanningProfileRepository` 查询或写入；偏好、原始反馈、Provider 数据和医疗叙述禁止进入 profile。
- 禁止依赖 LangGraph State、Provider DTO 或 Agent 图。

## 文件索引

| 文件 | 职责 |
|---|---|
| `__init__.py` | Python 包标识与公开领域模块边界 |
| `schemas.py` | 冻结的 profile、偏好、目标、菜谱与闭合结果 DTO |
| `models.py` | 最小化的 owner-bound `PlanningProfile` ORM 与数据库不变量 |
| `ports.py` | 可替换的 profile/recipe/nutrition 数据 Protocol 与 profile CRUD port |
| `repository.py` | SQLAlchemy tenant-filtered profile adapter，读取自动排除软删除资料 |
| `service.py` | `target-policy.v1`、健康 guard、确定性校验和 profile 事务边界 |
| `api.py` | 认证的 `/api/v1/planning/profile` HTTP CRUD 与统一不可用响应 |
