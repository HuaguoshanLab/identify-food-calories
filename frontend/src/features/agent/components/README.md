# Agent Components

## 职责

本目录保存 Agent feature 的用户可见组件。组件只渲染认证公开 API 返回的权威快照，不能用示例报告、静态营养数字或伪造成功结果替代真实响应；事件流只更新进度，不能拼装报告。

## 允许依赖

- 可以依赖 React 和 `src/components/ui/` 的基础组件。
- 禁止直接调用后端内部代码、存储认证 token、持有 LangGraph State 或进行营养计算。

## 文件索引

| 文件 | 职责 |
|---|---|
| `AnalyzePage.tsx` | 受保护分析 Tab 的拍照/相册 multipart 上传、隐私说明、文字降级、集中追问、估算与 partial 披露、权威快照报告、定向修正和 URL thread 恢复；不持久化图片或 token。 |
| `AnalyzePage.test.tsx` | 图片本地校验、multipart 合约、估算披露、输入校验、候选选择、中文展示、带单位重量原样提交、错误后保留输入及文字/图片错误区分测试。 |
| `SafeProgressStages.tsx` | 本地 allowlist 的五阶段进度语义和受控重试入口，不渲染 SSE 原文。 |
| `SafeProgressStages.test.tsx` | 阶段、无障碍播报与 SSE 边界安全测试。 |
