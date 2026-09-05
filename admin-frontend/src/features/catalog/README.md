# 营养目录后台功能

## 职责

`catalog/` 以筛选栏和服务端分页表格作为入口；新增/编辑、审核/发布及 CSV 导入统一使用居中弹窗。草稿填写后直接保存，不再套二次预览弹窗；保存前仍读取服务端预览并保护打开编辑时的版本。每行审核、发布分别确认，字段差异默认折叠；原因和后端审计不可省略。详情入口保留旧生命周期页及失格操作。

## 允许依赖

- 可依赖 React、React Hook Form、Zod、TanStack Query、`auth/` 的公开内存会话接口及 `components/ui/` 官方原语。
- `api.ts` 只可依赖 Zod、浏览器 `fetch` 与经构建校验的后台 API base；所有响应必须严格校验。
- 禁止导入用户 H5、后端源码、数据库、Provider SDK、密钥，或把访问令牌写入浏览器持久化存储。

## 文件索引

| 路径 | 职责 |
| --- | --- |
| `README.md` | 目录草稿能力的边界、允许依赖和文件索引。 |
| `CatalogDraftPage.test.tsx` | 目录草稿表单、确认、冲突和授权安全 UX 的组件契约。 |
| `CatalogDraftPage.tsx` | 草稿表单、弹窗直接保存/版本保护与幂等重试；兼容旧页的服务器预览与确认。 |
| `CatalogLifecyclePage.test.tsx` | 审核、发布、失格、冲突与只读审计的生命周期组件契约。 |
| `CatalogLifecyclePage.tsx` | 严格生命周期投影、两列 diff、理由确认和审计组合页。 |
| `api/` | 草稿严格 DTO 与公开 admin HTTP 命令；目录索引见 `api/README.md`。 |
| `CatalogListPage.tsx` | 筛选、分页、每行编辑/审核/发布的居中弹窗、模板/导出及授权错误处理。 |
| `CatalogListPage.test.tsx` | 筛选/分页、居中编辑保存/冲突保护、导入错误、重试去重和 403 零数据呈现。 |
| `CatalogDialog.tsx` | Base UI 居中弹窗、固定页脚、内容滚动、关闭优先焦点和提交期间关闭保护。 |
| `CatalogRowLifecycle.tsx` | 表格行审核/发布弹窗内容，服务端版本、折叠差异、原因确认与原键重试。 |
| `CatalogRowLifecycle.test.tsx` | 审核发布成功、原因必填、重复提交保护、冲突/权限及已发布/未授权阻止。 |
| `CatalogImportDialog.tsx` | CSV 选择、服务端校验预览、错误行号、原因确认及幂等重试。 |
