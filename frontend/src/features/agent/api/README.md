# Agent API Contract

## 职责

本目录只接收由运行时 OpenAPI 合约生成的客户端、类型和校验器。生成产物是浏览器与公开 `/api/v1` 的唯一数据接口；手写 DTO 或把 Graph State 映射进页面都不允许。每次后端 Agent schema 变化后必须先运行 `node generate-contracts.mjs generate-all`，再运行 `check-all`；后者会从真实 `create_app().openapi()` 在临时目录逐字重建所有工件。

## 允许依赖

- 只能依赖运行时 OpenAPI 生成器产生的文件和公开认证请求边界。
- 禁止依赖后端源码、ORM、LangGraph State、Provider DTO 或浏览器持久化 token。

## 文件索引

| 文件 | 职责 |
|---|---|
| `generate-contracts.mjs` | 唯一的运行时 OpenAPI → frozen JSON → TypeScript/Zod → operation client 生成与逐字漂移检查入口；JSON 与 multipart 图片上传均从 contract 推导。 |
| `schemas.generated.ts` | 从 OpenAPI schema 生成的 TypeScript 声明与 Zod runtime validator；禁止手改 |
| `client.generated.ts` | 从 operationId 生成、接收 AuthProvider 的运行时 request 后访问公开 Agent API 的客户端；含空图片线程和 multipart 上传操作，禁止手改 |
| `stream.ts` | 版本化安全 SSE 阶段的严格 Zod 边界；拒绝未知字段和原始 payload。 |
