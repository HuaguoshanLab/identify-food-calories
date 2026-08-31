# Meal Records Feature

## 职责

`features/records/` 通过公开餐食记录 API 呈现已确认餐食、详情、用餐时间修改和安全删除。

## 允许依赖

- React、React Router、Zod、认证请求能力和现有 UI primitives。
- 禁止后端源码、Agent run ID、Provider payload 或客户端营养计算。

## 文件索引

| 路径 | 职责 |
|---|---|
| `api/` | 安全 DTO 与公开 API 请求包装 |
| `components/` | 记录列表、详情、编辑与删除交互 |
