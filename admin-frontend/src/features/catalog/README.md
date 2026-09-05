# 营养目录后台功能

## 职责

`catalog/` 以筛选栏和服务端分页表格作为入口；新增/编辑在侧边窗口填写，CSV 导入先校验后确认，导出遵循已应用的筛选条件。它只消费公开 admin 合约；确认前显示服务端字段差异，保留既有审核、发布、失格与审计流程。

## 允许依赖

- 可依赖 React、React Hook Form、Zod、TanStack Query、`auth/` 的公开内存会话接口及 `components/ui/` 官方原语。
- `api.ts` 只可依赖 Zod、浏览器 `fetch` 与经构建校验的后台 API base；所有响应必须严格校验。
- 禁止导入用户 H5、后端源码、数据库、Provider SDK、密钥，或把访问令牌写入浏览器持久化存储。

## 文件索引

| 路径 | 职责 |
| --- | --- |
| `README.md` | 目录草稿能力的边界、允许依赖和文件索引。 |
| `CatalogDraftPage.test.tsx` | 目录草稿表单、确认、冲突和授权安全 UX 的组件契约。 |
| `CatalogDraftPage.tsx` | 目录草稿表单、服务器预览/冲突刷新、确认状态和服务器确认字段的受限呈现。 |
| `CatalogLifecyclePage.test.tsx` | 审核、发布、失格、冲突与只读审计的生命周期组件契约。 |
| `CatalogLifecyclePage.tsx` | 严格生命周期投影、两列 diff、理由确认和审计组合页。 |
| `api/` | 草稿严格 DTO 与公开 admin HTTP 命令；目录索引见 `api/README.md`。 |
| `CatalogListPage.tsx` | 筛选、分页表格、按需编辑、模板/导出及授权错误处理。 |
| `CatalogListPage.test.tsx` | 筛选/分页、编辑窗口、导入错误、重试去重和 403 零数据呈现。 |
| `CatalogDialog.tsx` | 本 feature 的 Base UI 侧边对话框与焦点/关闭语义。 |
| `CatalogImportDialog.tsx` | CSV 选择、服务端校验预览、错误行号、原因确认及幂等重试。 |
