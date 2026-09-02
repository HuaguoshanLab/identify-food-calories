---
phase: 06-user-dashboard-admin
plan: 06
subsystem: ui
tags: [react, typescript, zod, sse, accessibility, playwright]
requires:
  - phase: 06-user-dashboard-admin
    provides: Versioned safe-stream-stage.v1 SSE DTO and allowlisted Agent lifecycle mapping
provides:
  - Strict Zod parsing for safe SSE stage events at both H5 feature boundaries
  - Shared, accessible five-stage renderer with local allowlisted Chinese copy
  - Real-browser analysis and planning safety-progress regression coverage
affects: [frontend, agent-stream, diet-planning, UI-03]
tech-stack:
  added: []
  patterns: ["Strict SSE DTO parsing before component state", "Local stage-copy allowlist rather than rendering server messages", "One explicit retry without automatic retry loops"]
key-files:
  created:
    - frontend/src/features/agent/api/stream.ts
    - frontend/src/features/agent/components/SafeProgressStages.tsx
    - frontend/src/features/plans/api/stream.ts
    - frontend/src/features/plans/components/SafePlanningProgress.tsx
  modified:
    - frontend/src/features/agent/stream/useAgentEventStream.ts
    - frontend/src/features/agent/components/AnalyzePage.tsx
    - frontend/src/features/plans/components/PlanPage.tsx
    - frontend/tests/e2e/safe-stream-progress.spec.ts
key-decisions:
  - "SSE 的 message 即使来自安全后端也不直接渲染；页面只按本地 allowlist 阶段文案展示。"
  - "未知或附加字段立即转为一次通用可重试状态，并消费该事件序号，避免泄露和无限重连。"
  - "等待补充与终止范围不显示完成，也不自动重试；仅 retryable 露出一次显式重试控件。"
patterns-established:
  - "共享 SafeProgressStages 承担阶段语义与 aria-live，feature adapter 只拥有本地业务文案。"
  - "异步提交结束后恢复提交控件焦点，状态播报不抢占 H5 唯一滚动区。"
requirements-completed: [UI-03]
duration: 22min
completed: 2026-09-02
---

# Phase 06 Plan 06: H5 流式安全进度呈现 Summary

**分析与规划 H5 现在把严格校验过的 versioned SSE 阶段映射成可访问的五阶段本地文案，不显示模型、Provider、节点或原始事件。**

## Performance

- **Duration:** 22 min
- **Started:** 2026-09-02T10:04:00Z
- **Completed:** 2026-09-02T10:26:00Z
- **Tasks:** 2/2
- **Files modified:** 19

## Accomplishments

- 两条 feature API 边界都以 strict Zod 解析 `safe-stream-stage.v1`，拒绝额外字段与未知阶段。
- 共享五阶段进度 renderer 以本地 allowlist 展示感知、等待、计算、校验和完成；仅变化阶段使用 `aria-live="polite"`。
- retryable 状态提供一次显式重试；等待补充、范围终止和未知事件不会伪造完成或触发无限重连。
- 真实 Playwright 路径通过页面注册、Mailpit 验证、登录与公开 API 验证分析完成、规划安全可重试状态、无内部文本和提交焦点。

## Task Commits

1. **Task 1: 为两条流写 safe-stage 渲染 RED 测试** — `d1f6589` (`test`)
2. **Task 2: 接线安全阶段组件和流客户端** — `f4b1c6e` (`feat`)

## Files Created/Modified

- `frontend/src/features/agent/api/stream.ts` — Agent SSE 严格 DTO Schema 与解析入口。
- `frontend/src/features/agent/components/SafeProgressStages.tsx` — 共享五阶段语义、静态安全文案与受控重试。
- `frontend/src/features/plans/api/stream.ts` — 规划 feature 的独立严格 SSE 边界。
- `frontend/src/features/plans/components/SafePlanningProgress.tsx` — 规划业务文案 adapter。
- `frontend/src/features/agent/stream/useAgentEventStream.ts` — 传输层只交付通过严格校验的阶段，未知事件安全失败。
- `frontend/src/features/agent/components/AnalyzePage.tsx`、`frontend/src/features/plans/components/PlanPage.tsx` — 在真实 H5 流接线阶段 UI。
- `frontend/tests/e2e/safe-stream-progress.spec.ts` — 真实认证、公开 API 的双路径安全回归。

## Decisions Made

- SSE 文本不会直接进入 UI；前端只按已知 stage 展示本地、可审查文案。
- 共享组件负责阶段顺序和播报，规划只适配产品措辞，避免两条流的可访问性行为漂移。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 阶段切换会丢失初始提交控件焦点**
- **Found during:** Task 2 的真实浏览器 E2E
- **Issue:** 异步完成后 React 重渲染使“开始分析”和“生成今日餐单”不再保持键盘焦点。
- **Fix:** 在提交完成后的 animation frame 恢复对应提交控件焦点；live region 保持非侵入式。
- **Files modified:** `frontend/src/features/agent/components/AnalyzePage.tsx`, `frontend/src/features/plans/components/ProfileGoalForm.tsx`
- **Verification:** 隔离端口真实 Playwright E2E 两个路径均通过焦点断言。
- **Committed in:** `f4b1c6e`

**2. [Rule 1 - Bug] 旧传输测试仍假定未版本化的 type/summary SSE 格式**
- **Found during:** Task 2 的 typecheck 与 stream 测试
- **Issue:** 测试不会覆盖新 strict DTO，且会阻断类型检查。
- **Fix:** 改为 versioned stage payload，并保留 fragmented SSE、去重和序号缺口恢复断言。
- **Files modified:** `frontend/src/features/agent/stream/useAgentEventStream.test.ts`, `frontend/src/features/agent/components/AnalyzePage.test.tsx`
- **Verification:** 5 个相关 Vitest 文件、22 项测试全部通过。
- **Committed in:** `f4b1c6e`

**3. [Rule 2 - Project convention] 同步 feature 文件索引与缺失 API 目录说明**
- **Found during:** Task 2
- **Issue:** 新增 SSE 文件后目录 README 索引不完整，且规划 API 目录缺少职责说明。
- **Fix:** 更新现有索引，并新增 `frontend/src/features/plans/api/README.md`。
- **Files modified:** feature API/components 与 E2E README。
- **Verification:** README 合同所要求的职责、允许依赖和文件索引均已记录。
- **Committed in:** `f4b1c6e`

**Total deviations:** 3 auto-fixed（2 Rule 1，1 Rule 2）。
**Impact on plan:** 全部修复直接保障进度安全、可访问性与项目目录约束；无架构扩张。

## Issues Encountered

- 默认 8000 端口已被外部进程占用。Playwright 配置禁止复用未知服务，因此改用隔离的 `8016/5186` 端口运行完整服务栈。
- 当前 Fake Provider 的真实规划请求返回安全 `retryable` 状态，而不是完成计划；E2E 明确验证该状态不伪造“计划已生成”。这与 Phase 05 已记录的规划链路问题一致，不是本计划新引入的问题。

## Browser Verification

- Codex 内置浏览器确认实际产品入口 `http://127.0.0.1:5178/` 可访问。
- 隔离 Playwright Chromium 通过实际页面与公开 API 完成注册、Mailpit 验证、登录、分析和规划提交流程；未直写数据库、未伪造 token。
- 分析路径显示安全阶段并保持提交焦点；规划路径安全落入可重试状态且不显示完成或技术细节。

## Known Stubs

None.

## Next Phase Readiness

- UI-03 的前端阶段边界、可访问 renderer 和真实浏览器回归已就绪。
- 后续流 UI 必须复用 strict stage parser 和本地文案模式；不得渲染 SSE `message`、Provider、Graph State 或 raw payload。

## Self-Check: PASSED

- 已确认四个关键新增文件存在。
- 已确认 `d1f6589` 和 `f4b1c6e` 两个任务提交存在于 Git 历史。
