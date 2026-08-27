# Accounts Module

## 职责

`accounts/` 提供账户恢复用例。它只编排密码重置、验证码挑战与会话撤销，不承载 HTTP 或 SMTP 细节。

## 允许依赖

- API 只调用本模块的 Service。
- Service 只依赖本模块 Port、`auth` 的模型/密码安全函数与 `notifications.MailProvider`。
- Repository 可以依赖 SQLAlchemy 模型，但不得依赖 FastAPI 或具体邮件实现。

## 文件索引

| 文件 | 职责 |
|---|---|
| `schemas.py` | 恢复 API 的运行时输入输出契约 |
| `ports.py` | 恢复持久化与会话撤销能力边界 |
| `repository.py` | SQLAlchemy 恢复数据 adapter |
| `service.py` | 恢复协议及事务边界 |
| `api.py` | 恢复 HTTP 路由与 HttpOnly context cookie |
