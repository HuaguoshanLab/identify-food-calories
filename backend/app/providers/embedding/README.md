# Embedding Provider

## 职责

`embedding/` 为受控菜品检索提供严格、可替换的向量 Provider 边界。请求只允许已归一化的菜品名称；它不接收餐食、份量、身份、身体、健康或对话上下文。

## 允许依赖

- 可以依赖 Pydantic 和共同的安全 Provider 错误类型。
- 不依赖 FastAPI、SQLAlchemy、营养 Schema、Agent State、Repository、业务 Service 或具体网络 Adapter。
- Fake 必须离线运行，调用记录不得保留输入名称或向量。

## 文件索引

| 文件 | 职责 |
| --- | --- |
| `__init__.py` | Python 包边界。 |
| `dto.py` | 冻结的请求、结果、使用量与 1024 维有限浮点校验契约。 |
| `ports.py` | 应用层可依赖的窄异步 `EmbeddingProvider` Protocol。 |
| `fake.py` | 支持可脚本化成功和安全失败的零网络替身。 |
