---
phase: 05-diet-planning-subgraph
verified: 2026-09-02T03:45:04Z
status: human_needed
score: 4/5 roadmap must-haves verified
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 5/5
  gaps_closed: []
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "在可生成三餐的隔离合成账号中，滚到调整区，提交一次午餐调整。"
    expected: "午餐显示已调整，早餐和晚餐保持原样；polite 完成通知不获得焦点，page-scroll-area 的 scrollTop 不回到顶部。"
    why_human: "隔离 Playwright 在生成三餐之前显示通用错误，未执行本计划新增的滚动、焦点和局部替换断言。"
  - test: "恢复前端依赖后，重跑 PlanPage Vitest、typecheck、lint 和隔离 plans.spec.ts。"
    expected: "组件/静态门禁仍通过；E2E 到达今日三餐计划并运行 scrollTop 断言。"
    why_human: "本次复核环境没有 frontend/node_modules，vitest、tsc、eslint 均不可执行；不能把执行摘要的历史通过结果伪装成此次复跑结果。"
---

# Phase 5: 饮食规划子图复验报告

**Phase Goal:** Agent 根据用户目标和偏好生成可校验、可交互调整的一日三餐方案。
**Verified:** 2026-09-02T03:45:04Z
**Status:** human_needed（代码修复已验证，端到端闭环未验证）
**Re-verification:** Yes — UAT-05 滚动劫持修复后复验

> MVP 元数据与工作流格式存在历史不一致：路线图将 Phase 5 标为 `mvp`，但 Goal 不是规定的 user-story 格式。以下按路线图五项可观察结果和 05-11 的 UAT 缺口复核；这不替代后续将 Goal 规范化为用户故事的工作。

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | 身体数据与目标经确定性公式生成每日能量和宏量营养约束。 | ✓ VERIFIED | 05-11 仅修改前端完成通知及其测试；`bfe962b` 没有改动任何后端、目标公式、API 或配置。此前已验证的确定性链无本次回归迹象。 |
| 2 | 规划子图检索受控菜谱，生成餐单并用工具校验总量、比例、忌口和重复度。 | ✓ VERIFIED | 05-11 提交范围仅为 `PlanPage.tsx`、其组件测试和 `plans.spec.ts`；代码 diff 未触及图、受控菜谱或校验服务。 |
| 3 | 不合格方案仅在有限次数内重排，之后给出可解释失败结果。 | ✓ VERIFIED | `PlanPage.tsx` 仍保留既有 `limitReached`/`FocusedPlanningAlert` 分支；本次 diff 未触及线程、重排计数或拒绝路径。 |
| 4 | 用户反馈“换清淡”“不吃某菜”后，保留其他约束并恢复图继续规划。 | ? UNCERTAIN | 局部 UI 路径有实质代码和 mocked 组件合同：`submitAdjustment()` 将同一 `threadId` 发往 `/input`，安全快照的 `changed_slots` 驱动单餐标记，测试断言午餐更新、早餐/晚餐仍在。可是真实隔离 E2E 在初始三餐生成前失败，未执行局部替换、焦点或滚动断言；UAT-05 仍是 `issue`。 |
| 5 | 输出明确声明非医疗建议，并拒绝高风险健康请求。 | ✓ VERIFIED | 修复保留页首和页尾免责声明、既有 `statusKind === 'refusal'` 分支；`bfe962b` 没有改动这些安全边界。 |

**Score:** 4/5 roadmap truths verified；第 4 项是 **UNCERTAIN**，不是通过。

## UAT-05 Gap-Closure Evidence

| Check | Result | Evidence |
| --- | --- | --- |
| 原因是否真实移除 | ✓ VERIFIED | `bfe962b` 删除 `summaryRef`、`updatedSlot` 的 `focus()` effect 和 live region 的 `ref`/`tabIndex`。现存 `PlanPage.tsx:86` 的 `headingRef.current?.focus()` 只在首次进入页执行，是计划明确要求保留的标题焦点，不能误判为回归。 |
| 非侵入式通知是否保留 | ✓ VERIFIED | `PlanPage.tsx:158` 仅在 `updatedSlot` 存在时渲染 `<p aria-live="polite" className="sr-only">`；没有 `tabIndex`、ref、`focus()`、`scrollIntoView()` 或滚动 API。 |
| 提交后焦点合同 | ✓ VERIFIED（mocked component） | `PlanPage.test.tsx:156-198` 在提交前保存/聚焦按钮，断言 completion summary 有 polite live region、没有 tabindex、不获得焦点，提交按钮仍为 active element。 |
| 局部餐次合同 | ✓ VERIFIED（mocked component） | 同一组件测试断言请求发送到 owned thread 的 `/input`，仅有一个“已调整”，并保留早餐与晚餐文本。 |
| 真正滚动位置合同 | ? NOT EXECUTED | `plans.spec.ts:42-81` 正确把 `page-scroll-area.scrollTop` 设为非零并在调整后比较，但其运行在第 58 行等待“今日三餐计划”时失败，未到第 65-81 行。 |

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `frontend/src/features/plans/components/PlanPage.tsx` | 不夺焦点的 polite live-region 局部调整完成提示 | ✓ VERIFIED | 161 行实质组件；`updatedSlot` 从严格解析的 safe snapshot 得到，只控制固定中文通知。完成通知已无 programmatic focus 路径。 |
| `frontend/src/features/plans/components/PlanPage.test.tsx` | 局部调整的非焦点 live-region 组件回归合同 | ✓ VERIFIED（组件层） | 260 行；导入并渲染真实 `PlanPage`，模拟 owned-thread snapshot 与 `/input`，明确验证非焦点与其他餐次不变。它不拥有真实 AppShell，因此不能单独验证 scrollTop。 |
| `frontend/tests/e2e/plans.spec.ts` | 真实公开用户路径的滚动位置和局部替换回归 | ⚠️ WIRED, NOT EXECUTED | 83 行；使用注册、Mailpit 激活、登录和页面交互，且选择唯一 `page-scroll-area`。失败产物显示 Agent 生成通用可重试错误，断言入口未到达。 |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `PlanPage.tsx` | `PlanPage.test.tsx` | `updatedSlot` completion announcement | ✓ WIRED | 测试导入 `PlanPage` 并通过 HTTP mock 驱动 `changed_slots: ['lunch']` 的安全快照；断言渲染的 live region 和 active element。`gsd-sdk verify.key-links` 的“Target not referenced”是把测试关系错误当成源码 import，不构成断链。 |
| `plans.spec.ts` | `[data-testid="page-scroll-area"]` | 调整前后 `scrollTop` | ✓ WIRED, execution blocked | 第 64-78 行定位唯一滚动区、记录非零 scrollTop、比较更新后的值；运行时被初始 Agent 生成失败阻断。 |
| `submitAdjustment()` | 受所有权约束的同一 planning thread | `POST /agent/threads/{threadId}/input` 后读取 safe snapshot | ✓ WIRED（代码） | `PlanPage.tsx:132-141` 调用 `submitDietPlanningAdjustment` 后读取同一 thread；`api/client.ts:29-45` 运行时校验 description payload，并使用公开 API。真实 E2E 未走到这里。 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `PlanPage.tsx` | `updatedSlot` | `/agent/threads/{threadId}` 的 safe snapshot → `planReportSchema` → `adjustment.changed_slots[0]` | 组件逻辑只接受严格 schema 的单个 slot，而非文本或内部事件 | ✓ FLOWING（代码/组件 mock） |
| `MealCard` 映射 | `report.meals` 和 `mealAdjustment` | 同一 safe snapshot 与上一次 report 的受影响 slot | 组件测试使 lunch 替换而早餐/晚餐保持 | ✓ FLOWING（组件 mock） |
| AppShell 滚动区 | `scrollTop` | 真实浏览器 DOM | Playwright 已有读取与比较代码，但实例化三餐计划失败 | ⚠️ DISCONNECTED AT E2E ENTRY |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| 非焦点完成通知组件回归 | `cd frontend && npm test -- --run src/features/plans/components/PlanPage.test.tsx` | 05-11 执行记录为 7 passed；本复核环境运行时 `vitest: command not found`，因为 `frontend/node_modules` 缺失。 | ? NOT RE-RUN |
| TypeScript | `cd frontend && npm run typecheck` | 05-11 执行记录为 PASS；本复核环境运行时 `tsc: command not found`，因为依赖缺失。 | ? NOT RE-RUN |
| Lint | `cd frontend && npm run lint` | 05-11 执行记录为 PASS；本复核环境运行时 `eslint: command not found`，因为依赖缺失。 | ? NOT RE-RUN |
| 隔离公开 E2E | `E2E_BACKEND_PORT=8001 E2E_FRONTEND_PORT=5179 npm exec playwright test tests/e2e/plans.spec.ts` | 两条用例在“今日三餐计划”出现前超时；保存的 Playwright error context 显示页面 alert 为“暂时无法生成计划，请检查资料和网络后重试”。 | ✗ BLOCKED BEFORE TARGET ASSERTION |

### Probe Execution

Step 7c: SKIPPED — 仓库没有 `scripts/` 或 Phase 5 声明的 `probe-*.sh`。

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| PLN-01 | 01, 03, 05, 07, 09 | 用户提交资料/目标/偏好 | ✓ SATISFIED (regression only) | 05-11 不修改资料、表单或 API。 |
| PLN-02 | 01, 02, 08, 09 | 确定性目标计算 | ✓ SATISFIED (regression only) | 05-11 不修改计算或后端。 |
| PLN-03 | 02, 08, 09 | 受控菜谱与三餐候选 | ✓ SATISFIED (regression only) | 05-11 不修改受控菜谱、检索或组合服务。 |
| PLN-04 | 01, 02, 04, 08, 10 | 有界确定性校验与重排 | ✓ SATISFIED (regression only) | 05-11 不修改校验或重排路径。 |
| PLN-05 | 04, 06, 10, 11 | 自然语言局部替换并保留约束 | ? NEEDS HUMAN | 修复代码和 mock 合同成立；真实生成/调整路径被隔离 E2E 前置失败阻断，不能宣称 UAT-05 已关闭。 |
| PLN-06 | 01–06, 09, 10 | 非医疗说明与医疗边界 | ✓ SATISFIED (regression only) | 免责声明及 refusal 分支未被本次修复改变。 |

`REQUIREMENTS.md` 中 PLN-01..04、PLN-06 的复选状态仍未同步为完成；这是追踪文档不一致，未把它改写成实现缺陷或本次自动“通过”。

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `PlanPage.tsx` | 86 / 150 | 首次页面标题的 `focus()` 与 `tabIndex={-1}` | ℹ️ Intentional | 这是初始页面焦点管理，计划要求保留；没有依赖 `updatedSlot`，不再导致提交调整后的滚动劫持。 |

未发现本计划范围内未指向正式后续工作的 `TBD`、`FIXME`、`XXX`、空实现或 placeholder。

### Human Verification Required

#### 1. UAT-05 的真实调整闭环

**Test:** 在隔离的合成账号完成生成三餐后，滚动到调整区，提交一次午餐调整。

**Expected:** 完成通知由辅助技术礼貌播报且不获得焦点；午餐标为已调整；早餐和晚餐不变；`page-scroll-area` 不跳回顶部。

**Why human:** 自动 E2E 在三餐生成前即失败，当前没有真实用户会话或资料的浏览器复验；不得将 mock 组件测试当成实际浏览器验收。

#### 2. 恢复本地依赖后的自动回归

**Test:** 恢复 `frontend` 的锁定依赖后，重跑 Vitest、typecheck、lint 与隔离 Playwright。

**Expected:** 三个静态/组件门禁通过，且 Playwright 到达本次新增的 scrollTop、焦点和单餐替换断言。

**Why human:** 本次 verifier 进程缺少开发依赖；不应通过联网安装或用摘要替代独立运行结果。

## Conclusion

**结论：PARTIAL / BLOCKED，不能宣布 Phase 5 已完全 achieved。**

UAT-05 的直接根因已在代码中被精确移除，新的组件和 Playwright 合同也确实覆盖“通知不夺焦点、午餐局部替换、唯一滚动区不回顶”。但隔离的真实公开路径在生成三餐前显示通用错误，目标滚动断言一次也没有运行；同时本复核环境无法独立重跑前端静态门禁。需要先恢复隔离 Agent 生成路径和前端依赖，再完成合成账号浏览器复验，方可把此 UAT 缺口标为关闭。

---

_Verified: 2026-09-02T03:45:04Z_
_Verifier: the agent (gsd-verifier)_
