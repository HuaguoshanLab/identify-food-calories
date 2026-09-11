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
| `dashscope.py` | 唯一具体 HTTP Adapter；固定 HTTPS Endpoint、模型、维度和 1.5 秒超时，响应只映射为安全 DTO/错误码。 |
| `factory.py` | 只从受验证的 Settings 选择 Fake、禁用的文本降级或生产 DashScope Adapter。 |

`dashscope.py` 可以依赖 HTTPX、配置和本目录 DTO；`factory.py` 是唯一允许导入具体 Adapter 的模块。两者均不得依赖 API、Repository、Service、Agent State 或请求级 Endpoint 配置。
