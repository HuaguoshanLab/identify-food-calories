# Application Pages

## 职责

`app/` 保存登录后用户 H5 的页面内容组件。路由外壳由 `layouts/` 负责，认证与服务端状态继续由 `auth/` 负责；本目录不创建独立 API 请求或缓存。

## 允许依赖

- 可依赖 React、React Router、Lucide、`routePaths.ts`、`auth/` 的公开 hooks/页面组件和 `components/ui/`。
- 禁止依赖 backend 源码、数据库、服务端密钥，或绕开 `auth/` 自行请求认证/会话 API。

## 文件索引

| 文件 | 职责 |
|---|---|
| `PlaceholderTabPage.tsx` | 分析、记录、计划三个未开放 Tab 的诚实状态页。 |
| `SettingsLinkRow.tsx` | “我的”中的完整语义设置链接行。 |
| `MePage.tsx` | “我的”内容及个人资料、账号、会话、记忆入口；主标题和聚焦由固定Tab页头管理。 |
| `AccountDetailsPage.tsx` | 从 AuthProvider 权威身份映射出的只读账号资料。 |
| `SessionsDetailsPage.tsx` | 登录会话详情的组合入口，复用 `auth/SessionList` 的唯一 Query 所有权。 |
| `AppPages.test.tsx` | 应用页面组件的可见行为、语义和键盘可达性测试。 |

第5项视觉：MePage使用AuthProvider真实账号摘要与分组入口；AccountDetailsPage使用只读白卡，SettingsLinkRow保留原生链接。
