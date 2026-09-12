---
status: resolved
trigger: "选择候选食物后提交补充信息，没有返回营养结果"
created: 2026-09-12
updated: 2026-09-12
---

# Candidate Selection Resume Debug Session

## Symptoms

- expected: 用户选择候选“风干牛肉”并提交后，分析恢复、计算营养并展示报告。
- actual: 用户选择第一个候选后点击“提交补充信息”，页面没有返回结果。
- error: 当前截图未显示明确错误码或浏览器错误。
- timeline: 在 DashScope 向量空间激活并返回候选后发现。
- reproduction: 用户端输入“牛肉干 100g” → 选择“风干牛肉” → 点击“提交补充信息”。

## Current Focus

- hypothesis: 已验证：候选选择提交遗漏 catalog_version，后端因无法确认受控目录版本而将恢复视为无效。
- next_action: resolved

## Evidence

- timestamp: 2026-09-12T06:53:11Z
  observation: `AnalyzePage.submitClarification()` 原先只序列化 `{ candidate_id }`；候选对象本身已携带 `catalog_version`。
  implication: 前端提交体不完整。
- timestamp: 2026-09-12T06:53:11Z
  observation: `MealAnalysisGraph._apply_resume()` 要求 food answer 同时含 `candidate_id` 和与候选匹配的 `catalog_version`；缺任一字段直接原样返回 waiting state。
  implication: API 仍返回成功接受状态，但图不推进，正好解释页面没有结果且没有显式错误。
- timestamp: 2026-09-12T06:53:11Z
  observation: 新增前端回归测试选择“风干牛肉（not_specified）”后，断言提交 `candidate_id` 与 `catalog_version` 并能刷新为完成报告；Vitest 16/16 通过，TypeScript typecheck 通过。
  implication: 受影响路径已覆盖。

## Eliminated

## Resolution

- root_cause: 前端在候选食物恢复请求中漏传 `catalog_version`，而后端为防止跨目录版本误选，合法地将该请求视为无效并保持等待状态。
- fix: 从已选候选对象提取并与 `candidate_id` 一起提交 `catalog_version`。
- verification: `npm test -- --run src/features/agent/components/AnalyzePage.test.tsx`（16 passed）；`npm run typecheck`（passed）。真实浏览器验证未执行：本机 5178/8000 服务均未运行。
- files_changed: frontend/src/features/agent/components/AnalyzePage.tsx; frontend/src/features/agent/components/AnalyzePage.test.tsx
