# 后台运行概览

## 职责

`overview/` 只读取后端终态运行 metrics projection，并将同一 UTC 窗口交给 `/admin/runs` 深链接。它不重算百分位数、失败率或费用，也不显示运行账本原文与敏感字段。

## 允许依赖

- React Router、TanStack Query、Zod、`auth/` 的公开内存会话接口和公开 `/api/v1/admin/runs/metrics` HTTP 合约。
- 禁止导入其他 feature 的私有代码、用户 H5、后端源码、数据库、Provider SDK、密钥或敏感账本内容。

## 文件索引

| 文件 | 职责 |
| --- | --- |
| `api.ts` | 严格 Zod metrics DTO、固定 UTC 窗口和已认证 HTTP 请求。 |
| `AdminOverviewPage.tsx` | 四张指标卡及保留 UTC filters 的真实 runs Link。 |
| `AdminOverviewPage.test.tsx` | MSW 指标 DTO、严格链接和敏感 DOM 边界测试。 |
