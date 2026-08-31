# Vision Provider

## 职责

`vision/` 将安全图片临时引用转换为经过 Pydantic 验证的多菜视觉观察。它不产生营养数值，不接触 API Schema、ORM 或 LangGraph State。

## 允许依赖

- 可以依赖 `app.images` 的 `ValidatedImageReference`、核心配置、HTTP client 和共同的安全 Provider 错误类型。
- 不依赖 FastAPI、SQLAlchemy、Agent 图、营养 Service 或公开 API Schema。
- 只接收已经验证的临时引用；trace、DTO 和异常不得含图片 bytes、base64、原文件名、EXIF 或模型原文。

## 文件索引

| 文件 | 职责 |
| --- | --- |
| `dto.py` | 独立的视觉请求、观察、使用量与 metadata 契约。 |
| `ports.py` | 图可依赖的窄异步 Protocol。 |
| `fake.py` | 可脚本化成功、结构无效和安全失败的离线替身。 |
| `factory.py` | test 强制 Fake、production fail-closed 的 Provider 选择。 |
