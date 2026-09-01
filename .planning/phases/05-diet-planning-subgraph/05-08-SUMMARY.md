---
phase: 05-diet-planning-subgraph
plan: "08"
subsystem: planning
tags: [python, sqlalchemy, alembic, pydantic, postgresql, nutrition]
requires:
  - phase: 05-01
    provides: Versioned planning DTOs, deterministic target policy, and planning ports.
  - phase: 05-07
    provides: Owner-scoped planning persistence and the planning ORM/repository conventions.
provides:
  - Auditable project-authored controlled-recipe schema and seed metadata.
  - Qualified-catalog-only recipe activation query and per-ingredient Decimal recomputation.
  - Safe D-08 three-meal DTOs with controlled portions and short constraint summaries.
affects: [05-diet-planning-subgraph, agent-tools, planning-graph, planning-ui]
tech-stack:
  added: []
  patterns: [R-03 recipe audit chain, qualified ingredient references, deterministic nutrition recomputation]
key-files:
  created:
    - backend/app/planning/data/controlled-recipes.v1.json
    - backend/app/planning/data/README.md
    - backend/migrations/versions/0011_controlled_recipes.py
  modified:
    - backend/app/planning/schemas.py
    - backend/app/planning/repository.py
    - backend/app/planning/service.py
key-decisions:
  - "受控菜谱不保存或返回营养总计；每个固定克数食材均通过 NutritionService 重新计算。"
  - "recipe 激活同时检查项目自有来源、固定许可、审核证据、catalog version 与所有 ingredient 的 qualified 映射。"
patterns-established:
  - "R-03: seed、DTO、ORM/migration 和 repository active query 四层重复强制菜谱资格。"
  - "D-08: H5 只消费标准名、受控份量、短标签、约束摘要和重算营养，不接触来源或许可元数据。"
requirements-completed: [PLN-02, PLN-03, PLN-04]
duration: 10min
completed: 2026-09-01
---

# Phase 5 Plan 08: 审核、许可明确且可重算的受控菜谱 Summary

**项目自有、审核可追溯的三餐菜谱通过合格营养目录和固定克数重新计算，杜绝把 recipe 总计或未授权内容当作数值真相。**

## Performance

- **Duration:** 10 min
- **Started:** 2026-09-01T07:54:54Z
- **Completed:** 2026-09-01T08:04:54Z
- **Tasks:** 2/2
- **Files modified:** 11

## Accomplishments

- 用 RED 合同覆盖 R-03 许可/审核/版本/份量与 catalog 资格的所有拒绝入口，并固定早餐、午餐、晚餐 D-08 字段与目录重算行为。
- 新增 `controlled_recipes` 和 `controlled_recipe_ingredients` PostgreSQL schema：食材只有 food catalog reference 与 grams，没有可被误用的持久化营养总计。
- Repository 仅激活 project-authored、固定 license、approved audit 且每个 ingredient 都映射到相同 qualified catalog version 的 recipe；Service 对每种食材调用 `calculate_nutrition`。
- 添加只含项目自有短标签的三餐 seed，明确禁止第三方正文、图片、长步骤和购物清单。

## Task Commits

Each task was committed atomically:

1. **Task 1: 写 D-08/R-03 资格、重算和三餐组合的 RED 合同** — `78ec1a8` (`test`)
2. **Task 2: 实现审核 seed、recipe 存储与确定性候选查询** — `5c4adfa` (`feat`)

## Files Created/Modified

- `backend/app/planning/data/controlled-recipes.v1.json`、`data/README.md` — 项目自有、可审计且无第三方正文的三餐短 seed。
- `backend/app/planning/{schemas.py,ports.py,service.py}` — R-03 DTO、D-08 安全 meal card、窄计算 port 和逐食材营养重算。
- `backend/app/planning/{models.py,repository.py}`、`backend/migrations/versions/0011_controlled_recipes.py` — recipe/ingredient schema、active query 及 qualified catalog 链。
- `backend/tests/planning/test_planning_service.py` — Fake catalog 下的元数据拒绝、version/grams 拒绝和三餐重算证据。

## Decisions Made

- 受控 recipe 的 provenance/audit 只在后端保存和筛选；D-08 public DTO 不泄露 source reference 或 license。
- `catalog_version` 必须同时在 recipe、ingredient、catalog version row 与 qualified food row 对齐，任何一环不合格都会移出候选。

## Verification

- `cd backend && uv run pytest tests/planning/test_planning_service.py -q` — passed (38 passed)。
- `cd backend && uv run ruff check app/planning tests/planning/test_planning_service.py` — passed。
- `cd backend && uv run mypy app/planning` — passed (7 source files)。
- `cd backend && uv run alembic upgrade head` — passed（升级 `0010 -> 0011`）。
- `controlled-recipes.v1.json` 通过 Python JSON 解析验证。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 修正组合循环返回 recipe 而非安全 meal DTO**
- **Found during:** Task 2（实现审核 seed、recipe 存储与确定性候选查询）
- **Issue:** 首次实现的 generator 返回 `ControlledRecipe`，导致 `MealCompositionResult` 的 `PlannedMeal` 运行时校验失败。
- **Fix:** 组合循环改为只收集成功重算后生成的 `PlannedMeal`。
- **Files modified:** `backend/app/planning/service.py`
- **Verification:** 38 个 planning service 测试通过。
- **Committed in:** `5c4adfa`（part of task commit）

**2. [Rule 2 - Missing Critical Functionality] 补齐严格 DTO、计算 port 与父目录索引**
- **Found during:** Task 2（实现审核 seed、recipe 存储与确定性候选查询）
- **Issue:** 计划文件列表未列出承载 R-03 ingredient 和 D-08 response 的 `schemas.py`、接入真实 `calculate_nutrition` 的 `ports.py`，也未列出 migration parent README；不补齐会让 recipe audit chain 只能靠松散对象或违反目录文档硬约束。
- **Fix:** 扩展闭合 DTO/Protocol，并更新 migration 索引。
- **Files modified:** `backend/app/planning/{schemas.py,ports.py}`、`backend/migrations/versions/README.md`
- **Verification:** mypy、ruff、规划测试和 Alembic upgrade 均通过。
- **Committed in:** `5c4adfa`（part of task commit）

**3. [Rule 1 - Bug] 清理 RED 测试中的无用 import**
- **Found during:** Task 2（静态检查）
- **Issue:** 新 RED fixture 遗留无用 `NutritionAction` import，导致 ruff 失败。
- **Fix:** 删除无用 import。
- **Files modified:** `backend/tests/planning/test_planning_service.py`
- **Verification:** ruff passed。
- **Committed in:** `5c4adfa`（part of task commit）

---

**Total deviations:** 3 auto-fixed（Rule 1: 2；Rule 2: 1）。
**Impact on plan:** 修复均为 DTO 正确性、静态门禁或项目目录合同所必需；未扩张业务范围。

## Issues Encountered

- 受限沙箱不能访问用户级 uv cache；获准使用本机缓存后，测试、静态检查和迁移均正常完成。

## Known Stubs

None — 新增和修改文件未发现流向 UI 的空数据、占位文案或 mock 数据源。受控 seed 已完整给出三餐短 metadata。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

后续 planning graph/tool 只需通过 `SqlAlchemyPlanningProfileRepository.list_controlled_recipes` 和 `PlanningNutritionPort.calculate_nutrition` 获取合格候选；不得直接读 ORM、recipe seed 或任意持久化总计。

## Self-Check: PASSED

- 已确认 `backend/app/planning/data/controlled-recipes.v1.json` 与 `backend/migrations/versions/0011_controlled_recipes.py` 存在。
- 已确认任务提交 `78ec1a8` 与 `5c4adfa` 存在于 Git 历史。

---
*Phase: 05-diet-planning-subgraph*
*Completed: 2026-09-01*
