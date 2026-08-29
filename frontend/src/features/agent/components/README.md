# Agent Components

## 职责

本目录保存 Agent feature 的用户可见组件。组件只渲染认证公开 API 返回的权威快照，不能用示例报告、静态营养数字或伪造成功结果替代真实响应；事件流只更新进度，不能拼装报告。

## 允许依赖

- 可以依赖 React 和 `src/components/ui/` 的基础组件。
- 禁止直接调用后端内部代码、存储认证 token、持有 LangGraph State 或进行营养计算。

## 文件索引

| 文件 | 职责 |
|---|---|
| `AnalyzePage.tsx` | 受保护分析 Tab 的文字输入、集中追问、partial 披露、权威快照报告、定向修正与 URL thread 恢复。 |
| `AnalyzePage.test.tsx` | 输入校验、集中候选不自动选择与权威快照行为测试。 |
