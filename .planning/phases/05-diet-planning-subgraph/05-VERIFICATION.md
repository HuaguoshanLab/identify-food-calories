---
phase: 05-diet-planning-subgraph
verified: 2026-09-02T01:56:54Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "规划子图检索受控菜谱，生成餐单并用工具校验总量、比例、忌口和重复度。"
  gaps_remaining: []
  regressions: []
---

# Phase 5: 饮食规划子图 Verification Report

**Phase Goal:** Agent 根据用户目标和偏好生成可校验、可交互调整的一日三餐方案。
**Verified:** 2026-09-02T01:56:54Z
**Status:** passed
**Re-verification:** Yes — PLN-04 缺口关闭后复验

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | 身体数据与目标经确定性公式生成每日能量和宏量营养约束。 | ✓ VERIFIED | `PlanningService.calculate_target()` 使用 Decimal、固定 Mifflin–St Jeor/活动系数/速度和版本化目标策略；service 测试覆盖成人计算和无效输入。 |
| 2 | 规划子图检索受控菜谱，生成餐单并用工具校验总量、比例、忌口和重复度。 | ✓ VERIFIED | `validate_plan(target, meals, ...)` 对实际三餐重算 kcal/蛋白/脂肪/碳水，检查三槽、recipe 去重、忌口、1200 kcal 地板、目标区间和 AMDR；`SessionNutritionToolAdapter` 将 graph 的 `composition.meals` 原样传入。正反例覆盖 totals、ratio、duplicate 和 exclusion。 |
| 3 | 不合格方案仅在有限次数内重排，之后给出可解释失败结果。 | ✓ VERIFIED | `DietPlanningGraph` 初始生成和局部调整均受三次重排预算限制；第四次调整返回 `LIMIT_REACHED`，不会继续请求模型或菜谱替换。 |
| 4 | 用户反馈“换清淡”“不吃某菜”后，保留其他约束并恢复图继续规划。 | ✓ VERIFIED | graph 仅替换受影响 slot，adapter 以 `existing_meals` 排除已保留的 recipe；图/API/前端测试覆盖同线程局部替换和其他餐次保持不变。 |
| 5 | 输出明确声明非医疗建议，并拒绝高风险健康请求。 | ✓ VERIFIED | `_is_health_scope_blocked()` 在任何目标/菜谱计算前拒绝未成年、孕哺、疾病/用药、进食障碍/自伤及极端目标；真实 API 测试断言 18 岁请求只得到 `needs_input`，且不会保存 profile。H5 始终显示非医疗免责声明。 |

**Score:** 5/5 truths verified

## Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `backend/app/planning/service.py` | 确定性目标、健康边界与全餐单校验 | ✓ VERIFIED | 非 stub；验证入口接收 `tuple[PlannedMeal, ...]`，总量与比例均来自餐单而非模型文本或硬编码。 |
| `backend/app/agent/tools.py` + `backend/app/agent/graph.py` | 图到确定性校验的完整闭环 | ✓ VERIFIED | graph 传递 composition，adapter 传递 meals，service 返回 PASS/REPLAN/RELAX/BLOCK；RELAX 不会放宽能量地板、比例、忌口或重复度。 |
| `backend/app/planning/data/controlled-recipes.v2.json` + `repository.py` | 当前可用的三餐候选 | ✓ VERIFIED | 查询同时限制 catalog、`controlled-recipes.v2` 与 `is_active`；五个 v2 recipes 足以生成不重复、超过最低能量的三餐。 |
| `backend/migrations/versions/0012_activate_controlled_recipes_v2.py` + `importer.py` + `scripts/bootstrap_local_planning_data.py` | 保留 v1 审计历史并激活 v2 的本地启动 | ✓ VERIFIED | 0012 仅把 v1 标为 inactive、没有删除记录；importer 以版本幂等导入，v2 激活时停用旧 active 版本；local bootstrap 按 v1→v2 顺序导入且不重置资料/偏好。隔离数据库 round-trip 与 bootstrap 测试通过。 |
| `backend/app/agent/api.py` + `frontend/src/features/plans/components/PlanPage.tsx` | 安全、无内部细节泄露的用户路径 | ✓ VERIFIED | 公开 API 返回 allowlisted planning snapshot；PlanPage 严格解析状态、固定展示三餐和免责声明。此前真实浏览器路径已由用户确认可用；本轮真实 API 覆盖明确命名的合成普通成人成功场景。 |

## Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `DietPlanningGraph` | `SessionNutritionToolAdapter` | `validate_daily_plan(target, meals=composition.meals, ...)` | ✓ WIRED | 实际 composition 的 meal DTO 进入 adapter；不是只传 target 的空校验。 |
| `SessionNutritionToolAdapter` | `PlanningService.validate_plan` | `meals=meals` | ✓ WIRED | adapter 将完整 meals、已匹配忌口和重排次数传给 service；服务端按真实 totals 决定结果。 |
| `PlanningService.compose_daily_meals` | 版本化 controlled recipe repository | catalog + `CONTROLLED_RECIPE_VERSION` | ✓ WIRED | runtime 明确选择 v2；inactive 的 v1 不会进入当前候选。 |
| Alembic 0012 / local bootstrap | controlled recipe data | deactivate v1 → import v1/v2 → activate v2 | ✓ WIRED | 迁移保留历史，bootstrap 使用同一 importer；隔离 PostgreSQL 测试证实当前版本只有 v2 active。 |
| public diet-planning API | graph/service/report | FastAPI → AgentService → planning graph | ✓ WIRED | HTTPX + PostgreSQL 真实请求以明确命名的合成普通成人 fixture 返回完成的三餐计划。 |

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `PlanningService.validate_plan()` | `daily_totals`、macro energy ratio | 传入的 `PlannedMeal.nutrition` | Decimal 聚合三餐实际数值 | ✓ FLOWING |
| `DietPlanningGraph` | `composition.meals` | repository 受控 recipe → deterministic nutrition calculation | 真实受控食材 grams 和营养 DTO | ✓ FLOWING |
| public API response | `report.meals` / `target` / safe refusal | PostgreSQL profile + graph checkpoint/report | 真实 PostgreSQL API 成功与拒绝例 | ✓ FLOWING |
| `PlanPage.tsx` | parsed planning snapshot | authenticated public Agent API | 严格 Zod allowlist，而非内部 exception/trace | ✓ FLOWING |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| 总量、宏量比例、重复度、忌口、图有界重排 | `cd backend && APP_ENV=test … uv run pytest tests/planning/test_planning_service.py tests/planning/test_controlled_recipe_importer.py tests/unit/test_diet_planning_graph.py -q` | 54 passed | ✓ PASS |
| 真实 PostgreSQL API：成人成功路径与健康拒绝 | `cd backend && APP_ENV=test … uv run pytest tests/integration/test_diet_planning_agent_api.py -q` | 5 passed | ✓ PASS |
| 0012 round-trip 与 v1/v2 seed 激活状态 | `cd backend && APP_ENV=test … uv run pytest tests/integration/test_agent_bootstrap.py tests/integration/test_agent_migration.py -q` | 3 passed（已知 SQLAlchemy `vector` reflection warning，不影响断言） | ✓ PASS |
| 本轮合并独立回归 | `cd backend && APP_ENV=test … uv run pytest [上述六个测试文件] -q` | exit 0 | ✓ PASS |
| 修改范围静态检查 | `cd backend && uv run ruff check app/planning app/agent tests/planning/test_planning_service.py tests/planning/test_controlled_recipe_importer.py tests/unit/test_diet_planning_graph.py tests/integration/test_diet_planning_agent_api.py` | All checks passed | ✓ PASS |

`…` 为报告中已省略的 `DATABASE_URL` 与 `TEST_DATABASE_URL`；两者均指向测试环境。未运行会写入开发库的 bootstrap 脚本；其不重置、只导入版本化 seed 的行为已通过代码审查和隔离 bootstrap 测试验证。

## Probe Execution

Step 7c: SKIPPED — 本阶段没有声明 `probe-*.sh`，仓库亦不存在 Phase 5 对应 probe。

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| PLN-01 | 01, 03, 05, 07, 09 | 用户提交资料/目标/偏好 | ✓ SATISFIED | owner-scoped profile CRUD、显式保存和删除、前端预填/空态均已接线。 |
| PLN-02 | 01, 02, 08, 09 | 确定性目标计算 | ✓ SATISFIED | 版本化策略、Decimal 计算和 service/API 测试。 |
| PLN-03 | 02, 08, 09, 11 | 受控菜谱与三餐候选 | ✓ SATISFIED | audit/catalog/version 过滤、v2 seed 和本地 bootstrap。 |
| PLN-04 | 01, 02, 04, 08, 10, 11 | 总量/宏量/忌口/重复度校验与有界重排 | ✓ SATISFIED | meals 已进入 service；总量、AMDR、排除项与唯一 recipe 均在确定性服务端执行。 |
| PLN-05 | 04, 06, 10 | 同线程自然语言局部调整 | ✓ SATISFIED | affected-slot replacement、其余餐次保留和次数上限已测试。 |
| PLN-06 | 01–06, 09, 10, 11 | 非医疗说明与医疗边界 | ✓ SATISFIED | fail-closed health guard、无 profile 写入的真实 API 拒绝和 H5 免责声明。 |

## Anti-Patterns Found

未发现本阶段修改文件中的 `TBD`、`FIXME`、`XXX`、空实现、硬编码空数据或仅日志处理器。此前 PLN-04 的空心校验链已不再存在。

## Conclusion

原先阻断 Phase 5 的 PLN-04 已由真实代码闭合：餐单数据从 graph 流入 adapter 和确定性 service，校验结果再驱动有界重排或安全终止；它没有以放宽能量、宏量比例、忌口、重复度或健康边界为代价。0012/v2 seed 方案保留 v1 历史，并在隔离本地启动等价路径和真实 PostgreSQL API 正反例中通过。阶段目标已达成。

---

_Verified: 2026-09-02T01:56:54Z_
_Verifier: the agent (gsd-verifier)_
