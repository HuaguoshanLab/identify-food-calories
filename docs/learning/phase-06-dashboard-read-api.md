# Phase 06：看板读 API 的投影边界

## 为什么看板不读取个人资料

今日摄入和历史记录是 `MealRecord` 的已确认营养快照；它们按保存时确认的 IANA 时区固化为 `consumed_local_date`。看板不能为了显示进度而查询 `PlanningProfile`，更不能从身高、体重或目标类型重新猜一个热量目标：资料更新、删除或旧规划失效后，这种猜测会把已经撤销的目标继续展示给用户。

目标资格只有一个来源：规划模块提供的 `PlanningCompletionTargetPort`。该 Port 只返回 `eligible`、固定目标区间和版本；没有活跃、已验证的完成计划投影时返回 `eligible=false`，DTO 会省略目标值。

## 请求与数据流

```text
GET /api/v1/dashboard/overview
  → dashboard/api.py：认证主体和查询参数
  → dashboard/service.py：本周七个本地日槽位 + 窄目标 Port
  → dashboard/repository.py：user_id + deleted_at + consumed_local_date SQL 聚合
  → MealRecord 已确认营养快照

GET /api/v1/dashboard/history
  → service 解码并校验签名 cursor
  → repository 以 local_date / consumed_at / id DESC keyset 查询
  → service 仅投影历史最小营养事实并签发下一页 opaque cursor
```

Repository 从一开始就在 SQL 加入 `user_id`、`deleted_at IS NULL` 与非空 `consumed_local_date`；不能先载入所有记录再在 Python 或浏览器过滤。`consumed_local_date` 是持久化事实，当前系统时间或前端时区不参与历史归属。

## 如何测试

服务层用 fake repository 和 fake completion Port 验证七天槽位、目标降级和 cursor 调用；HTTPX 合约验证公开路由只暴露 overview/history，并将篡改 cursor 与非法范围映射为 422。Repository 集成测试必须通过隔离 PostgreSQL wrapper：

```bash
cd backend
uv run python tests/run_pg.py --env-file .env.test.example -- \
  uv run pytest tests/dashboard/test_dashboard_service.py \
  tests/integration/test_dashboard_repository.py \
  tests/integration/test_dashboard_overview_projection.py \
  tests/unit/test_dashboard_api.py -q
```

这组测试覆盖软删和跨用户记录不进入聚合、同一时间戳下由 UUID 决定稳定次序，以及无有效 projection 时目标字段从响应中消失。

## 常见错误

- 用 `PlanningProfile` 推导目标：这绕过撤销投影，属于授权错误。
- 将 cursor 做成明文 JSON 或 offset：前者可被篡改，后者在插入记录时会漏项或重复。
- 重新按当前营养目录计算历史 totals：目录会演进，历史必须使用确认时快照。
- 把餐食原文、图片、邮箱、Agent run 或模型数据塞进 history DTO：看板只需要最小的日期、总量和记录 ID。
