# Nutrition Domain

## 职责

`nutrition/` 提供受控营养目录的确定性查询、计算与校验。它只处理版本化、具备来源和授权且可计算的数据；不导入 Agent、Provider、FastAPI 或 LangGraph State。

## 允许依赖

- Pydantic DTO、Decimal、SQLAlchemy adapter 与共享 `app.auth.models.Base`；Repository 可只读 `app.admin` 的 publication pointer/eligibility ORM，以 SQL 排除未来失格版本。
- Service 只依赖 `NutritionRepository` Protocol；单元测试必须使用内存 fake。
- API 或 Agent 编排只能调用 `NutritionService` 的三个公开工具方法，不能查询这里的 ORM。

## 文件索引

| 文件 | 职责 |
|---|---|
| `schemas.py` | 营养工具输入、输出、版本与封闭 action DTO |
| `ports.py` | 可替换的 qualified catalog Repository Protocol |
| `models.py` | 共享 Base 的 catalog/version/source/food/alias/portion 权威营养目录 ORM 模型 |
| `repository.py` | flush-only SQLAlchemy 查询 adapter；只读取 active + eligible admin publication snapshot，并在失格后立即拒绝未来查询 |
| `service.py` | `search_food_catalog`、`calculate_nutrition`、`validate_nutrition_result` |
| `importer.py` | 离线 FDC manifest 校验、不可变版本写入与 CLI |
| `data/` | 受 hash 保护的 USDA FDC 小型 seed manifest |
