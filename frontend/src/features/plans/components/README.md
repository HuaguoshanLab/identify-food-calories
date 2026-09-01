# Diet Planning Components

## 职责

呈现符合 H5 单一滚动区合同的规划资料、目标和偏好复核交互；组件不计算营养目标、不管理长期偏好，也不伪造餐单结果。

## 允许依赖

- React、React Hook Form、TanStack Query、plans API、memory 的公开只读 API、认证能力和现有 UI primitives。
- 禁止后端源码、另一个 feature 的组件、直接网络请求、localStorage 健康资料及偏好写操作。

## 文件索引

| 文件 | 职责 |
|---|---|
| `ProfileGoalForm.tsx` | 完整资料/偏好复核、显式保存意图与严格启动命令。 |
| `ProfileGoalForm.test.tsx` | 可见表单、公开请求和服务端字段错误合同。 |
