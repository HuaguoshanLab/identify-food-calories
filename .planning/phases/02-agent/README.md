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
| `02-AI-SPEC.md` | LangGraph 框架选择、官方实现模式、营养领域评测合同、护栏与生产监控策略 |
| `02-CONTEXT.md` | 已锁定的 Phase 2 产品行为、范围、权威引用与现有代码接线点 |
| `02-DISCUSSION-LOG.md` | 仅供人工审计的选项、选择与讨论记录，不供下游 Agent 消费 |
| `02-RESEARCH.md` | Phase 2 技术研究、依赖核验、数据来源、SSE 与持久化实现建议 |
| `02-PATTERNS.md` | 现有代码模式、模块边界、文件映射与新增模式约束 |
| `02-01-PLAN.md` | 供应链证据门、依赖锁与实际执行环境同步计划 |
| `02-02-PLAN.md` | PostgreSQL 测试环境、初始化启动器与 Playwright 安全链计划 |
| `02-03-PLAN.md` | Reasoning Provider DTO、端口、Fake 与测试工厂计划 |
| `02-04-PLAN.md` | Agent 前端 feature 骨架、SSE 解析依赖与逐级目录索引计划 |
| `02-05-PLAN.md` | 冻结评测数据首批主路径与版本合同计划 |
| `02-06-PLAN.md` | 营养领域模型、Repository、Service 与确定性工具计划 |
| `02-07-PLAN.md` | Agent 运行账本、事件、Graph State 与持久化基础计划 |
| `02-08-PLAN.md` | Alembic、Checkpointer、FDC 导入与幂等初始化计划 |
| `02-09-PLAN.md` | Agent API 全量哨兵合同与 OpenAPI→TS/Zod/client 漂移门计划 |
| `02-10-PLAN.md` | 登录用户文字餐食分析首个真实纵向 GREEN 计划 |
| `02-11-PLAN.md` | interrupt/resume、集中追问与同线程恢复计划 |
| `02-12-PLAN.md` | partial、排除项、定向修正与 SSE 恢复增强计划 |
| `02-13-PLAN.md` | DeepSeek Provider、运行时依赖锁与 Phoenix 可观测性计划 |
| `02-14-PLAN.md` | D-18 自动清理调度、租约与 24h/7d/30d 保留计划 |
| `02-15-PLAN.md` | 用户删除接口、UI 与候选视觉基线计划 |
| `02-16-PLAN.md` | 24-case 机器评测、专家签署结构与发布阈值计划 |
| `02-17-PLAN.md` | 专家、付费 Promptfoo 与视觉人工审批门计划 |
| `02-18-PLAN.md` | 发布报告、真实浏览器验收、教学文档与阶段索引收口计划 |
| `README.md` | 本目录职责、依赖边界与文件索引 |
