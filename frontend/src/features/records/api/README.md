# Records API

## 职责

封装公开 `/api/v1/meal-records` 的 Zod DTO 与认证请求。

## 允许依赖

- Zod 与认证请求函数；禁止后端内部字段。

## 文件索引

| 文件 | 职责 |
|---|---|
| `schemas.ts` | 餐食记录安全响应 DTO |
| `client.ts` | 保存、列表、详情、修改和删除请求；浏览器 IANA zone 只能通过 records confirmation command 提交 |
| `client.test.ts` | 保存请求必须提交浏览器 IANA 时区；confirmation 严格解析 200，并把既有 preference 的 409 作为读取 gate 成功 |
| `dashboard.test.ts` | history 严格 DTO 接受后端 RFC 3339 时间戳、将被 `response_model_exclude_none` 省略的 cursor 恢复为 null，并验证 cache key 只含真实请求变量 |
| `dashboard.ts` | strict dashboard overview/history DTO、只反映 `weekStart`/cursor 的 query key 与公开读取请求；不接收浏览器 timezone |
| `weeklyReview.ts` | strict weekly-review safe-outcome DTO、只按 `weekStart` 缓存的公开读取请求；服务端已确认 preference 是统计权威 |
