# 营养目录后台功能

## 职责

`catalog/` 承载营养目录草稿的严格 HTTP DTO、目录编辑工作台和局部组件。它只消费公开 `/api/v1/admin/catalog-drafts` 合约，以可读字段展示服务端确认的目录数据；目录审核、发布和失格由后续功能在此能力边界内扩展。

## 允许依赖

- 可依赖 React、React Hook Form、Zod、TanStack Query、`auth/` 的公开内存会话接口及 `components/ui/` 官方原语。
- `api.ts` 只可依赖 Zod、浏览器 `fetch` 与经构建校验的后台 API base；所有响应必须严格校验。
- 禁止导入用户 H5、后端源码、数据库、Provider SDK、密钥，或把访问令牌写入浏览器持久化存储。

## 文件索引

| 路径 | 职责 |
| --- | --- |
| `README.md` | 目录草稿能力的边界、允许依赖和文件索引。 |
| `CatalogDraftPage.test.tsx` | 目录草稿表单、确认、冲突和授权安全 UX 的组件契约。 |
| `CatalogDraftPage.tsx` | 目录草稿表单、确认状态和服务器确认字段的受限呈现。 |
| `api/` | 草稿严格 DTO 与公开 admin HTTP 命令；目录索引见 `api/README.md`。 |
