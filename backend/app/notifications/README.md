# Notifications Module

## 职责

`notifications/` 隔离应用服务与邮件传输。应用层只依赖 `MailProvider`，SMTP/Mailpit 是可替换基础设施 adapter。

## 允许依赖

- `ports.py` 只依赖标准库类型，不得依赖 FastAPI、SQLAlchemy 或具体 SMTP 实现。
- `smtp.py` 可以依赖标准库 SMTP/email 和已校验 Settings；不得包含认证业务规则。
- 邮件正文可以包含一次性验证码，但不得记录验证码、密码、令牌或完整 provider 凭据。

## 文件索引

| 文件 | 职责 |
|---|---|
| `__init__.py` | Notifications Python 包标识 |
| `ports.py` | 应用服务依赖的 `MailProvider` Protocol |
| `smtp.py` | 本地 Mailpit/生产 SMTP adapter 与配置装配 |
