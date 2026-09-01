# Diet Planning Feature

## 职责

`features/plans/` 负责饮食规划的瞬时资料复核、已确认偏好摘要、公开启动命令与后续安全餐单展示。身体资料的持久化只能通过用户本次明确选择交由服务端处理；忌口与口味仍只在 `features/memory/` 管理。

## 允许依赖

- React、React Hook Form、Zod、TanStack Query、认证请求能力和现有 UI primitives。
- 可读取 `memory/api/client.ts` 的公开只读记忆摘要；不得导入 memory 组件、内部状态或写入接口。
- 禁止后端源码、客户端目标计算、浏览器持久化健康资料、Provider/Graph 状态与第二个偏好编辑器。

## 文件索引

| 路径 | 职责 |
|---|---|
| `api/` | 严格公开 DTO、资料预填读取与 Agent 启动请求。 |
| `components/` | 资料、目标与已确认偏好的 H5 复核，以及安全三餐结果呈现。 |
| `format.ts` | 规划目标范围、计划值与文本状态的安全展示格式化。 |
