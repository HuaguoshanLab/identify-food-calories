# Diet Planning API

## 职责

封装公开的 `/api/v1/planning/profile` 只读预填和 `/api/v1/agent/threads/diet-planning` 启动命令，所有传入及返回的浏览器 DTO 均经过 Zod 运行时校验。

## 允许依赖

- Zod 与 `auth/AuthContext.ts` 的 `AuthenticatedRequest`。
- 禁止导入后端实现、直接 `fetch`、本地持久化资料或绕过 Agent 启动命令的 profile 写入。

## 文件索引

| 文件 | 职责 |
|---|---|
| `schemas.ts` | Closed profile、启动命令与安全事件 DTO。 |
| `client.ts` | 资料预填读取和具备幂等键的规划启动请求。 |
