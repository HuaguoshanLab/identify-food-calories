# Frontend Source

## 职责

`src/` 保存浏览器端 React 运行时代码。当前负责公开 landing、法律页面及登录/注册/注册验证码表单；受保护业务内容、完整认证状态、后端密码恢复 API 和饮食功能按后续计划接入。

## 允许依赖

- 可依赖 `frontend/package.json` 中已审核的浏览器和 UI 包。
- 网络访问只能面向公开 FastAPI `/api/v1` 合约。
- 禁止依赖 backend 源码、Node 服务端 API、数据库驱动和任何密钥。

## 文件索引

| 文件 | 职责 |
|---|---|
| `main.tsx` | React、Router 与 Query Client 组合根 |
| `App.tsx` | 用户 H5 路由表；只声明公开入口与受保护 `/app` 入口，不包含后台路由 |
| `App.test.tsx` | 落地页路由的 Vitest/Testing Library 行为测试 |
| `styles.css` | Tailwind CSS 入口、UI-SPEC 颜色/圆角 tokens 与全局可访问性样式 |
| `test-setup.ts` | Vitest 的 jest-dom 断言扩展与测试后 DOM 清理 |
| `auth/` | 公开认证页面、表单与受控 API 适配器；禁止存储 token、验证码或引入后台表面 |
| `components/` | 应用组件边界与官方 shadcn UI 基础设施（Button/Input/Label/Card/Separator 等原语） |
