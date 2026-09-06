# Diet Planning Components

## 职责

呈现符合 H5 单一滚动区合同的规划资料、目标和偏好复核，以及已验证安全快照的一日三餐结果；组件不计算营养目标、不管理长期偏好，也不伪造餐单结果。

PlanPage 的主标题和路由聚焦统一由固定 TabHeader 管理，不在内容区重复；历史入口、临时资料与调整行为保持原有所有权。

## 允许依赖

- React、React Hook Form、TanStack Query、plans API、memory 的公开只读 API、认证能力和现有 UI primitives。
- 禁止后端源码、另一个 feature 的组件、直接网络请求、localStorage 健康资料及偏好写操作。

## 文件索引

| 文件 | 职责 |
|---|---|
| `ProfileGoalForm.tsx` | 完整资料/偏好复核、显式保存意图与严格启动命令。 |
| `ProfileGoalForm.test.tsx` | 可见表单、公开请求和服务端字段错误合同。 |
| `PlanPage.tsx` | AppShell 计划根页、profile/memory 只读 Query owner 与安全快照接线。 |
| `PlanPage.test.tsx` | 预填、零静默写入、三餐受控结果和拒绝边界合同。 |
| `PlanOverview.tsx` | 四项目标区间、计划值及文本状态概览。 |
| `MealCard.tsx` | 固定餐次的标准菜名、受控份量、标签和已遵守约束。 |
| `PlanningStatus.tsx` | 六种 allowlisted 业务进度及安全错误/拒绝状态。 |
| `SafePlanningProgress.tsx` | 复用分析的阶段语义，并适配规划页面的本地安全文案。 |
| `SafePlanningProgress.test.tsx` | 规划阶段、受控重试与 SSE 边界安全测试。 |
| `PersonalProfilePage.tsx` | DetailLayout 内的资料查看、编辑、删除和唯一 memory 偏好入口。 |
| `PersonalProfilePage.test.tsx` | 资料 CRUD、不可逆删除和偏好职责分离合同。 |

| `PlanHistoryPage.tsx` | 按日期分页展示正式存档。 |
| `SavedPlanPage.tsx` | 只读版本详情、营养/三餐快照和整日删除确认。 |
| `SavedPlanPages.test.tsx` | 刷新恢复、时区确认、错误恢复、版本和删除确认。 |

PlanPage 允许调用 records 公开 `confirmDashboardTimeZone`，确认今日计划与看板采用同一统计日期。

H5第5项：PersonalProfilePage只读摘要为响应式浅绿网格，编辑表单使用白卡；全部字段与CRUD行为保留。

H5第7项：PlanPage历史入口日历/右箭头；ProfileGoalForm保留全部临时字段和可选保存，按身体资料、活动、目标、偏好白卡分组，选中使用浅绿。PlanOverview目标块、MealCard三餐分层、PlanHistoryPage图标列表、SavedPlanPage版本按钮和删除视觉统一；不改API与状态机。
