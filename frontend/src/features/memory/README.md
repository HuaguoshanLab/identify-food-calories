# Long-term Memory Feature

## 职责

`features/memory/` 展示和管理会影响后续建议的长期偏好，且绝不显示外部 ID、向量或对话原文。

## 允许依赖

- React、React Router、Zod、认证请求能力和现有 UI primitives。
- 禁止后台源码、Mem0/pgvector 实现、provider score 与内部同步状态。
- `plans` feature 只能调用公开只读 `listMemories` 生成复核摘要；计划页不得调用 memory 写入接口或渲染第二个偏好编辑器。

## 文件索引

| 路径 | 职责 |
|---|---|
| `api/` | 安全记忆 DTO 与公开 API 请求包装 |
| `components/` | 记忆管理与编辑页面 |
