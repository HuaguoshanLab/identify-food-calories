# Agent Event Stream

## 职责

本目录约束 Agent 事件流传输。未来必须使用认证后的 `fetch`，将解码后的每个响应 chunk 交给 `eventsource-parser` 处理分片 `event`、`data` 与 `id` 边界；禁止 `EventSource`、按换行手写切分，或在传输层拼装分析报告。

服务端权威快照始终优先于重放事件。传输层只转发版本化事件，不能保存 Graph State 或营养计算结果。

## 允许依赖

- 可以依赖 React 生命周期、认证上下文的运行时请求能力和 `eventsource-parser`。
- 禁止依赖后端源码、数据库、Provider、LangGraph State、localStorage/sessionStorage token 或手写 SSE parser。

## 文件索引

| 文件 | 职责 |
|---|---|
| `useAgentEventStream.ts` | 认证 fetch SSE 重放、分片解析和取消边界；不拼装报告。 |
