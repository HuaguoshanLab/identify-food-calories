---
phase: 02-agent
plan: 03
subsystem: provider
tags: [pydantic, async-protocol, fake-provider, deepseek, fail-closed]
requires:
  - phase: 01-engineering-auth-foundation
    provides: "Pydantic Settings、后端目录 README 合同和测试基础设施"
provides:
  - "独立的 Reasoning Provider DTO、async Port 和无网络 Fake"
  - "test 强制 Fake 与 production DeepSeek fail-closed 选择边界"
  - "Provider DTO、API Schema、Graph State 与 ORM 的物理分离合同"
affects: [agent-graph, agent-runs, provider-adapter, evaluation]
tech-stack:
  added: []
  patterns: ["Provider port + programmable Fake", "Provider-only Pydantic DTO", "production provider fail-closed"]
key-files:
  created:
    - backend/app/providers/reasoning/dto.py
    - backend/app/providers/reasoning/ports.py
    - backend/app/providers/reasoning/fake.py
    - backend/app/providers/reasoning/factory.py
  modified:
    - backend/app/core/config.py
    - backend/app/README.md
    - backend/tests/test_reasoning_provider.py
key-decisions:
  - "测试环境无条件选择 Fake，避免付费模型和网络副作用。"
  - "生产只接受显式 DeepSeek；真实 adapter 未装配时启动失败而非回退 Fake。"
  - "Fake 轨迹只保存调用、token、费用和延迟，不保存用户原文或模型正文。"
patterns-established:
  - "后续图节点只依赖 ReasoningModelProvider Protocol，不能导入供应商 SDK。"
  - "Provider DTO 仅描述解析/修正观察，不能携带权威营养数值。"
requirements-completed: [AGT-02, AGT-06, AGT-07, ARC-06]
duration: 18min
completed: 2026-08-29
---

# Phase 02 Plan 03: Provider 边界 Summary

**独立的推理模型 DTO、异步 Port 和零网络 Fake，配合 test 强制替身与 production DeepSeek fail-closed 配置。**

## Performance

- **Duration:** 18 min
- **Completed:** 2026-08-29
- **Tasks:** 2/2
- **Files modified:** 11

## Accomplishments

- 定义 extra-forbid 的 Provider 请求、解析/修正结果、用量、元数据及三类稳定失败 DTO。
- 提供可脚本化成功、瞬时、永久和未知结果的 Fake，并记录不含正文的调用/费用/延迟轨迹。
- 在测试环境强制 Fake；生产环境要求显式 DeepSeek 与密钥，真实 adapter 未加入前直接 fail closed。
- 新建 Provider 目录自文档并同步 `app/` 父索引。

## Task Commits

1. **Task 1: 定义独立 Provider 合同与 Fake (RED)** — `69e50b5` (`test`)
2. **Task 1: 定义独立 Provider 合同与 Fake (GREEN)，Task 2: 目录 README 与父索引** — `43e7670` (`feat`)

## Files Created/Modified

- `backend/app/providers/reasoning/dto.py` — Provider 专属运行时 DTO、用量和安全错误分类。
- `backend/app/providers/reasoning/ports.py` — async `ReasoningModelProvider` Protocol。
- `backend/app/providers/reasoning/fake.py` — 无网络、可编程并可审计的测试替身。
- `backend/app/providers/reasoning/factory.py` — 环境受控 Provider 选择与 fail-closed 行为。
- `backend/app/core/config.py` — 生产环境 Provider mode 和 DeepSeek 密钥验证。
- `backend/tests/test_reasoning_provider.py` — Fake、配置与无敏感轨迹合同测试。
- `backend/app/providers/README.md`、`backend/app/providers/reasoning/README.md`、`backend/app/README.md` — 目录职责、允许依赖与索引。

## Decisions Made

- 费用值用 `Decimal` 保持精度；Fake 调用轨迹只暴露安全元数据。
- 输入 DTO 可以承载瞬时用户文本，但 ledger/Fake trace 不保存该文本。
- 没有真实 DeepSeek adapter 时，production 不能以 Fake 或隐式默认值继续启动。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] TDD 测试文件与目录文档同提交约束**
- **Found during:** Task 1
- **Issue:** 计划标记 TDD 但遗漏测试文件；同时将 README 设为 Task 2 会使新 Python 目录在 Task 1 提交中违反项目“新增目录同提交 README 和父索引”硬约束。
- **Fix:** 新增根级 `backend/tests/test_reasoning_provider.py` 完成 RED/GREEN；将两级 README 与父索引纳入 GREEN 提交。
- **Files modified:** `backend/tests/test_reasoning_provider.py`, `backend/app/providers/**`, `backend/app/README.md`
- **Verification:** Provider 测试、mypy、ruff 与目录合同测试通过。
- **Committed in:** `69e50b5`, `43e7670`

**Total deviations:** 1 auto-fixed (1 missing critical correctness/documentation contract)

## Issues Encountered

- Pydantic 将 `model_validator` 中的 `ConfigurationError` 包装为 `ValidationError`；测试按现有配置测试模式同时断言两者。
- Fake 队列初版的 union 返回值不满足 mypy；拆分 parse/correction 出队函数后通过严格检查。

## Known Stubs

None. 真实 DeepSeek adapter 是后续计划明确交付物，当前 production fail-closed，未伪造可用能力。

## User Setup Required

None - 本计划未安装外部依赖，也未启用真实模型调用。

## Next Phase Readiness

后续 Agent 图可以仅依赖 `ReasoningModelProvider`，使用 Fake 覆盖所有确定性路径。真实 DeepSeek adapter 接入前，production 启动将刻意拒绝继续，防止隐式模型降级。

## Self-Check: PASSED

- Provider DTO、Port、Fake、factory 和两级 README 均存在。
- TDD RED `69e50b5` 与 GREEN `43e7670` 均存在于提交历史。

*Phase: 02-agent*
*Completed: 2026-08-29*
