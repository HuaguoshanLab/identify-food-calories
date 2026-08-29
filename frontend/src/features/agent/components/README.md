# Agent Components

## 职责

本目录保存 Agent feature 的用户可见组件。组件通过明确的状态呈现后端是否可用，不能用示例报告、静态营养数字或伪造成功结果替代真实响应。

## 允许依赖

- 可以依赖 React 和 `src/components/ui/` 的基础组件。
- 禁止直接调用后端内部代码、存储认证 token、持有 LangGraph State 或进行营养计算。

## 文件索引

| 文件 | 职责 |
|---|---|
| `AnalyzePage.tsx` | 受保护分析 Tab 的文字输入与诚实状态壳。 |
| `AnalyzePage.test.tsx` | 输入校验、提交状态和未接通状态的行为测试。 |
