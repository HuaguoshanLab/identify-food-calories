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
| `client.test.ts` | 保存请求必须提交浏览器 IANA 时区；confirmation 仅严格 200 成功，different-zone 409 是可分类安全冲突 |
| `dashboard.test.ts` | history 严格 DTO 接受后端 RFC 3339 时间戳、将被 `response_model_exclude_none` 省略的 cursor 恢复为 null，并验证 current cache key/URL 不含浏览器范围 |
| `dashboard.ts` | strict dashboard overview/history DTO；overview current key 固定且无范围，history 只使用 opaque cursor |
| `weeklyReview.ts` | strict weekly-review safe-outcome DTO；无参数 current 与显式 completed history 使用独立 typed 调用/key，服务端 preference 是统计权威 |
| `mealMetadata.ts` | meal-slot.v1 餐次标签、初始建议、RHF/Zod 时间表单合同；由公开 client 导出供分析确认使用。 |
