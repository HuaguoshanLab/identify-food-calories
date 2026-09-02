# Records API

## 职责

封装公开 `/api/v1/meal-records` 的 Zod DTO 与认证请求。

## 允许依赖

- Zod 与认证请求函数；禁止后端内部字段。

## 文件索引

| 文件 | 职责 |
|---|---|
| `schemas.ts` | 餐食记录安全响应 DTO |
| `client.ts` | 保存、列表、详情、修改和删除请求 |
| `dashboard.ts` | strict dashboard overview/history DTO、query key 与公开请求 |
