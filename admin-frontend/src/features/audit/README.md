# 后台操作审计功能

## 职责

`audit/` 只负责呈现后端返回的最小化、只读审计证据。它不会请求 API、拼接可信 diff 或保存操作内容；所有请求与 Zod 校验仍归触发该能力的 feature API 边界所有。

## 允许依赖

- 可依赖 React、语义 HTML、所属调用方传入的严格校验后的审计 DTO。
- 禁止请求 `/api/v1/admin/*`、读取 access token、导入后端、用户 H5、数据库、Provider SDK 或密钥。

## 文件索引

| 路径 | 职责 |
| --- | --- |
| `README.md` | 只读审计展示的边界、允许依赖与索引。 |
| `AuditTimeline.tsx` | 安全字段白名单过滤后的可访问审计时间线。 |
