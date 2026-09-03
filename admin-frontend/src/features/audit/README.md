# 后台操作审计功能

## 职责

`audit/` 负责读取和呈现后端返回的最小化、只读审计证据。`api.ts` 是唯一 HTTP/Zod 边界；页面不会从目录响应复用数据、拼接可信 diff 或保存操作内容。

## 允许依赖

- 可依赖 React、语义 HTML、`auth/` 的公开内存会话接口、Zod 与本功能 `api.ts`。
- `api.ts` 可请求公开 `/api/v1/admin/audit` 并完成严格 DTO 校验；页面不得直接 fetch。
- 禁止导入后端、用户 H5、数据库、Provider SDK、密钥，或持久化 access token、cursor 与审计证据。

## 文件索引

| 路径 | 职责 |
| --- | --- |
| `README.md` | 只读审计展示的边界、允许依赖与索引。 |
| `AuditTimeline.tsx` | 安全字段白名单过滤后的可访问审计时间线。 |
| `api.ts` | `/audit` 只读 allowlist filters、opaque cursor 与严格 Zod DTO。 |
| `AuditPage.tsx` | 筛选、只读表格、分页、skip link 与 401/403 安全失败体验。 |
| `AuditPage.test.tsx` | MSW/Vitest 审计 filters、最小化 DOM 和授权 UX 契约。 |
