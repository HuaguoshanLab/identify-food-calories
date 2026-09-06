# Meal Records Feature

## 职责

`features/records/` 通过公开餐食记录 API 呈现已确认餐食、详情、餐次与用餐时间修改和安全删除。

## 允许依赖

- React、React Router、TanStack Query、React Hook Form、Zod、认证请求能力和现有 UI primitives。
- `api/client.ts` 的公开 `confirmMealRecord` 及其导出的餐次/时间表单合同可被 `agent` feature 调用，作为用户明确确认分析结果后的保存动作；禁止向其他 feature 暴露 records 组件或内部状态。
- 禁止后端源码、Agent run ID、Provider payload 或客户端营养计算。

## 文件索引

| 路径 | 职责 |
|---|---|
| `api/` | 安全 DTO、已保存餐食与 dashboard projection 的公开 API 请求包装；含餐次/时间表单合同；current window 只由服务端已确认统计时区决定 |
| `components/` | 记录 dashboard、详情、编辑与删除交互；Records current reads 仅在 strict same-zone confirmation 后启用，冲突零读取 |
| `format.ts` | 持久化营养 Decimal 的只读展示和本地用餐时间转换 |
| `format.test.ts` | 精度展示与本地时间转换的回归测试 |

- plans feature 可调用本模块公开 `api/client.ts` 的 `confirmDashboardTimeZone`，以统一今日计划与记录的统计时区；不共享组件或内部状态。
