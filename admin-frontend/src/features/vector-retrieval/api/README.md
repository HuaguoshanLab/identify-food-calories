# 向量检索 HTTP 合约

## 职责

严格校验 `/api/v1/admin/catalog-search-index-backfills` 与 `/api/v1/admin/vector-space-builds*` 的安全投影和命令响应。令牌仅由调用方内存传入。

## 允许依赖

- Zod、浏览器 `fetch`、构建时后台 API base。
- 禁止 React、Provider SDK、密钥、数据库或令牌持久化。

## 文件索引

| 路径 | 职责 |
| --- | --- |
| `index.ts` | 检索名称回填、构建列表、创建、失败重试与激活请求。 |
