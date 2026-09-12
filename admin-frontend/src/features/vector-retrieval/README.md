# 向量检索管理

## 职责

管理冻结向量空间构建、聚合状态、失败任务重试与服务端准入后的显式激活。页面只显示安全计数和版本身份，不显示名称清单、向量、Provider 原文或密钥。

## 允许依赖

- React、TanStack Query、`auth/` 公开会话以及本 feature 的 `api/`。
- 禁止直接 `fetch`、Provider SDK、密钥、用户端或后端源码。

## 文件索引

| 路径 | 职责 |
| --- | --- |
| `README.md` | 能力边界与索引。 |
| `VectorRetrievalPage.tsx` | 构建、状态、重试与显式激活页面。 |
| `VectorRetrievalPage.test.tsx` | 页面安全 UX 与命令契约。 |
| `api/` | 严格 HTTP 合约。 |
