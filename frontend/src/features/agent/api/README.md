# Agent API Contract

## 职责

本目录只接收由运行时 OpenAPI 合约生成的客户端、类型和校验器。生成产物是浏览器与公开 `/api/v1` 的唯一数据接口；手写 DTO 或把 Graph State 映射进页面都不允许。

## 允许依赖

- 只能依赖运行时 OpenAPI 生成器产生的文件和公开认证请求边界。
- 禁止依赖后端源码、ORM、LangGraph State、Provider DTO 或浏览器持久化 token。

## 文件索引

当前没有生成文件。生成器与冻结 OpenAPI 工件将在后续计划接入；在那之前，组件不能伪造 API 响应。
