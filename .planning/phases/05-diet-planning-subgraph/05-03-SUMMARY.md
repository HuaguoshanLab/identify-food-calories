---
phase: 05-diet-planning-subgraph
plan: "03"
subsystem: plans-h5
tags: [react, typescript, react-hook-form, zod, tanstack-query, vitest, h5]
requires:
  - phase: 05-02
    provides: "严格 DietPlanningStartCommand 与显式 save_profile 语义"
  - phase: 05-07
    provides: "只读 planning profile prefill 与偏好不进入 profile 的公开边界"
provides:
  - "H5 首轮资料、目标、公式、活动和保守速度的 RHF/Zod 复核表单"
  - "已确认 memory 摘要、显式保存意图和仅向 Agent 启动端点发送的严格命令"
  - "关闭未知字段的前端 DTO、safe-event schema 与权威服务端字段错误映射"
affects: [plans-route, planning-result, personal-profile, h5-acceptance]
tech-stack:
  added: []
  patterns: ["closed Zod public DTO", "RHF profile-review boundary", "read-only memory cross-feature API", "explicit persistence intent"]
key-files:
  created:
    - frontend/src/features/plans/api/schemas.ts
    - frontend/src/features/plans/api/client.ts
    - frontend/src/features/plans/components/ProfileGoalForm.tsx
    - frontend/src/features/plans/components/ProfileGoalForm.test.tsx
  modified:
    - frontend/src/features/README.md
    - frontend/src/features/memory/README.md
key-decisions:
  - "计划表单只读取 /planning/profile 作为预填，提交始终只走 /agent/threads/diet-planning；不从浏览器直接写 profile。"
  - "忌口与口味只由 memory 的公开只读 API 汇总，用户必须勾选复核后才能启动计划。"
  - "save_profile 默认 false，即使资料来自已保存 prefill 也不会隐式改变持久化状态。"
patterns-established:
  - "跨 feature 只消费具名公开 API，并在双方 README 记录只读依赖和禁止的写入边界。"
  - "将 FastAPI 422 的 body/profile field 路径映射回 RHF 字段，保留服务端作为最终权威。"
requirements-completed: [PLN-01, PLN-02, PLN-06]
duration: 7min
completed: 2026-09-01
---

# Phase 5 Plan 03: H5 首轮资料与偏好复核表单 Summary

**以 RHF/Zod 完整复核身体资料和只读饮食偏好，显式选择保存后才随严格 Agent start command 提交的 H5 输入边界。**

## Performance

- **Duration:** 7 min
- **Started:** 2026-09-01T08:34:34Z
- **Completed:** 2026-09-01T08:41:11Z
- **Tasks:** 2/2
- **Files modified:** 9

## Accomplishments

- 创建 `features/plans/` 的 API 与组件边界，以及父目录、API、组件 README 索引；计划功能不再依赖 Placeholder 的扩张。
- 以可见标签和单位呈现身高、体重、年龄、显式公式选项、五档活动示例、目标及保守速度；所有关键触控控件保持 44px 高度和语义 token 样式。
- 用 TanStack Query 读取 profile prefill 和 memory 公共摘要；忌口/口味没有文本框、删除 chip 或写入接口，真实链接仍指向 `/app/me/memories`。
- 提交前必须确认偏好；默认 `save_profile=false`，无论 true/false 均只调用 Agent start endpoint，由后端处理唯一的持久化决定与幂等性。
- Zod closed DTO 验证 profile、start command 和安全事件；422 field errors 映射回对应 RHF 字段，浏览器端不替代服务端健康/数值判断。

## Task Commits

1. **Task 1: 写首轮资料、偏好复核和显式保存的 RED 组件合同** — `264fe77` (`test`)
2. **Task 2: 实现严格 public client 与 ProfileGoalForm** — `4af3c1a` (`feat`)

## Files Created/Modified

- `frontend/src/features/plans/api/schemas.ts` — closed profile/start/safe-event schemas 与表单合同。
- `frontend/src/features/plans/api/client.ts` — profile prefill、启动命令、Idempotency-Key 与安全错误投影。
- `frontend/src/features/plans/components/ProfileGoalForm.tsx` — 复核表单、只读偏好摘要和显式保存控制。
- `frontend/src/features/plans/components/ProfileGoalForm.test.tsx` — 可见文案、请求历史、无静默 profile mutation 及服务端字段错误测试。
- `frontend/src/features/{README.md,memory/README.md,plans/**/README.md}` — feature 责任、公开依赖和目录索引。

## Decisions Made

- `save_profile` 只作为 Agent start command 的显式布尔意图；客户端没有 PUT/PATCH profile mutation，因此预填与持久化不会混淆。
- 公式参数不可推断，活动固定五档，速度固定三档保守 enum；客户端不计算目标、不推断公式。
- 计划 feature 仅调用 memory 的 `listMemories` 公开读取接口，双方 README 记录该依赖，保证偏好编辑仍只有 memory 页面。

## Verification

- `cd frontend && npm run typecheck` — passed。
- `cd frontend && npm run lint` — passed。
- `cd frontend && npm test -- --run src/features/plans/components/ProfileGoalForm.test.tsx` — 3 passed。
- 浏览器验收由 Plan 06 在 `/app/plans` 路由接线完成；本计划只提供尚未挂载路由的受测组件，未宣称完成真实页面验收。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test contract] 修正服务端字段错误测试的不可达输入**
- **Found during:** Task 2（实现严格 public client 与 ProfileGoalForm）
- **Issue:** RED 测试将身高改为 `99`；该值会先被客户端的安全边界拒绝，无法真正验证服务端 422 字段错误映射。
- **Fix:** 使用有效预填资料触发模拟的服务端 422，测试实际的权威错误显示路径。
- **Files modified:** `frontend/src/features/plans/components/ProfileGoalForm.test.tsx`
- **Verification:** 组件测试 3/3 通过。
- **Committed in:** `4af3c1a`（part of task commit）

**2. [Rule 2 - AGENTS.md feature-isolation documentation] 登记 plans → memory 的只读公开 API 依赖**
- **Found during:** Task 1（写首轮资料、偏好复核和显式保存的 RED 组件合同）
- **Issue:** 项目架构要求跨 feature 的具名公开 API 依赖在双方 README 登记；原计划只列出了 plans 侧四个 README。
- **Fix:** 同步更新 `memory/README.md`，限定 plans 只能调用 `listMemories`，禁止 memory 写入与第二编辑器。
- **Files modified:** `frontend/src/features/memory/README.md`
- **Verification:** lint、typecheck 和组件请求历史测试通过。
- **Committed in:** `264fe77`（part of task commit）

---

**Total deviations:** 2 auto-fixed（Rule 1: 1；Rule 2: 1）。
**Impact on plan:** 两项均保证测试真实覆盖和 feature 隔离文档完整性，没有新增产品能力。

## Issues Encountered

None — the initial RED import failure was expected TDD behavior and the completed scoped verification is clean.

## Known Stubs

None — 本计划代码不渲染空的餐单、mock 结果或占位资料；等待后续路由接线时只暴露可验证的输入组件。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 06 可以将 `ProfileGoalForm` 接入真实 `/app/plans` 页面并以其 `onStarted` 回调消费安全快照；路由接线后必须用内置浏览器走真实公开 API 验收成功与错误路径。后续个人资料页只能复用公开 profile 边界，不得复制偏好编辑。

## Self-Check: PASSED

- 已确认 `schemas.ts`、`client.ts`、`ProfileGoalForm.tsx` 和组件测试存在。
- 已确认任务提交 `264fe77` 与 `4af3c1a` 存在于 Git 历史。
- 已扫描本计划文件；唯一空字符串是目标速度 select 的“请选择保守预设”无效选项，不流向 UI 结果，也不是 stub。

---
*Phase: 05-diet-planning-subgraph*
*Completed: 2026-09-01*
