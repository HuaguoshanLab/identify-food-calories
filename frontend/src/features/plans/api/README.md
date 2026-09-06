# Diet Planning API

## 职责

定义规划页面使用的公开 HTTP 与 SSE 契约；在进入组件前完成 Zod 运行时校验，不传播未验证的响应、Graph State 或 Provider 数据。

## 允许依赖

- Zod、认证请求能力和本 feature 的 Schema。
- 禁止后端源码、直接 DOM 操作、组件导入和 localStorage 健康资料缓存。

## 文件索引

| 文件 | 职责 |
| --- | --- |
| `client.ts` | 规划启动与调整的受控公开 API 调用。 |
| `profile.ts` | 个人资料 HTTP 契约和安全错误映射。 |
| `schemas.ts` | 规划表单、快照和报告运行时 Schema。 |
| `stream.ts` | 版本化安全 SSE 阶段的严格 Zod 边界。 |

| `archive.ts` | 今日、分页历史、版本详情、删除请求与 Query keys。 |
| `report.ts` | 首次/调整餐单、放宽目标与安全快照共用 Zod 合同。 |
