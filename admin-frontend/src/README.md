# 管理后台源码

## 职责

`src/` 保存独立管理后台的浏览器运行时代码。它只装配后台路由、内存会话、页面壳和按能力划分的功能模块；所有数据只能经公开 `/api/v1/admin/*` 合约取得，后端数据库 RBAC 仍是唯一授权真相。

## 允许依赖

- 仅依赖本项目 `package.json` 已锁定的 React、Router、TanStack Query、Base UI 和测试包。
- 网络调用只能由功能所属的 `features/<feature>/api/` 访问公开后台 API，并在该处完成运行时 DTO 校验。
- 禁止导入用户 H5、后端源码、数据库客户端、Provider SDK 或任何密钥。

## 文件索引

| 路径 | 职责 |
| --- | --- |
| `main.tsx` | 按 BrowserRouter、QueryClientProvider、AdminAuthProvider、App 的固定顺序装配运行时。 |
| `App.tsx` | 独立后台路由根，组合登录、probe guard、AdminShell 与 feature outlet。 |
| `vite-env.d.ts` | Vite 与经构建校验的后台 API base 类型声明。 |
| `auth/` | 管理员运行时身份、令牌清理和后续认证体验；不承担后端授权。 |
| `styles/` | 后台语义 token、全局可访问性与减弱动画基线。 |
| `test/` | Vitest、Testing Library、MSW 的共享测试运行时。 |
| `layouts/` | 后台页面壳、导航和桌面/窄屏结构；不发领域请求，目录索引见 `layouts/README.md`。 |
| `components/` | 仅跨两个以上后台 feature 的共享展示组件与官方 UI 原语；目录索引见 `components/README.md`。 |
| `features/` | 按后台能力隔离的 API、Query、页面和组件；目录索引见 `features/README.md`。 |
