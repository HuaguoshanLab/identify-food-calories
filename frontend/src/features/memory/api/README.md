# Memory API

## 职责

封装公开 `/api/v1/memories` 的脱敏 DTO 和管理请求。

## 允许依赖

- Zod 和认证请求；禁止 external ID、vector 与 score。

## 文件索引

| 文件 | 职责 |
|---|---|
| `client.ts` | 记忆列表、详情、编辑和删除请求及 Zod schema |
