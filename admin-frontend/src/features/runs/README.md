# 运行诊断后台功能

## 职责

`runs/` 只消费后台公开的终态 Agent run metrics、签名游标分页列表和最小详情投影。它共享同一 UTC 筛选范围请求 metrics 与列表，详情只显示后端白名单的运行及 invocation 证据。

## 允许依赖

- 可依赖 React、语义 HTML、`auth/` 的公开内存会话接口和本功能的 `api.ts`。
- `api.ts` 只可依赖 Zod、浏览器 `fetch` 与受构建校验的后台 API base。
- 禁止导入用户 H5、后端、数据库、Provider SDK、密钥，或持久化 access token、cursor 与详情数据。

## 文件索引

| 路径 | 职责 |
| --- | --- |
| `README.md` | 运行诊断的边界、允许依赖与文件索引。 |
| `api.ts` | 严格 Zod metrics/list/detail DTO、allowlist filters 与 HTTP 读取。 |
| `RunsPage.tsx` | UTC 筛选、指标、语义表格、分页与会话安全失败体验。 |
| `RunDetailDrawer.tsx` | 最小 run/invocation 详情的键盘可关闭抽屉。 |
| `RunsPage.test.tsx` | MSW/Vitest 的筛选、cursor、详情、最小化与授权 UX 契约。 |
