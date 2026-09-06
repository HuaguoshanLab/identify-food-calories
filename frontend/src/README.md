# Frontend Source

## 职责

`src/` 保存浏览器端 React 运行时代码。当前负责公开 landing、法律页面、认证表单和内存认证启动；`/app` 通过数据库权威的 `/users/me` 保护，饮食业务功能按后续计划接入。

## 允许依赖

- 可依赖 `frontend/package.json` 中已审核的浏览器和 UI 包。
- 网络访问只能面向公开 FastAPI `/api/v1` 合约。
- 禁止依赖 backend 源码、Node 服务端 API、数据库驱动和任何密钥。

## 文件索引

| 文件 | 职责 |
|---|---|
| `main.tsx` | React、Router 与 Query Client 组合根 |
| `App.tsx` | 用户 H5 的嵌套路由表：公开/认证内容统一进入 `PublicAuthLayout`，所有 `/app/*` 统一经过 pathless guard 后再分流到四 Tab 或无底栏详情；不包含后台路由 |
| `App.test.tsx` | 路由 index replace、Tab 浏览器历史、刷新深链和详情壳的 Vitest/Testing Library 行为测试 |
| `routePaths.ts` | 用户 H5 的精确路径合同，供路由声明与登录返回地址白名单共同使用 |
| `styles.css` | Tailwind CSS 入口、h5-forest-v1 森林绿主题、系统中文字体、8px 基础圆角、绿灰阴影与全局可访问性样式 |
| `test-setup.ts` | Vitest 的 jest-dom 断言扩展与测试后 DOM 清理 |
| `auth/` | 认证页面、内存会话、路由守卫与受控 API 适配器；禁止存储 token、验证码或引入后台表面 |
| `components/` | 应用组件边界与官方 shadcn UI 基础设施（Button/Input/Label/Card/Separator 等原语） |
| `layouts/` | H5 设备容器、唯一主滚动区、公开/详情/Tab 外壳和底部导航；不承载业务数据或认证协议 |
| `app/` | 登录后 Tab 根页与详情页的内容组件；不自行包裹页面壳或复制认证/Query 状态 |
| `features/` | 按业务能力组织的用户功能模块；Agent 的页面、生成 API 合约与流式边界都位于此处，路由、认证和页面壳保持在既有边界。 |

- `App.tsx` / `routePaths.ts` 同步登记 `/app/plans/history` 与 `/app/plans/detail?id=…`，详情使用 DetailLayout，登录返回仍为精确路径白名单。
