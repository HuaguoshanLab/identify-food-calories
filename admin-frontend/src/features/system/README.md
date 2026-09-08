# 系统管理

## 职责

`system/` 负责全部账号的最小化列表、固定角色说明，以及受审计的管理员授予/撤销交互。

## 允许依赖

- 可依赖 React、TanStack Query、认证上下文和共享 UI 原语。
- HTTP 与 Zod DTO 只能位于 `api/`；只调用公开 `/api/v1/admin/users` 与 `/api/v1/admin/roles`。
- 不得读取用户会话、密码、健康资料、餐食或 Agent 原文，不得把前端禁用态当作授权。

## 文件索引

| 路径 | 职责 |
| --- | --- |
| `api/index.ts` | 账号、角色与角色变更的严格 HTTP/Zod 合同。 |
| `UsersPage.tsx` | 账号筛选分页、角色变更确认和安全失败处理。 |
| `RolesPage.tsx` | 固定 `user/admin` 权限矩阵与账号统计。 |
| `UsersPage.test.tsx` | 全账号邮箱、自操作禁用、原因确认和公开角色命令组件合同。 |
