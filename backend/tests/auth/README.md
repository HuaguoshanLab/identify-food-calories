# Auth Tests

## 职责

`tests/auth/` 验证认证应用协议与 HTTP 合约，包括注册、邮箱验证码、登录、会话和安全错误映射。

## 允许依赖

- Service 测试只使用 fake repository、fake provider 和可控时钟，不连接数据库或网络。
- API 合约测试可以使用 FastAPI TestClient；持久化证据必须连接隔离的真实 PostgreSQL。
- 禁止断言或输出密码、验证码摘要、明文验证码和令牌。

## 文件索引

| 文件 | 职责 |
|---|---|
| `test_registration_verification.py` | 注册与邮箱验证码策略、Provider 注入和 HTTP 合约证据 |
| `test_login_me_service.py` | 登录、最小 access claims、opaque refresh 摘要与数据库权威身份的 Service 证据 |
| `test_login_me_api.py` | login Cookie、Bearer 失败、真实 PostgreSQL `/users/me` 与 OpenAPI 证据 |
| `test_login_rate_limit_service.py` | HMAC bucket、可控时钟、失败阈值与成功复位的 Service 合约证据 |
