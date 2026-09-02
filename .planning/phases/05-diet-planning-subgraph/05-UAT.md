---
status: testing
phase: 05-diet-planning-subgraph
source: 05-01-SUMMARY.md, 05-02-SUMMARY.md, 05-03-SUMMARY.md, 05-04-SUMMARY.md, 05-05-SUMMARY.md, 05-06-SUMMARY.md, 05-07-SUMMARY.md, 05-08-SUMMARY.md, 05-09-SUMMARY.md, 05-10-SUMMARY.md, 05-11-SUMMARY.md
started: 2026-09-02T02:39:17Z
updated: 2026-09-02T03:10:00Z
---

## Current Test

number: 5
name: 单餐局部调整
expected: |
  对一餐提出可执行的调整后，仅受影响餐次显示“已调整”；其余两餐保持不变，结果仍按早餐、午餐、晚餐顺序展示。
awaiting: user response

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
result: pending

### 6. 有界调整与透明放宽
expected: 必要的能量或宏量放宽会明确展示原范围、计划值、偏离和安全理由，并说明忌口与显式排除没有被放宽；达到三次调整上限后不再提供绕过入口。
result: pending

### 7. 安全拒绝与非医疗边界
expected: 页面可见非医疗声明；系统遇到不适合个性化饮食规划的高风险情况时，仅显示停止生成和咨询医生/注册营养师的明确提示，不展示餐卡或替代性“医疗方案”。
result: pass

### 8. 资料删除保护
expected: 个人资料页的删除操作有明确确认提示；未确认不会删除资料，删除后不会保留旧资料作为后续计划的预填。
result: pass

## Summary

total: 8
passed: 6
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps

_没有当前可复现的缺陷。此前的失败在同一浏览器重新提交后未复现；服务端记录、受控菜谱激活状态和当前页面输出均正常。_
