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
| `AppHeader.tsx` | 48px 主体的详情返回栏，18px 居中唯一主标题；按真实历史返回。 |
| `TabHeader.tsx` | 56px 主体的固定 Tab 页头；图标及20px标题，pathname变化时聚焦，不打断同页输入。 |
| `tabNavigation.ts` | 四项 Tab 的路由、标签、页头标题和图标唯一配置。 |
| `PublicAuthLayout.tsx` | 公开页和认证页的无 Tab 外壳；显式区分品牌入口与有确定返回目标的后续步骤。 |
| `DetailLayout.tsx` | 详情无 Tab 外壳，唯一滚动区与底部安全区；pathname变化时重置阅读位置。 |
| `AppShell.tsx` | 固定页头、唯一主滚动区和导航在 frame 内同级；常规内容28px、窄屏16px边距，保留跳转入口。 |
| `BottomNavigation.tsx` | 以 `routePaths.ts` 为唯一真相的真实四项路由导航；不维护本地 active 状态。 |
| `layouts.test.tsx` | 外壳滚动、导航语义和可访问性合同测试。 |

页头和底部导航的主体高度不含1px边框与安全区。详情/Tab根页面内容不再输出h1，主标题由布局拥有；公开认证页保留页面自己的h1。查询参数变化不重置滚动和焦点。
