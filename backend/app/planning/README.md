# Diet Planning Domain

## 职责

`planning/` 拥有普通成年人单日饮食规划的版本化目标区间、健康拒绝、受控菜谱与管理员成品菜候选资格、餐单校验规则，以及唯一、最小化的身体资料与目标持久化边界。偏好仍只属于 `memory/`；本模块不诊断疾病、不生成模型推理。

## 允许依赖

- Domain Service 只通过 `PlanningRepository` 和 `PlanningNutritionPort` Protocol 获取资料、受控菜谱/成品菜候选和营养数据；每个菜品必须调用 nutrition 的确定性 `calculate_nutrition`，不得读取或保存 recipe total。
- 完成计划投影只通过 planning-owned Port 写入、撤销和读取；dashboard 仅消费资格、目标区间与版本，不能读取 profile ORM。
- Profile API 只可依赖 `auth.api.AuthenticatedPrincipal`、Profile Service 与 request-scoped SQLAlchemy adapter；不得接受客户端 `user_id`。
- Profile Service 只通过 `PlanningProfileRepository` 查询或写入；偏好、原始反馈、Provider 数据和医疗叙述禁止进入 profile。
- 禁止依赖 LangGraph State、Provider DTO 或 Agent 图。
- Repository 仅为受控菜谱 future query 读取 `app.admin` publication eligibility overlay；不得写入 admin 状态，已确认餐食快照不属于本模块重算范围。

## 文件索引

| 文件 | 职责 |
|---|---|
| `__init__.py` | Python 包标识与公开领域模块边界 |
| `schemas.py` | 冻结的 profile、偏好、目标、R-03 recipe、管理员成品菜候选、D-08 meal card 与闭合结果 DTO |
| `models.py` | 最小化的 owner-bound `PlanningProfile`、可撤销 `PlanningCompletionProjection`，以及受审核菜谱、固定食材引用和管理员候选 ORM 与数据库不变量 |
| `ports.py` | 可替换的 profile/recipe/candidate/nutrition 数据 Protocol、completion projection 与 profile CRUD port |
| `repository.py` | SQLAlchemy tenant-filtered profile/projection adapter，以及排除失格或停用目录项的 recipe/candidate future query |
| `service.py` | `target-policy.v1`、健康 guard、目录重算的餐单组合、确定性校验、completion projection 和 profile 事务边界 |
| `api.py` | 认证的 `/api/v1/planning/profile` HTTP CRUD 与统一不可用响应 |
| `importer.py` | 离线校验并幂等导入项目自有、已审核的受控菜谱 seed；仅启用 `controlled-recipes.v2`，旧版本保留审计记录但不能被组合 |
| `data/` | 项目自有、无第三方正文的 R-03 受控菜谱短 seed；`v1` 为审计历史，`v2` 为当前可用版本 |

## 正式餐单存档

`archive_*` 管理独立于 Agent 保留策略的日期计划与完整版本。Archive Service 经 Port 访问存储，完成写入只 flush；AgentService 拥有同事务 commit。Repository 为统计日期读取 records 的 `DashboardTimezonePreference`，为写入串行化锁定 auth 的 User 主键，为可调整性只读取 AgentThread/AgentEvent；这些跨域 ORM 读取不返回原始用户资料。

| 文件 | 职责 |
|---|---|
| `archive_schemas.py` | 独立于 State 的报告、存档命令、今日/历史/详情严格 DTO。 |
| `archive_ports.py` | 存档读写与事务能力边界。 |
| `archive_repository.py` | 用户隔离、日期分页、版本快照、删除墓碑及并发锁。 |
| `archive_service.py` | 日期归属、去重、完成存档、读取及删除事务。 |
| `archive_api.py` | 受保护的今日、历史、版本详情与删除 API。 |
