# Reasoning Provider

## 职责

`reasoning/` 定义文本推理模型的窄异步 Port、独立 Pydantic DTO、确定性 Fake 和 Provider 选择工厂。它将供应商响应限制为餐食解析/修正观察，不能提供热量、蛋白质、脂肪或碳水真值。

## 运行时供应链说明

生产可观测性固定使用经实测可导入的 `arize-phoenix==18.1.0`。`20.3.0` 与官方候选 `20.4.0` 虽满足 FastAPI 元数据约束，却都在当前 Python 3.11 的实际 `import phoenix` 触发内部 mutable-default dataclass 错误，不能上线；完整证据、registry 响应哈希与批准理由在 `backend/supply-chain-evidence.json`。

## 允许依赖

- 可以依赖 Pydantic、HTTPX、`app.core.config` 与 Python 标准库。
- 可以被后续 Agent 图节点依赖。
- 不依赖 FastAPI API Schema、SQLAlchemy ORM、Repository、营养 Service 或 LangGraph State。

## 文件索引

| 文件 | 职责 |
|---|---|
| `__init__.py` | Python 包标识 |
| `dto.py` | extra-forbid Provider 输入、输出、用量和安全错误 DTO |
| `ports.py` | `ReasoningModelProvider` 异步协议 |
| `fake.py` | 无网络的可编程结果、错误、用量与安全调用轨迹 |
| `factory.py` | test 强制 Fake、production DeepSeek fail-closed 选择 |
| `deepseek.py` | `/responses` JSON Schema adapter；仅记录安全调用元数据，未知结果绝不重发 |
