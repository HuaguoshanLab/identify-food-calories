# Diet Planning Components

## 职责

呈现符合 H5 单一滚动区合同的规划资料、目标和偏好复核，以及已验证安全快照的一日三餐结果；组件不计算营养目标、不管理长期偏好，也不伪造餐单结果。

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
| `PersonalProfilePage.tsx` | DetailLayout 内的资料查看、编辑、删除和唯一 memory 偏好入口。 |
| `PersonalProfilePage.test.tsx` | 资料 CRUD、不可逆删除和偏好职责分离合同。 |
