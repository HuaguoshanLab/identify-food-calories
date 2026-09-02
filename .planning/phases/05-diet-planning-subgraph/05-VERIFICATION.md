---
phase: 05-diet-planning-subgraph
verified: 2026-09-02T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
gaps: []
historical_gaps:
  - truth: "规划子图检索受控菜谱，生成餐单并用工具校验总量、比例、忌口和重复度。"
    status: failed
    reason: "实际校验入口不接收 meals，也没有计算总量、宏量比例或重复度；图把 meals 传给 adapter，但 adapter 丢弃该参数。任何三餐组合都会在未触发 RELAX 时得到 PASS。"
    artifacts:
      - path: "backend/app/planning/service.py"
        issue: "PlanningService.validate_plan() 只接受 target、matched_exclusions、allow_target_relaxation，不能校验餐单。"
      - path: "backend/app/agent/tools.py"
        issue: "validate_daily_plan(..., meals=...) 调用 service.validate_plan() 时未传递或汇总 meals。"
    missing:
      - "在确定性 PlanningService 中汇总三餐营养，检查能量区间、每项宏量范围/比例、已确认忌口和重复度。"
      - "让 PlanningToolAdapter 将实际 meals 传入校验，并以 REPLAN/RELAX/BLOCK 的闭合动作驱动有界重排。"
      - "补充总量、宏量比例、重复度的正反例 service、graph 与真实 PostgreSQL/API 测试。"
---

# Phase 5: 饮食规划子图 Verification Report

**Phase Goal:** Agent 根据用户目标和偏好生成可校验、可交互调整的一日三餐方案。  
**Verified:** 2026-09-01T10:07:12Z  
**Status:** gaps_found  
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | 身体数据与目标经确定性公式生成每日能量和宏量营养约束。 | ✓ VERIFIED | `backend/app/planning/service.py` 使用 Decimal 的 Mifflin–St Jeor、五档活动系数、保守速度、能量及宏量区间；`tests/planning/test_planning_service.py` 覆盖确定性数值、缺失输入和健康 guard。 |
| 2 | 规划子图检索受控菜谱，生成餐单并用工具校验总量、比例、忌口和重复度。 | ✗ FAILED | 菜谱检索、资格过滤和逐食材重算存在；但 `PlanningService.validate_plan()` 不接收 meals，`SessionNutritionToolAdapter.validate_daily_plan()` 丢弃 meals，因此总量、宏量比例、重复度从未被校验。 |
| 3 | 不合格方案仅在有限次数内重排，之后给出可解释失败结果。 | ✓ VERIFIED | `DietPlanningGraph` 对首次组合以 `while current.replan_count < 3` 限制；调整路径在 `replan_count >= 3` 返回 `LIMIT_REACHED`。`test_diet_planning_graph.py` 断言三次后第四次不调用 replacement。 |
| 4 | 用户反馈“换清淡”“不吃某菜”后，保留其他约束并恢复图继续规划。 | ✓ VERIFIED | 图仅替换选中的 slot，adapter 保留其余 `existing_meals`；偏好捕获经既有 typed memory tool；unit、API、Playwright 都断言早餐/晚餐不变、午餐替换。 |
| 5 | 输出明确声明非医疗建议，并拒绝高风险健康请求。 | ✓ VERIFIED | `PlanningService._is_health_scope_blocked()` 在目标/菜谱之前拒绝；`PlanPage` 首次、结果 footer 均显示免责声明，且仅 safe health-scope snapshot 显示医疗转介、无餐卡绕过。用户已确认真实 `/app/plans` 在修复候选耗尽误判后可用。 |

**Score:** 4/5 truths verified

## Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `backend/app/planning/service.py` | 版本化目标、健康边界、确定性餐单校验 | ⚠️ PARTIAL | 375 行、非 stub；目标、健康 guard、受控候选与逐食材重算真实存在，但校验逻辑未接收餐单。 |
| `backend/app/planning/repository.py` + `data/controlled-recipes.v1.json` | 审计合格的三餐候选 | ✓ VERIFIED | SQL 过滤 project-authored/license/audit/catalog qualification；seed 有早餐、两个午餐候选和晚餐，并由受控 grams 重算。 |
| `backend/app/agent/graph.py` + `state.py` | 独立、有界的 DietPlanningGraph | ✓ VERIFIED | 独立 state 版本/namespace、三次限制、slot-local 调整、safe report 已接入 `RoutedAgentGraph`。 |
| `backend/app/planning/api.py` + `frontend/src/features/plans/components/PersonalProfilePage.tsx` | 用户级最小资料 CRUD 与删除入口 | ✓ VERIFIED | 认证 Principal → Service → tenant-filtered Repository；软删除 active predicate；H5 有查看、编辑、确认删除和 plans-only 空态入口。 |
| `frontend/src/features/plans/components/PlanPage.tsx` + `MealCard.tsx` | 无内部泄露的三餐、安全状态、调整 UI | ✓ VERIFIED | 严格 Zod snapshot、六个 allowlisted 事件、固定三餐顺序、持续免责声明、局部替换/上限/refusal 展示。 |

## Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `DietPlanningGraph` | `PlanningToolAdapter` | calculate → compose → validate | ⚠️ PARTIAL | 调用链存在，但 validate link 不传递或使用实际三餐，形成空心校验。 |
| `PlanningService` | NutritionService | qualified catalog item ID + grams | ✓ WIRED | `_build_meal()` 对每个 ingredient 调用 `calculate_nutrition` 并汇总公开 nutrient DTO。 |
| `/api/v1/agent/threads/diet-planning` | 独立 planning checkpoint | AgentService + graph-kind codec namespace | ✓ WIRED | API 以 `DIET_PLANNING` 创建 run；state codec/namespace 映射与跨 codec 测试存在。 |
| `PlanPage` | public profile/memory reads + Agent API | TanStack Query, validated command, snapshot/SSE | ✓ WIRED | Profile 和 memories 仅 GET 预填；start/adjust commands 均经 authenticated public API，未见 browser-side memory/profile 隐式写入。 |

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `PlanPage.tsx` | `report.meals`, `target`, `adjustment` | owned-thread snapshot → strict Zod schemas | 后端安全 report | ✓ FLOWING |
| `MealCard.tsx` | 标准名、grams、tags、matched constraints | `PlanPage` parsed meal prop | 受控 recipe DTO，不是硬编码 mock | ✓ FLOWING |
| `PlanningService.validate_plan()` | 理应为 meals/totals/ratios/repetition | adapter 没有向 service 提供 meals | 无 | ✗ DISCONNECTED |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| H5 资料复核、结果、安全状态、个人资料组件 | `cd frontend && npm run typecheck && npm run lint && npm test -- --run src/features/plans/format.test.ts src/features/plans/components/ProfileGoalForm.test.tsx src/features/plans/components/PlanPage.test.tsx src/features/plans/components/PersonalProfilePage.test.tsx` | typecheck/lint 通过；15 tests passed | ✓ PASS |
| 确定性目标、健康 guard、图重排/调整上限 | `cd backend && uv run pytest tests/planning/test_planning_service.py tests/unit/test_diet_planning_graph.py -q` | 46 passed | ✓ PASS |
| 修改范围静态质量 | `cd backend && uv run ruff check app/planning app/agent tests/planning/test_planning_service.py tests/unit/test_diet_planning_graph.py && uv run mypy app/planning` | ruff passed；mypy 8 files clean | ✓ PASS |
| 校验是否消费实际餐单 | `inspect.signature(PlanningService.validate_plan)` + adapter call-site scan | signature 只有 target/exclusions/relax flag；`validate_daily_plan(... meals=...)` 未把 meals 传给 service | ✗ FAIL |

## Probe Execution

Step 7c: SKIPPED — 本阶段未声明 `probe-*.sh`，且仓库没有 Phase 5 相关 conventional probe。

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| PLN-01 | 01, 03, 05, 07, 09 | 用户提交资料/目标/偏好 | ✓ SATISFIED | RHF/Zod 表单、只读 memory 复核、显式 save_profile、owner CRUD 与删除链存在。 |
| PLN-02 | 01, 02, 08, 09 | 确定性目标计算 | ✓ SATISFIED | `target-policy.v1` 与 Decimal 单测；浏览器仅显示 server range。 |
| PLN-03 | 02, 08, 09 | 受控菜谱与三餐候选 | ✓ SATISFIED | audit/catalog SQL filter、离线 seed、严格 bootstrap、三槽 report。 |
| PLN-04 | 01, 02, 04, 08, 10 | 总量/宏量/忌口/重复度校验与有界重排 | ✗ BLOCKED | 忌口过滤和三次上限存在；总量、宏量比例、重复度校验不存在，不能满足完整 requirement。 |
| PLN-05 | 04, 06, 10 | 同线程自然语言局部调整 | ✓ SATISFIED | owned-thread input → captured explicit preference → affected slot replacement；API/E2E evidence。 |
| PLN-06 | 01–06, 09, 10 | 非医疗说明与医疗边界 | ✓ SATISFIED | deterministic health guard、safe public failure projection、persistent H5 disclaimer。 |

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- |
| `backend/app/planning/service.py` | 107 | 校验接口没有 meals 参数 | 🛑 Blocker | 无法校验三餐总量、宏量比例或重复度。 |
| `backend/app/agent/tools.py` | 299 | adapter 接收 `meals` 后丢弃 | 🛑 Blocker | 图→校验的关键数据流被切断。 |
| `frontend/src/features/plans/components/PlanPage.tsx` | 113 | 候选耗尽曾被误映射为健康拒绝 | ℹ️ Fixed | `e95e1af` 已把 terminal exhaustion 映射为真实普通错误，新增回归覆盖。 |

未发现本阶段修改文件中的无引用 `TBD`、`FIXME` 或 `XXX` 债务标记；组件中的空初始状态会被 Query/用户输入填充，不是 stub。

## Human Verification Required

用户已在真实本地 `/app/plans` 路径确认恢复后的页面可用；Phase 06 的隔离公开 Playwright 已覆盖注册→Mailpit→登录→生成→局部调整→资料删除。由于存在 blocker，以下仅作为修复后的复验清单：

### 1. 真实校验失败与重排说明

**Test:** 在修复后使用一组会让每日总热量或宏量比例超出范围、或制造重复食材的受控候选，生成计划。  
**Expected:** 页面只显示后端安全的重排/放宽/上限说明；不能把不合格组合标为完成。  
**Why human:** 可自动覆盖边界，但最终中文文案、焦点和移动端理解度需要真实浏览器确认。

## Gaps Summary

这不是“测试没写够”的警告，而是数据流缺失：图确实调用了名为 validate 的工具，但该工具无法看到 meals。现有 46 个后端定向测试和 15 个前端测试都能通过，因为它们没有构造并拒绝一个营养总量、宏量比例或重复度不合格的三餐。

Phase 6 的路线图不承担该确定性校验实现，故不能作为延后项。必须先补齐 PLN-04，再将本 Phase 标为完成。

---

_Verified: 2026-09-01T10:07:12Z_  
_Verifier: the agent (gsd-verifier)_

---

## Re-verification: 2026-09-02 — PASSED

此节取代上方的 PLN-04 失败结论；原报告保留为发现问题的审计记录。

| 先前缺口 | 已验证修复 | 证据 |
| --- | --- | --- |
| 三餐总量、宏量比例、重复度没有进入确定性校验 | `PlanningService.validate_plan()` 接收三餐 DTO，以 Decimal 汇总能量和全部宏量，校验三槽完整、recipe 去重、排除项、1200 kcal 地板、目标区间和 AMDR 比例。 | `tests/planning/test_planning_service.py`、`test_controlled_recipe_importer.py` 与 `test_diet_planning_graph.py` 共 54 passed。 |
| graph → adapter → service 丢弃 meals | `PlanningToolAdapter` 与 `SessionNutritionToolAdapter` 强类型透传 `tuple[PlannedMeal, ...]`；初始 `RELAX` 产生公开偏离投影。 | 图测试覆盖实际 meals 传递、非健康 REPLAN 三次终止和初始 RELAX 安全报告。 |
| v1 受控三餐总量约 1011 kcal | 新增不可变 `controlled-recipes.v2`，adapter/repository 显式选择它；0012 与 importer 停用 v1，bootstrap 按 v1 → v2 幂等导入。 | importer/seed bootstrap 测试和 Alembic `0012 → 0011 → 0012` 回归通过。 |
| 真实公开 API 缺少安全正反例 | 健康范围仍 fail-closed；161cm/50kg/28岁/久坐/维持经公开 API 生成三餐，能量高于 1200 且落在目标区间。 | `tests/integration/test_diet_planning_agent_api.py`：5 passed，真实 PostgreSQL + HTTPX。 |

### Commands

- PASS — `uv run pytest tests/planning/test_planning_service.py tests/planning/test_controlled_recipe_importer.py tests/unit/test_diet_planning_graph.py -q` → 54 passed。
- PASS — `uv run pytest tests/integration/test_diet_planning_agent_api.py -q` → 5 passed。
- PASS — 隔离 PostgreSQL 的 migration/bootstrap targeted suites，以及 0012 downgrade/upgrade head。
- PASS — Ruff。
- KNOWN EXTERNAL — mypy 跟踪到既有 `app/memory/providers.py` 的 Mem0 类型问题；本次 planning/graph 文件没有类型错误。

本地开发库已升级至 `0012` 并导入 `controlled-recipes.v2`，未触碰个人资料。这里不声称 seed 切换后的新浏览器点击已完成。
