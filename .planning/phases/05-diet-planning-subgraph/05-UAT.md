---
status: diagnosed
phase: 05-diet-planning-subgraph
source: 05-01-SUMMARY.md, 05-02-SUMMARY.md, 05-03-SUMMARY.md, 05-04-SUMMARY.md, 05-05-SUMMARY.md, 05-06-SUMMARY.md, 05-07-SUMMARY.md, 05-08-SUMMARY.md, 05-09-SUMMARY.md, 05-10-SUMMARY.md, 05-11-SUMMARY.md
started: 2026-09-02T02:39:17Z
updated: 2026-09-02T03:20:00Z
---

## Current Test

[testing complete]

## Tests

### 1. 冷启动可用性
expected: 从零启动后迁移、受控菜谱导入和计划页首屏均正常。
result: pass

### 2. 个人资料查看与编辑入口
expected: 在“我的”中进入“个人资料”，可查看身高、体重、年龄、估算参数、活动、目标和速度；可见编辑入口，饮食偏好只链接到既有偏好管理页。
result: pass

### 3. 普通饮食计划生成
expected: 完整填写并确认普通成人资料与偏好后，计划页能生成早餐、午餐、晚餐；页面持续显示“普通饮食参考，不替代医疗建议”。
result: pass
retested: "2026-09-02：在当前浏览器重新提交后，三餐和非医疗声明正常显示。"

### 4. 三餐与全天目标解释
expected: 每餐显示受控份量、方法或口味标签及匹配约束；全天显示能量与三大宏量的目标范围、计划值和状态，不出现模型编造的食材营养数值。
result: pass
retested: "2026-09-02：当前浏览器显示三餐卡片及四项全天目标范围、计划值和状态。"

### 5. 单餐局部调整
expected: 对一餐提出可执行的调整后，仅受影响餐次显示“已调整”；其余两餐保持不变，结果仍按早餐、午餐、晚餐顺序展示。
result: issue
reported: "点击提交调整后，页面整体自动滚到上方，需要手动往下滑动才能查看调整结果。"
severity: minor

### 6. 有界调整与透明放宽
expected: 必要的能量或宏量放宽会明确展示原范围、计划值、偏离和安全理由，并说明忌口与显式排除没有被放宽；达到三次调整上限后不再提供绕过入口。
result: pass

### 7. 安全拒绝与非医疗边界
expected: 页面可见非医疗声明；系统遇到不适合个性化饮食规划的高风险情况时，仅显示停止生成和咨询医生/注册营养师的明确提示，不展示餐卡或替代性“医疗方案”。
result: pass

### 8. 资料删除保护
expected: 个人资料页的删除操作有明确确认提示；未确认不会删除资料，删除后不会保留旧资料作为后续计划的预填。
result: pass

## Summary

total: 8
passed: 7
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "对一餐提出可执行的调整后，仅受影响餐次显示“已调整”；其余两餐保持不变，结果仍按早餐、午餐、晚餐顺序展示。"
  status: failed
  reason: "用户报告：点击提交调整后，页面整体自动滚到上方，需要手动往下滑动才能查看调整结果。"
  severity: minor
  test: 5
  root_cause: "PlanPage.tsx 的 effect 在 updatedSlot 变化时对 sr-only 的替换摘要调用 focus()；浏览器会滚动到这个不可见元素，导致用户离开提交调整时的阅读位置。现有单测还把该隐藏元素获得焦点当成正确行为。"
  artifacts:
    - path: "frontend/src/features/plans/components/PlanPage.tsx"
      issue: "第 88 行的 programmatic focus 指向第 160 行的 sr-only 摘要。"
    - path: "frontend/src/features/plans/components/PlanPage.test.tsx"
      issue: "局部调整测试断言隐藏摘要拥有焦点，固化了页面滚动副作用。"
  missing:
    - "保留 aria-live 通知，但取消对隐藏摘要的 programmatic focus。"
    - "改为验证视觉滚动位置不被调整完成逻辑劫持。"
  debug_session: "inline: PlanPage focus-effect inspection"
