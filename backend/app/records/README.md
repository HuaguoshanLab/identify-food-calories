# Meal Records

## 职责

`records/` 保存用户显式确认后的餐食营养快照，并维护长期偏好记忆的本地授权账本与外部删除 outbox。它不是 Agent 图状态、营养目录或外部记忆 Provider 的实现位置。

## 允许依赖

- 可依赖 Pydantic、SQLAlchemy、`auth` 的 Base，以及 Agent/Nutrition 的窄 Port 或安全 DTO。
- API 只调用 Service，并从 `auth.api.AuthenticatedPrincipal` 获取用户身份；Service 只通过 Repository Port 访问持久化数据。
- 禁止 LangGraph、Provider、原图/base64、完整对话和 embedding 直接进入本模块。

## 文件索引

| 路径 | 职责 |
|---|---|
| `__init__.py` | Python 包标识 |
| `models.py` | 餐食快照、看板统计时区确认/回填审计、记忆授权账本和删除 outbox ORM |
| `ports.py` | 记录 Service 所依赖的窄 Repository Protocol |
| `repository.py` | tenant-filtered、flush-only SQLAlchemy adapter（含统计时区回填查询） |
| `service.py` | 显式餐次确认、独立餐次/时间修改、删除、IANA 本地日冻结，以及同 IANA 安全幂等/异 IANA 泛化冲突并可从唯一约束竞争恢复的一次性回填事务边界 |
| `schemas.py` | 独立 HTTP 请求/响应 DTO，不描述历史所在地 |
| `api.py` | 认证保护的餐食记录与统计时区确认 REST 路由；无效 IANA 统一映射为不泄露实现细节的 400 |

- planning 的 archive Repository 只读 `DashboardTimezonePreference` 作为计划日期归属；确认仍由 records API/Service 执行，不允许 planning 修改此事实。
