# Provider Tests

## 职责

此目录验证 `app/providers/` 的运行时校验 DTO、窄 Provider port 与 adapter 对称性。测试只使用 Fake Provider 或 HTTP mock；禁止真实模型调用。

## 允许依赖

- `app.providers.reasoning` 的公开 DTO、port、Fake 与 adapter
- pytest 与合成、去标识化 fixture loader

不允许依赖 ORM、FastAPI 路由、真实密钥、网络服务、用户餐食原文、图片、prompt、Provider body 或推理过程。

## 文件索引

- `test_weekly_review_provider_dto.py`：周复盘 Provider request/result 的严格 DTO 与 Fake 隐私边界。
