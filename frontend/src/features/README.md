# Feature Modules

## 职责

`features/` 保存按用户业务能力组织的前端模块。路由表和页面壳仍由 `src/App.tsx`、`layouts/` 组合；模块不能绕过认证边界或直接依赖后端源码。

## 允许依赖

- 可以依赖 React、公开的 `auth/` hook、`components/ui/` 和公开的 `/api/v1` 合约。
- 禁止读取浏览器持久化 token、服务端密钥、数据库或 LangGraph State。

## 文件索引

| 目录 | 职责 |
|---|---|
| `agent/` | 用户餐食分析能力的页面、API 合约与流式传输边界。 |
