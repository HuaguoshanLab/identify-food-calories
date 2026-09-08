# 管理后台页面壳

## 职责

`layouts/` 保存独立后台的页面壳、侧栏、顶部栏及桌面到窄屏的结构适配。它只组合导航和布局，不发领域请求、不定义后端 DTO，也不把前端可见性当作授权判断。

## 允许依赖

- 可依赖 `src/routePaths.ts`、React 和 `src/components/ui/` 的官方原语。
- 可依赖 `src/auth/` 已公开的会话体验接口，但不得读取或持久化 token。
- 禁止依赖用户 H5、后端源码、数据库、Provider SDK、feature 私有实现，或直接访问 `/api/v1/admin/*`。

## 文件索引

| 路径 | 职责 |
| --- | --- |
| `README.md` | 页面壳职责、允许依赖与文件索引。 |
| `AdminShell.tsx` | 固定侧栏、顶部区域、响应式抽屉和 main landmark 的装配边界；不发领域请求。 |
| `AdminHeader.tsx` | 顶部面包屑、全局操作入口与管理员会话菜单。 |
| `AdminSidebar.tsx` | 深色侧栏、分组二级菜单、折叠态与移动抽屉内容。 |
| `AdminTabs.tsx` | 跟随路由创建、切换和关闭的页面标签栏。 |
| `adminNavigation.ts` | 后台菜单、图标和路由展示元数据的单一配置源，包含系统管理分组。 |

后续 `AdminShell`、导航和响应式结构文件必须在这里登记，并同步更新 `src/README.md`。
