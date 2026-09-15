# 管理后台 UI 原语

## 职责

`components/ui/` 保存仅来自官方 shadcn/Base UI registry 的无业务含义 UI 原语。它们提供一致的交互和样式基础，不拥有网络请求、领域状态、认证协议或权限判断。

## 允许依赖

- 可依赖 React、已锁定的 Base UI、`class-variance-authority`、Tailwind 样式和本目录内的纯样式辅助代码。
- 仅允许从已配置的官方 shadcn/Base UI registry 生成原语；不得引入第三方 registry、整页 block 或第二套组件库。
- 禁止依赖 `features/`、`auth/`、`layouts/`、用户 H5、后端源码、数据库、Provider SDK、密钥，或直接调用 `/api/v1/admin/*`。

## 文件索引

| 路径 | 职责 |
| --- | --- |
| `README.md` | 官方 UI 原语边界、允许依赖与文件索引。 |
| `AlertDialog.tsx` | 基于官方 Base UI 的受控高风险确认对话框原语。 |

未来新增原语时保持官方 shadcn/Base UI 来源和无业务依赖边界；不再逐文件维护父级索引。
