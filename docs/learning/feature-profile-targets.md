# 11 个人资料与饮食目标：先确认输入，再计算范围

[返回功能学习总目录](README.md)

用户提供身体资料、活动水平和目标后，后端按版本化规则计算一日目标范围。用户可选择保存资料，下次使用时仍需确认本次输入。

## 1. 先看一个实际例子

小林填写身体资料和活动水平，确认这次要使用的偏好，只想先试算目标；他没有勾选保存资料。我们看系统如何计算，却不把试算自动变成长期资料。

这个例子贯穿下面的执行过程。示例数据用于理解代码，不是线上测量或真实模型效果证明。

## 2. 为什么需要这样实现

如果用户只是试算一次目标，后端不应自动把输入当成长期个人资料。数值目标也需要固定计算政策，不能每次由模型随意编一个。

## 3. 一张图看懂全过程

```mermaid
flowchart TD
    N0["填写并确认资料与偏好"]
    N1["检查输入完整性"]
    N0 --> N1
    N2["检查项目支持范围"]
    N1 --> N2
    N3["按固定公式与政策计算目标"]
    N2 --> N3
    N4["返回能量和营养素范围"]
    N3 --> N4
    N5["用户选择时保存资料"]
    N4 --> N5
```

图展示主线，失败与追问分支在第 5 节对照阅读。

## 4. 跟着这个例子读代码

以下为当前源码的连续节选，省略外围处理，不能单独运行。每一步都说明调用位置和数据去向。

### 4.1 先检查是否能计算

**收到什么**

图调用目标工具，收到本次资料与已确认偏好。

**代码在哪里**

[backend/app/planning/service.py](../../backend/app/planning/service.py) 的 `calculate_daily_target`。

```python
if not self._has_complete_inputs(profile, preferences):
    return TargetCalculationResult(
        action=PlanValidationAction.NEEDS_INPUT,
        safe_message="请补全并确认身体资料、目标和饮食偏好后继续。",
    )
if self._is_health_scope_blocked(profile):
    return TargetCalculationResult(
        action=PlanValidationAction.BLOCK_HEALTH_SCOPE,
        safe_message=HEALTH_REFUSAL_MESSAGE,
    )
```

**为什么这样写**

完整输入和项目支持范围是前置条件；不应该让模型先编目标再补检查。这里只解释现有代码政策，不是给读者的个人健康建议。

**处理后变成什么，交给谁**

缺失返回 NEEDS_INPUT，超出范围返回 BLOCK_HEALTH_SCOPE；本例通过后进入公式。

> 语法小注：枚举 action 是下一步的明确指令，不是一段需要模型猜测含义的文字。

### 4.2 固定公式生成目标范围

**收到什么**

资料已通过检查，公式所需字段不再为空。

**代码在哪里**

[backend/app/planning/service.py](../../backend/app/planning/service.py) 的 `calculate_daily_target`。

```python
energy = (
    self._mifflin_st_jeor(profile)
    * ACTIVITY_FACTORS[profile.activity_level]
    + SPEED_DELTAS[profile.goal_speed]
)
energy_range = TargetRange(
    lower=energy - TARGET_RANGE_MARGIN_KCAL,
    upper=energy + TARGET_RANGE_MARGIN_KCAL,
)
if energy < MIN_SAFE_ENERGY_KCAL or energy_range.lower < MIN_SAFE_ENERGY_KCAL:
    return TargetCalculationResult(
        action=PlanValidationAction.BLOCK_HEALTH_SCOPE,
        safe_message=HEALTH_REFUSAL_MESSAGE,
    )
```

**为什么这样写**

基础公式、活动系数和目标调整量都在代码中。先得到能量再给范围，并检查最低边界，不让模型决定数值真相。

**处理后变成什么，交给谁**

生成 energy_range，后续用它派生宏量营养范围，返回 DailyTarget 给规划流程。相同输入和政策得到可重算结果。

> 语法小注：`Decimal` 处理十进制值；范围是上下界，不是精确的个人需求承诺。

### 4.3 通过检查后才考虑保存资料

**收到什么**

当前已有可用目标，还带用户是否选择保存的 save_profile。

**代码在哪里**

[backend/app/agent/graph.py](../../backend/app/agent/graph.py) 的 `DietPlanningGraph.ainvoke`。

```python
# A health-scope refusal must not persist the transient command as a profile.  Saving is
# intentionally deferred until the deterministic health guard has accepted the request.
if current.save_profile and not current.profile_save_completed:
    current = self._call_profile_upsert(current)
```

**为什么这样写**

使用资料算一次与长期存储是两个决定。保存放在范围检查后，避免被拒绝的输入被顺便记录。

**处理后变成什么，交给谁**

本例 save_profile=False，直接进入餐单组合，不写资料。为真则调用 _call_profile_upsert，且用完成标记防止重复保存。

## 5. 换一种输入，会走哪条路

| 情况 | 判断与处理 | 应观察的结果 |
|---|---|---|
| 缺身高等字段 | NEEDS_INPUT | 等待补充 |
| 超出支持范围 | 拒绝 | 不借此持久化资料 |
| 不勾选保存 | 跳过 upsert | 仍可继续本次流程 |

## 6. 自己验证一次

在仓库根目录执行现有测试，使用后端已安装的测试环境：

```bash
cd backend
.venv/bin/python -m pytest tests/planning/test_planning_service.py tests/planning/test_planning_profile_service.py -q
```

观察目标计算与资料写入是独立测试；比较完整输入、缺字段和删除资料后目标资格的变化。

本轮运行范围与结果见[总目录验证记录](README.md)。替身测试证明指定输入下的代码行为，不能替代真实模型效果、数据库并发或页面验收。

## 7. 读完应该能回答什么

1. 为什么试算不等于保存？
2. 目标数值在哪里产生？
3. 资料改变后旧目标为什么需要失效？

源码阅读顺序：[planning/service.py](../../backend/app/planning/service.py) → [agent/graph.py](../../backend/app/agent/graph.py)。先跟本例函数走一遍，再展开旁支。
