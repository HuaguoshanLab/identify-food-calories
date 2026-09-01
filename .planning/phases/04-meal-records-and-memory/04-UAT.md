---
status: diagnosed
phase: 04-meal-records-and-memory
source: 04-01-PLAN.md, 04-02-PLAN.md, 04-03-PLAN.md, 04-04-PLAN.md (execution summaries are missing)
started: 2026-08-31T12:03:49Z
updated: 2026-09-01T01:42:00Z
---

## Current Test

[testing complete]

## Tests

### 1. 显式保存并查看餐食记录
expected: 在完成分析后确认保存，详情和按日期分组的记录列表均显示同一份不可变营养快照。
result: pass

### 2. 餐食详情和编辑的历史栈返回
expected: 从“记录”进入“餐食记录”，再进入“编辑餐食”；连续两次“返回上一页”依次回到餐食记录和记录列表。
result: pass

### 3. 餐食记录删除确认与即时隐藏
expected: 编辑页删除按钮先显示不可逆确认弹窗；确认后该记录立即从详情和记录列表消失，且不会删除原分析会话。
result: pass

### 4. 长期偏好写入并在“我的”中可见
expected: 在分析时明确表达稳定偏好或忌口后，该偏好会保存；“我的 → 饮食偏好与记忆”显示来源和更新时间，不暴露内部 ID、原始对话或向量分数。
result: issue
reported: "不符合 我写了 我不吃辣，点击分析，然后去饮食偏好与记忆中并没有保存"
severity: major

### 5. 长期偏好编辑和删除
expected: 打开一条长期偏好可修改文字，保存后来源显示为“用户手动维护”；删除经确认后立刻从列表消失，后续建议不再引用它。
result: skipped
reason: "验收 4 未将明确忌口写入长期记忆，因此没有可编辑或删除的记录。"

## Summary

total: 5
passed: 3
issues: 1
pending: 0
skipped: 1
blocked: 0

## Gaps

- truth: "在分析时明确表达稳定偏好或忌口后，该偏好会保存，并在“我的 → 饮食偏好与记忆”中可见。"
  status: failed
  reason: "User reported: 不符合 我写了 我不吃辣，点击分析，然后去饮食偏好与记忆中并没有保存"
  severity: major
  test: 4
  root_cause: "分析图只检索已有的个人上下文，从未通过窄工具调用 MemoryService.create_direct()；该写入服务只有手动 POST /api/v1/memories 使用。"
  artifacts:
    - path: "backend/app/agent/graph.py"
      issue: "分析输入只触发个人上下文读取，没有用户直接表达的长期记忆写入节点或工具调用。"
    - path: "backend/app/memory/api.py"
      issue: "create_direct() 只由手动记忆 API 调用，Agent 运行链路不可达。"
  missing:
    - "在 Agent 窄工具边界增加用户直接表达的偏好写入能力，Graph 不直接访问 Repository。"
    - "将明确忌口/目标/稳定偏好映射为白名单 category 和 canonical_text，并保证 run 重放不重复写入。"
    - "补 Agent、真实 PostgreSQL API、浏览器/E2E 的写入、隔离、编辑和删除回归测试。"
  debug_session: ".planning/debug/phase-04-direct-memory-write.md"
