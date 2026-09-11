# Providers

## 职责

`providers/` 保存外部能力的 Port 与 Adapter 边界。它隔离供应商 SDK、调用协议和可替换测试替身，避免领域、API 或图编排直接绑定厂商实现。

## 允许依赖

- 可以依赖跨模块配置和各自 Provider 所需的受控 SDK。
- 不依赖 FastAPI 路由、SQLAlchemy ORM、Repository 或业务 Service。
- 子模块必须保持 Provider DTO、API Schema、Graph State 和 ORM Model 的物理分离。

## 文件索引

| 路径 | 职责 |
|---|---|
| `__init__.py` | Python 包标识 |
| `reasoning/` | 文本推理 Provider 的独立 DTO、Port、Fake 和工厂 |
| `vision/` | 图片观察 Provider 的独立 DTO、Port、Fake 和工厂；只接收安全临时引用。 |
| `embedding/` | 菜品检索 Embedding Provider 的独立 DTO、Port 和离线 Fake；只接收归一化菜品名称。 |
