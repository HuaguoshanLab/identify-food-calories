# Agent Feature

## 职责

`agent/` 承载用户可见的餐食分析交互。页面只呈现来自运行时 API 合约的状态；它不保存 access token、不持有 Graph State，也不计算或编造营养数值。

## 允许依赖

- 可以依赖 React、`components/ui/`、认证上下文公开的运行时请求能力，以及后续由 OpenAPI 生成的 API 文件。
- 禁止依赖后端源码、数据库、模型 Provider、LangGraph 或浏览器持久化 token。

## 文件索引

| 目录 | 职责 |
|---|---|
| `api/` | 仅保存运行时 OpenAPI 生成的公开 API 客户端与校验器。 |
| `stream/` | 认证 fetch 的 SSE 传输边界；分片由 `eventsource-parser` 处理。 |
| `components/` | 分析页的可访问 UI 组合；不拥有 Graph State 或营养计算。 |
