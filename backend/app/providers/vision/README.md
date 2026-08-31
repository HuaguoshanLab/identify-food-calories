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
| `qwen.py` | Qwen-VL 的 OpenAI 兼容 HTTP adapter；仅发送已验证的临时图片，强制 JSON 输出、非 thinking 模式、受限重试和人民币分档计量。 |

## Qwen 生产配置

只有在人工核实 Model Studio 的区域、业务空间、模型可用性和数据处理条款后，生产环境才可设置 `VISION_PROVIDER_MODE=qwen`。`QWEN_API_KEY` 只能保留在未提交的环境变量中；测试环境始终使用 Fake Provider。

`QWEN_BASE_URL` 是业务空间的 OpenAI compatible Base URL，adapter 在内存中追加 `/chat/completions`。价格以当前已核实的人民币每百万 Tokens 分档写入 `QWEN_UP_TO_*_CNY_PER_M`，调用记录只保存估算成本、受控用量和 provider request id，不保存图片、base64、prompt 或模型原文。
