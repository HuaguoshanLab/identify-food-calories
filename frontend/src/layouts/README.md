# Layouts

## 职责

`layouts/` 集中定义用户 H5 的视口、单一主滚动区和页面外壳边界。它只负责结构、导航语义和可访问性，不承载认证状态、接口请求或具体业务内容。

## 允许依赖

- 可依赖 React、React Router、已锁定的 Lucide 图标和 `src/routePaths.ts`。
- 可依赖 `src/components/ui/` 中的通用 UI 原语。
- 禁止依赖 `auth/api.ts`、TanStack Query、后端源码、数据库、运行时密钥或具体饮食业务模块。

## 文件索引

| 文件 | 职责 |
|---|---|
| `MobileFrame.tsx` | H5 视口与桌面设备容器，拥有唯一的页面高度、flex 列布局和裁剪边界。 |
| `PageScrollArea.tsx` | 仅有的页面主纵向滚动区。 |
| `AppHeader.tsx` | 详情页的确定返回入口与标题栏。 |
| `PublicAuthLayout.tsx` | 公开页和认证页的无 Tab 外壳；显式区分品牌入口与有确定返回目标的后续步骤。 |
| `DetailLayout.tsx` | 账号资料与会话详情页的无 Tab 外壳；组合标题栏、返回“我的”链接和主滚动区。 |
| `AppShell.tsx` | 四个 Tab 根页面的统一外壳；提供可聚焦跳转链接，并让主滚动区与导航保持 frame 内同级。 |
| `BottomNavigation.tsx` | 以 `routePaths.ts` 为唯一真相的真实四项路由导航；不维护本地 active 状态。 |
| `layouts.test.tsx` | 外壳滚动、导航语义和可访问性合同测试。 |
