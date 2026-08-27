# Frontend Components

## 职责

`src/components/` 保存可复用的浏览器 UI 组件边界。当前只建立官方 shadcn Base UI 基础设施；具体认证与应用组件由后续计划按页面契约添加。

## 允许依赖

- 可依赖 React、Base UI、Lucide 和 `src/components/ui/` 中的官方 shadcn 封装。
- 可依赖同级纯展示组件，不得直接访问数据库、服务端密钥或 backend 源码。
- 服务端状态必须留在 TanStack Query 边界，组件不得自行建立第二套缓存。
- 禁止第三方 shadcn registry、整页 block 和 Next.js 专用模块。

## 文件索引

| 路径 | 职责 |
|---|---|
| `README.md` | 组件目录职责、依赖边界与索引 |
| `ui/` | 官方 shadcn Base UI 组件与共享样式 utility：表单、布局、AlertDialog 与状态原语 |
