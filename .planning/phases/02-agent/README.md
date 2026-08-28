# Phase 02：可追问的 Agent 核心

## 目录职责

本目录保存 Phase 2 的讨论上下文、研究、计划、执行摘要和验证证据。阶段范围是文字餐食分析、LangGraph 餐食分析子图、确定性营养工具、PostgreSQL Checkpoint、SSE 与有界恢复；图片识别、餐食保存、长期记忆和饮食规划不在本目录的实现范围内。

## 允许依赖

- 可引用 `.planning/PROJECT.md`、`.planning/REQUIREMENTS.md`、`.planning/ROADMAP.md`、`.planning/STATE.md` 和既有阶段文档。
- 可引用仓库源码、测试、官方技术文档和具有明确来源/授权的营养数据说明。
- 不得把讨论日志作为研究、规划或执行输入；下游 Agent 只消费 `02-CONTEXT.md` 及后续正式研究/计划文档。
- 不得在此目录保存密钥、原始用户餐食内容、图片、模型思维链或未脱敏 Provider 响应。

## 文件索引

| 文件 | 职责 |
|------|------|
| `02-CONTEXT.md` | 已锁定的 Phase 2 产品行为、范围、权威引用与现有代码接线点 |
| `02-DISCUSSION-LOG.md` | 仅供人工审计的选项、选择与讨论记录，不供下游 Agent 消费 |
| `README.md` | 本目录职责、依赖边界与文件索引 |
