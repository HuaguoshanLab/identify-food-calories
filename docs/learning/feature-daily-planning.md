# 12 生成一日餐单：从可用候选中组合，再逐项校验

[返回功能学习总目录](README.md)

根据本次确认的目标和偏好选择早餐、午餐、晚餐，必要时含加餐，并检查整日约束。当前核心组合由后端规则完成，不是模型自由创作一份菜单。

## 1. 先看一个实际例子

小林确认资料和忌口，希望得到一日三餐。假设候选池有足够合格菜品，我们看系统怎样先组合，再决定能否接受，而不是只要凑出三道菜就成功。

这个例子贯穿下面的执行过程。示例数据用于理解代码，不是线上测量或真实模型效果证明。

## 2. 为什么需要这样实现

让模型直接输出三道菜很容易，但菜可能不在目录中，营养也无法复算。系统需要可计算的候选来源，并说明为什么某份计划能被接受。

## 3. 一张图看懂全过程

```mermaid
flowchart TD
    N0["确认资料和偏好"]
    N1["工具计算目标"]
    N0 --> N1
    N2["读取合格菜谱候选"]
    N1 --> N2
    N3["组合餐次并重算营养"]
    N2 --> N3
    N4["检查全天约束"]
    N3 --> N4
    N5["通过则返回；可放宽目标时复用餐单重验，否则明确提示"]
    N4 --> N5
```

图展示主线，失败与追问分支在第 5 节对照阅读。

## 4. 跟着这个例子读代码

以下为当前源码的连续节选，省略外围处理，不能单独运行。每一步都说明调用位置和数据去向。

### 4.1 取得目标，明确下一动作

**收到什么**

用户已确认本次偏好；未确认的请求在前面返回 needs_input。

**代码在哪里**

[backend/app/agent/graph.py](../../backend/app/agent/graph.py) 的 `DietPlanningGraph.ainvoke`。

```python
current = state
target_result = self._tools.calculate_daily_target(
    profile=current.profile, preferences=current.preferences
)
current = self._record_tool(current, "calculate_targets", target_result.action.value, target_result)
if target_result.action is not PlanValidationAction.PASS or target_result.target is None:
    return self._safe_terminal(current, target_result.action, target_result.safe_message)
current = current.model_copy(
    update={"target": target_result.target, "next_action": DietPlanningAction.COMPOSE_PLAN}
)
```

**为什么这样写**

目标先通过确定性工具计算，失败不进入组合。把 target 写进状态，让后续校验仍对照同一目标。

**处理后变成什么，交给谁**

状态拿到 DailyTarget，下一步 COMPOSE_PLAN。显式资料保存处理后执行一次有预算的组合搜索。

> 语法小注：`model_copy(update=...)` 生成更新后的状态，传递下一步需要的数据。

### 4.2 把目标传给选菜服务

**收到什么**

`DailyTarget` 是确定性工具算出的全天目标；`PreferenceReview` 是用户确认的忌口和口味。

**代码在哪里**

[backend/app/agent/tools.py](../../backend/app/agent/tools.py) 的 `SessionNutritionToolAdapter.compose_daily_plan`。以下省略 Session 的创建和关闭：

```python
return service.compose_daily_meals(
    user_id=user_id,
    target=target,
    catalog_version=None,
    preferences=preferences,
    recipe_version=CONTROLLED_RECIPE_VERSION,
)
```

**为什么这样写**

目标必须参与选菜。管理员候选携带自己的目录版本，不固定为某个初始目录。新环境尚未配置过管理员候选时，服务可读取当前启用且审核通过的受控食谱；一旦存在管理员候选记录，即使全部停用或删除，也不会自动回退，避免绕过管理员决定。

**处理后变成什么，交给谁**

每个候选按目录和原有份量重算营养，再交给 `planning/selection.py` 的 `select_meals`。未改变食谱份量和营养公式。

### 4.3 在有界组合中比较目标与偏好

[backend/app/planning/selection.py](../../backend/app/planning/selection.py) 使用 `planning-selection.v5`。输入是已经计算好的候选餐次；输出是一组三餐或空结果。

- Repository 先筛餐次、启用状态和目录资格，再按 UUID 游标翻页：`id > after_id`，没有全库加载和“总数超过 1024 就失败”。管理员候选的两个目录来源先各取一页，再合并取当前页；初始受控菜谱也分页读取。
- Service 的 `_scan_recipes` 给每餐独立的条数和时间预算，默认每页 64 条、每餐最多扫描 2,048 条或 3 秒。先根据菜名和标签排除已知忌口，再调用营养工具并复核目录别名；后面的页面仍有机会进入候选。
- `select_meals` 一边消费候选一边保留每餐前 12 项，不累积整个菜谱库的计算结果。配置入口见 [后端 README](../../backend/README.md#餐单筛选预算)。
- 忌口匹配先保留中文分句边界，再匹配受控菜名、别名和标签。例如“不吃辣 饮食清淡”中的“不吃辣”会排除“香辣”标签；这仍是有限文字规则，不代表能理解任意自然语言约束。
- 组合阶段默认最多尝试 1,728 个三餐组合或 2 秒，重复菜谱的组合也计入尝试预算；停止后保留已找到的最佳结果，再走最终校验。
- 排序先看硬校验与目标符合情况，再比较口味匹配、近期重复和目标中点距离；排序与遍历顺序固定；未触发时间截止且目录未变化时，同样输入、预算与历史产生相同结果。触发时间截止时，机器负载可能影响已扫描范围。
- 近期吃过的菜仍可使用：不能为了换花样丢掉唯一能通过校验的组合。
- 这是有限候选中的启发式搜索，不保证全局最优；最终仍必须通过 `validate_plan`。

忌口检查使用菜名、受控别名、做法和口味标签；受控食谱还检查每个已知食材的名称和别名。全角字符、大小写和多余空白会先归一化。管理员成品菜没有完整配料结构，不能把这种匹配当作过敏原保障，也不推断缺失配料。

时间预算是协作式检查：一次同步查询或计算返回后才会检查时间，不能保证整个请求严格在 11 秒内结束。预算耗尽并不表示库中不存在合适组合，只表示本次有限搜索没有找到；不会用不符合忌口的菜凑满三餐。指定替换按食物、餐次、菜谱 ID 和修订号直接过滤后再分页，旧修订和停用候选不能通过。

> 语法小注：生成器的 `yield` 每次交出一个候选，避免一次构造完整列表；UUID 游标只读取上次 ID 之后的行，更新日期不会让已读记录再次出现。`product(*pools)` 枚举各餐次候选的组合；评分元组从左到右比较。`Decimal` 保留十进制计算，避免浮点误差参与排序。

### 4.4 检查三餐与重复，之后才查数值

**收到什么**

组合产生 PlannedMeal 序列，包括餐次、菜谱 ID 和营养。

**代码在哪里**

[backend/app/planning/service.py](../../backend/app/planning/service.py) 的 `validate_plan`。

```python
if not set(REQUIRED_MEAL_SLOTS).issubset({meal.slot for meal in meals}) or len({meal.slot for meal in meals}) != len(meals):
    return PlanValidationResult(
        action=PlanValidationAction.REPLAN,
        rule_id="incomplete-meal-slots",
        safe_message="餐单必须包含不重复的早餐、午餐和晚餐后才能校验。",
    )
if len({meal.recipe_id for meal in meals}) != len(meals):
    return PlanValidationResult(
        action=PlanValidationAction.REPLAN,
        rule_id="duplicate-controlled-recipe",
        safe_message="同一受控菜谱不能在一天内重复使用。",
    )
```

**为什么这样写**

三餐齐全、不重复是结构条件；后面先检查忌口、最低能量与宏量比例，再检查目标范围。范围放宽不能跳过宏量比例。单个食物算对不代表整日组合符合约束。

**处理后变成什么，交给谁**

违规返回 REPLAN；全部通过才 PASS。图不再原样组合三次。只有校验器通过 `relaxation_available` 明确允许调整目标范围时，才复用同一份餐单再校验一次；RELAX 会明确展示偏差，不等于严格通过。

> 语法小注：`set` 去重，比较数量能发现同一餐次或菜谱重复。

## 5. 换一种输入，会走哪条路

| 情况 | 判断与处理 | 应观察的结果 |
|---|---|---|
| 偏好未确认 | 等待输入 | 不开始组合 |
| 缺少某餐候选 | 结束当前生成，指出缺少的餐次 | 补充或启用合格菜谱后再生成 |
| 已确认忌口筛掉候选 | 结束并说明缺少的餐次 | 核对偏好或补充合适菜谱，不自动放宽忌口 |
| 候选营养数据不可用 | 与忌口问题区分 | 检查当前营养目录资格 |
| 扫描或组合预算耗尽 | 说明本次搜索额度用完 | 可稍后重试；反复发生时调整预算，不能断言库中没有解 |
| 仅目标范围不匹配 | 在规则允许时复用餐单重验一次 | 明确展示目标偏差，无重复目录计算 |
| 触犯排除项 | 不允许靠放宽接受 | 调整候选 |

### 5.1 失败分类与诊断怎样连接

`PlanningService._search_failure` 把实际扫描结果归为 `missing_slot`、`exclusions`、`nutrition_unavailable`、`search_budget` 或 `no_combination`。命中条数上限时不额外读取下一页，因此保守地标记“可能尚有未读候选”；不会将有限搜索失败误写成全库无解。

`DietPlanningGraph._validate_composed_meals` 同时服务首次生成和单餐替换。严格校验失败后，只有 `PlanValidationResult.relaxation_available=True` 才进入第二次校验；这个标志只允许目标区间偏差，不能用于忌口、最低能量、宏量比例或重复菜谱。第二次使用相同的 `meals`，营养工具会重新检查硬约束，不重新扫描菜谱。每次校验前检查剩余工具预算。新运行标记为 `diet-planning-graph.v2` / `planning-tools.v2`，Checkpoint 结构无需迁移。

每次组合输出一条 `planning_search` 后端诊断日志，由 [diagnostics.py](../../backend/app/planning/diagnostics.py) 的闭合 Schema 生成：按餐次记录页数、读取/扫描数量、忌口淘汰、目录不可用、其他条件过滤、营养计算次数、合格及最终候选数、停止原因与耗时。另记录组合尝试次数、重复组合数及校验通过/可调整/拒绝次数。工具边界的 `planning_validation` 记录最终规则码和是否采用目标调整。

日志不含用户标识、偏好正文、菜名、菜谱 ID、身体资料或营养目标数值。它们进入后端标准日志，不新增业务表，不发送给 Mem0，也不通过页面或 SSE 暴露。生产日志的保留时间由部署环境配置；目前没有新增日志查询后台。

## 6. 自己验证一次

在仓库根目录执行现有测试，使用后端已安装的测试环境：

```bash
cd backend
.venv/bin/python -m pytest tests/unit/test_diet_planning_graph.py tests/planning/test_planning_service.py tests/planning/test_personalized_selection.py -q
```

观察 COMPOSE 后还必须 VALIDATE，检查候选失败只组合一次、目标范围偏差最多校验两次，以及 PASS/RELAX 的不同结果。用户主动换餐仍保留三次调整上限，自动校验不消耗这个计数。替身验证的是规则路由，不是模型菜单质量。

新增回归覆盖不同目标产生不同组合、口味排序、别名忌口、仅剩可行旧菜、组合上限和宏量比例不能被放宽跳过。替身测试证明指定输入下的代码行为，不能替代真实模型效果、数据库并发或页面验收。

2026-09-15 早前本地验收：`frontend/tests/e2e/plans.spec.ts` 两项通过；Codex 内置浏览器走过公开注册、资料保存、生成、午餐清淡调整、刷新和历史版本。无可替换早餐时流程有界结束，已保存餐单未被覆盖。使用 Fake Provider，仅验证产品链路；真实模型理解质量与真实设备软键盘仍未验证。

同日重新生成故障修复追加验证：规划模块与图测试 114 项、独立 PostgreSQL 计划接口与完成投影测试 9 项、前端全部组件测试 179 项通过。内置浏览器在 `http://127.0.0.1:5178/app/plans` 使用经公开接口注册和准备资料的独立账号，验证偏好未确认提示、首次生成、取消重新生成、生成第 2 版和刷新保留；使用当前 612 条可用候选及“不吃辣 饮食清淡”输入。另修复前端将 SSE 序号当作非法负载字段的问题，进度流结束后重读最终快照，避免历史进度覆盖成功或失败结果。本次未重跑 Playwright E2E；上述浏览器验收为真实页面与公开 API 交互。

同日分批筛选改造验证：规划 Service、选择器和图测试 129 项通过，覆盖 1,500/7,000 条候选、排除项位于前几页、各餐独立的扫描条数/时间预算、组合次数/时间预算，以及指定菜谱的修订复核。独立 PostgreSQL 的候选 Repository、规划接口、完成投影测试 27 项通过；其中 1,200 条候选通过每餐两页、每页最多 7 条组成三餐，并检查 SQL 含 LIMIT、游标不重复、最新目录资格有效。内置浏览器使用独立测试账号在 5178 页面重新生成第 3 版计划并刷新，三餐和自动保存状态保留。

本次还通过 Ruff 检查及餐单 Playwright 两项测试（首次生成、单餐调整、刷新和历史版本）；使用原 `plans.spec.ts` 的临时副本，仅移除共享 Mailpit 邮箱的全量清空调用，所有业务断言保持不变，独立服务使用 5198/8098/5199 端口和受保护测试库，结束后临时副本及服务已清理。前后台构建通过，用户前端仍有既有的打包体积警告。

这些验证不是百万级数据压测；尚未验证极端数据库慢查询下的请求总耗时，也不证明有限候选搜索能找到全库最优组合。

同日失败诊断与有效重试验证：142 项规划/图测试、27 项独立 PostgreSQL 集成测试、14 项计划页测试及 2 项餐单 Playwright 测试通过；Ruff、前端类型检查与构建通过。Playwright 继续使用保留业务断言、仅移除共享邮箱全量清空调用的临时副本，结束后已删除。未执行完整后端和全站前端回归；当前证据覆盖本次规划链路，不代表真实模型质量或生产慢查询压测。

内置浏览器在临时 5198/8098 测试环境，通过实际登录页使用 E2E 注册的测试账号：请求替换早餐，在只有一份早餐且该份已被使用时看到明确的“早餐没有满足当前要求的可用候选”提示；刷新后第 1 版三餐保留，重新生成成功保存第 2 版。对应日志只有一次失败筛选，记录 `missing_slot`、早餐扫描 1 条、营养计算 0 次，没有用户原文；临时页面及服务已关闭。

## 7. 读完应该能回答什么

1. 候选来源在哪里决定？
2. 为什么选满三餐仍可能不通过？
3. RELAX 与 PASS 有何区别？

源码阅读顺序：[agent/graph.py](../../backend/app/agent/graph.py) → [planning/service.py](../../backend/app/planning/service.py)。先跟本例函数走一遍，再展开旁支。
