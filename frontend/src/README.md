# Frontend Source

## 职责

`src/` 保存浏览器端 React 运行时代码。当前只负责挂载应用并通过公开 API 查询后端健康状态，不包含认证或业务占位实现。

## 允许依赖

- 可依赖 `frontend/package.json` 中已审核的浏览器和 UI 包。
- 网络访问只能面向公开 FastAPI `/api/v1` 合约。
- 禁止依赖 backend 源码、Node 服务端 API、数据库驱动和任何密钥。

## 文件索引

| 文件 | 职责 |
|---|---|
| `main.tsx` | React、Router 与 Query Client 组合根 |
| `App.tsx` | 后端健康状态运行壳 |
