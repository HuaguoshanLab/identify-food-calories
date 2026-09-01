# Memory API

## 职责

封装公开 `/api/v1/memories` 的脱敏 DTO 和管理请求。

## 允许依赖

- Zod 和 `auth/AuthenticatedRequest`；禁止 external ID、vector、score 或依赖其他 feature 的 API 类型。

## 文件索引

| 文件 | 职责 |
|---|---|
| `client.ts` | 记忆列表、详情、编辑和删除请求及 Zod schema |
