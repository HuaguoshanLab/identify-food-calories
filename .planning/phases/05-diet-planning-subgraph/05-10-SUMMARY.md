---
phase: 05-diet-planning-subgraph
plan: "10"
subsystem: ui
tags: [react, typescript, zod, tanstack-query, h5, accessibility]
requires:
  - phase: 05-04
    provides: safe same-thread adjustment snapshots, closed meal choices, relaxation projection, and replan limit
  - phase: 05-09
    provides: validated initial plan report, meal cards, and planning-page route
provides:
  - same-thread H5 adjustment submission and safe snapshot refresh
  - visible local replacement, contained ambiguity, relaxation, limit, and refusal states
  - client-side fourth-adjustment guard with no constraint or health-boundary override
affects: [planning-ui, agent-api, playwright-uat]
tech-stack:
  added: []
  patterns: [strict-safe-dto-parsing, snapshot-derived-replacement-summary, focused-terminal-alert]
key-files:
  created: []
  modified:
    - frontend/src/features/plans/api/schemas.ts
    - frontend/src/features/plans/api/client.ts
    - frontend/src/features/plans/components/PlanPage.tsx
    - frontend/src/features/plans/components/MealCard.tsx
    - frontend/src/features/plans/components/PlanningStatus.tsx
    - frontend/src/features/plans/components/PlanPage.test.tsx
    - frontend/tests/e2e/plans.spec.ts
key-decisions:
  - "调整沿用既有 owned-thread /input API；浏览器只提交文本或封闭的三餐选择。"
  - "旧菜名由上一次已验证安全快照与新快照对比得出，不要求后端暴露原始反馈或内部候选。"
  - "仅安全 DTO 中的 energy/macro relaxation 字段可展示；忌口、明确排除与健康边界没有客户端放宽路径。"
patterns-established:
  - "Planning snapshot parsing accepts only the complete, needs-input, limit, and safe adjustment projections needed by the H5."
  - "Replacement completion moves focus to a polite summary while unchanged meal slots stay in their fixed order."
requirements-completed: [PLN-04, PLN-05, PLN-06]
duration: 9min
completed: 2026-09-01
---

# Phase 5 Plan 10: H5 调整、放宽、上限及高风险拒绝状态 Summary

**H5 计划页现在可在同一受控线程内安全调整单餐，并透明展示目标放宽、三次上限与高风险拒绝。**

## Performance

- **Duration:** 9 min
- **Started:** 2026-09-01T09:19:46Z
- **Completed:** 2026-09-01T09:27:52Z
- **Tasks:** 2/2
- **Files modified:** 7

## Accomplishments

- RED 合同覆盖午餐局部替换、歧义三餐选择、RELAX 四项事实、三次上限和拒绝无绕过。
- 调整 client 严格校验公开 DTO、使用当前 owned thread 刷新安全快照；UI 不发送或计算 constraint、exclusion、health 或 relaxation 决策。
- 受影响餐次显示“已调整”、旧菜/匹配约束/全天范围状态；成功后焦点移至礼貌摘要，未受影响餐次仍按早餐、午餐、晚餐顺序保留。
- 放宽告警只显示 energy/macro 的原范围、计划值、偏离和安全理由，并明确忌口与显式排除未放宽；第四次调整入口被替换为新建计划和个人资料操作。

## Task Commits

1. **Task 1: 写同线程调整恢复的 RED H5 合同** — `5bb17f1` (`test`)
2. **Task 2: 实现严格 adjustment client 和受控恢复界面** — `03df25b` (`feat`)

## Verification

- PASS — `cd frontend && npm test -- --run src/features/plans/components/PlanPage.test.tsx` — 6 tests passed.
- PASS — `cd frontend && npm run typecheck`.
- PASS — `cd frontend && npm run lint`.
- BLOCKED (environment) — `cd frontend && npm run test:e2e -- --grep "phase 5 daily planning H5"`; Playwright's isolated web server rejects the already-occupied `127.0.0.1:8000` process. The shared-process rule forbids stopping it. A sandbox retry also confirmed the project can access its existing Docker stack when permitted.

## Files Created/Modified

- `frontend/src/features/plans/api/{schemas.ts,client.ts}` — strict adjustment command/response validation and owned-thread submission.
- `frontend/src/features/plans/components/PlanPage.tsx` — safe snapshot recovery, local replacement, ambiguity, relaxation, limit, and refusal UI.
- `frontend/src/features/plans/components/{MealCard.tsx,PlanningStatus.tsx}` — affected-slot details and focusable terminal alert.
- `frontend/src/features/plans/components/PlanPage.test.tsx` — safety and accessibility recovery contracts.
- `frontend/tests/e2e/plans.spec.ts` — real owned-thread local-replacement browser path.

## Decisions Made

- 复用公开 `/agent/threads/{thread_id}/input`，不新增平行调整 endpoint 或事件解析器。
- 旧菜信息只从相邻的安全结果快照推导，避免把 provider、tool、ledger、raw feedback 或内部 ID 渲染进页面。
- 高风险拒绝保持可编辑资料表单，用户可以修正误填基本资料；结果卡、调整表单和任何绕过操作都不会出现。

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None — 恢复界面使用真实公开 Agent API 的安全投影，不依赖 mock 数据或空展示字段。

## Issues Encountered

- Playwright 验证受共享的 `127.0.0.1:8000` 进程阻塞。未终止未知进程，避免破坏其他并行任务；组件测试、类型检查和 lint 已通过。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 真实 H5 的调整路径可在端口空闲后运行 `plans.spec.ts` 完成 Playwright 复验。
- Plan 06 的内置浏览器完整路径验收仍应覆盖实际注册、生成、局部替换、RELAX、上限和健康拒绝状态。

## Self-Check: PASSED

- 已确认 `PlanPage.tsx`、`MealCard.tsx`、`PlanningStatus.tsx`、`schemas.ts`、`client.ts`、组件测试和 Playwright 测试均存在。
- 已确认任务提交 `5bb17f1` 与 `03df25b` 均在 Git 历史中存在。
