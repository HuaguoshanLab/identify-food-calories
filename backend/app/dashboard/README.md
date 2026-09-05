# Dashboard Domain

## 职责

`dashboard/` 提供用户看板的严格读模型：聚合已确认餐食快照，并通过窄完成计划资格 Port 读取目标区间。它只读 records 所有、经一次确认的统计时区，并由 Service 用 ZoneInfo 计算用户本地今日和自然周；overview 与默认周复盘不接受浏览器范围，显式周复盘只可读取已结束的本地 Monday 周。周复盘 graph 只接收已验证的去标识聚合事实并调用 Reasoning Provider 窄 port；它不读取规划资料、健康详情、Agent State、ORM 或 Provider 原始数据。

## 允许依赖

- 仅可依赖规划模块公开的、最小化资格 Port 和运行时 DTO；可通过只读 Port 查询 records 所有的、一次确认统计时区。SQL 只读取本用户未软删且已有持久化 `consumed_local_date` 的餐食快照。
- 不得导入 `PlanningProfile` ORM，也不得通过 profile 推导目标。

## 文件索引

| 文件 | 职责 |
|---|---|
| `__init__.py` | Python 包标识。 |
| `ports.py` | 看板对完成计划资格和 records-owned 已确认统计时区的窄只读 `DashboardTimezoneReadPort` Protocol；不提供 preference 写入能力。 |
| `schemas.py` | `extra=forbid` 的 overview/history、闭合安全周复盘 HTTP DTO 与私有 cursor 位置。 |
| `repository.py` | tenant-filtered 的 SQL 聚合、统计时区投影与 keyset 分页 adapter；不读取 Profile 作为目标真相。 |
| `service.py` | preference-owned overview/history、用户统计时区 ZoneInfo 当前窗口、已结束周复盘域验证、facts-first cache 用例、目标 Port 注入和 HMAC 签名 opaque cursor。 |
| `weekly_review_dto.py` | 周复盘最小 facts、cache key 与安全响应 DTO。 |
| `weekly_review_graph.py` | 最多两次、八秒、360 token 的 facts-only 周复盘安全 graph 与语义阀。 |
| `weekly_review.py` | 周复盘 graph 的应用层调用包装；持久化只能消费返回的最小安全元数据。 |
| `models.py` | 仅保存语义安全建议、摘要和版本的周复盘缓存 ORM。 |
| `api.py` | `/api/v1/dashboard` HTTP 路由与输入边界；overview 不接收客户端范围，weekly 仅映射 Service 的本地历史周校验结果。 |
