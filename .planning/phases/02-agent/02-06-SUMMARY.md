---
phase: 02-agent
plan: 06
subsystem: nutrition-domain
tags: [pydantic, sqlalchemy, decimal, deterministic-tools, fake-repository]
requires:
  - phase: 01-engineering-auth-foundation
    provides: "共享 SQLAlchemy Base、Service/Repository 分层和 Python 测试门禁"
  - phase: 02-agent
    provides: "已批准的 Python runtime lock 与受保护测试环境"
provides:
  - "独立的营养 catalog DTO、Repository Port、ORM adapter 和确定性 Service"
  - "不依赖数据库的 fake-repository nutrition 单元测试"
affects: [agent-graph, catalog-importer, agent-api, evaluation]
tech-stack:
  added: []
  patterns: ["Qualified catalog port", "Decimal-only nutrition truth", "closed deterministic validation actions"]
key-files:
  created:
    - backend/app/nutrition/schemas.py
    - backend/app/nutrition/ports.py
    - backend/app/nutrition/models.py
    - backend/app/nutrition/repository.py
    - backend/app/nutrition/service.py
    - backend/tests/unit/test_nutrition.py
  modified:
    - backend/app/README.md
    - backend/tests/unit/README.md
key-decisions:
  - "营养工具仅接受已资格化、带来源/授权/版本的 DTO，null 营养绝不补零。"
  - "计算与校验使用未舍入 Decimal；展示层才允许按产品规则舍入。"
  - "Graph 未来只能调用三个 Service 工具方法，不能导入 nutrition ORM 或 Repository。"
patterns-established:
  - "Service 依赖窄 Protocol，SQLAlchemy adapter 只查询并 flush，不拥有事务。"
  - "校验路由只消费 RECALCULATE/ASK/BLOCK/WARN/PASS 枚举，模型不能覆盖。"
requirements-completed: [AGT-06, NUT-01, NUT-02, NUT-03, NUT-04, NUT-05, ARC-06, QLT-02]
duration: 11min
completed: 2026-08-29
---

# Phase 02 Plan 06: 确定性 Nutrition Domain Summary

**受控、可追溯目录通过 Repository Port 提供给纯 Decimal 计算与封闭校验动作，模型和 Graph 无法成为营养数值来源。**

## Performance

- **Duration:** 11 min
- **Completed:** 2026-08-29T04:22:08Z
- **Tasks:** 2/2
- **Files modified:** 12

## Accomplishments

- 建立 Pydantic DTO、共享 SQLAlchemy Base 的 catalog/alias/portion ORM、窄 Repository Protocol 和 flush-only adapter；Repository 只返回具备资格的数据。
- 实现 `search_food_catalog`、`calculate_nutrition`、`validate_nutrition_result`：唯一受控别名才自动匹配，候选最多 3 个，未审计份量要求追问，按 `per100g × grams / 100` 使用未舍入 Decimal 计算。
- 将负值、密度、份量、总量和来源能量差映射为 `RECALCULATE`、`ASK`、`BLOCK`、`WARN` 或 `PASS`；没有模型输入能改变该裁决。
- 用纯内存 fake repository 锁定查询、null 不补零、精度、边界输入和所有校验动作。

## Task Commits

1. **Task 1: 实现确定性 Nutrition Service** — `bc9fc55` (`feat`)
2. **Task 2: 用 fake repository 锁定营养真值并索引模块** — `cc2a0ac` (`test`)

## Files Created/Modified

- `backend/app/nutrition/schemas.py` — 独立运行时 DTO、目录/计算规则版本和封闭 action。
- `backend/app/nutrition/{ports,models,repository,service}.py` — 分层 catalog 边界、ORM 与确定性三个工具方法。
- `backend/tests/unit/test_nutrition.py` — 不连接 PostgreSQL 的 fake-repository 证据。
- `backend/app/README.md`、`backend/app/nutrition/README.md`、`backend/tests/unit/README.md` — 模块职责、允许依赖和文件索引。

## Decisions Made

- 只有大小写与空白规范化可参与自动映射；拼写、语义或模型猜测一律不能选中 catalog 条目。
- 未审计家庭份量不转克数；用户必须提供克数或选择目录中精确受控且审计过的份量。
- `WARN` 保留来源能量值，`RECALCULATE` 处理内部总量不一致，`BLOCK` 禁止最终报告。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] 首个 nutrition 提交同步建立目录合同与未审计份量分支**

- **Found during:** Task 1
- **Issue:** 计划把 `nutrition/README.md` 放在 Task 2，但 Task 1 已创建 `nutrition/`，会违反新目录必须同次提交 README 与父级索引的硬约束；此外原始计算输入无法表达受控份量，不能证明“未审计份量必须 ASK”。
- **Fix:** Task 1 同步创建 nutrition README 与更新 `app/README.md`；为 `NutritionCalculationInput` 增加可选 `portion_description`，只接受唯一且 `audited` 的 food-specific portion，其他情况返回 `ASK`。
- **Files modified:** `backend/app/nutrition/README.md`, `backend/app/README.md`, `backend/app/nutrition/schemas.py`, `backend/app/nutrition/service.py`
- **Verification:** nutrition 单测覆盖缺失与未审计份量；mypy、ruff 和目录合同测试通过。
- **Committed in:** `bc9fc55`, `cc2a0ac`

**Total deviations:** 1 auto-fixed（Rule 2）。
**Impact on plan:** 为项目目录合同和 D-01 份量安全所必需，没有新增产品范围。

## Issues Encountered

None.

## Known Stubs

None. ORM 表的 Alembic migration、离线 FDC seed 与真实 PostgreSQL importer 已明确留给 02-05/02-08；当前没有伪造数据源或可用 catalog。

## Threat Flags

None. 本计划没有新增网络端点、认证路径、文件访问或跨信任边界 schema 迁移。

## User Setup Required

None - 没有新增外部依赖、密钥或账户。

## Next Phase Readiness

- 02-05 可以从 nutrition ORM 的单一 metadata 真相创建 `0004_agent_core` migration。
- 02-08 可以通过 Repository adapter 导入并查询离线、版本化 FDC seed；Graph 只需持有 `NutritionService`，不能直接导入 ORM。

## Verification

- `validate_supply_chain.py verify`：PASS
- `lock_dependencies.py check`：PASS
- `pytest tests/unit/test_nutrition.py tests/unit/test_supply_chain.py tests/architecture/test_directory_contract.py -q`：29 passed
- `mypy app`、`ruff check app tests/unit/test_nutrition.py`：PASS

## Self-Check: PASSED

- `backend/app/nutrition/service.py`、`backend/tests/unit/test_nutrition.py` 与本 Summary 均已确认存在。
- `bc9fc55`、`cc2a0ac` 均存在于 Git 历史。

*Phase: 02-agent*
*Completed: 2026-08-29*
