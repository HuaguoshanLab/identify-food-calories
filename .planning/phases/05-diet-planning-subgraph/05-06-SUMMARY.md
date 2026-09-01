---
phase: 05-diet-planning-subgraph
plan: "06"
subsystem: testing
tags: [pytest, vitest, playwright, react, fastapi, postgres, mailpit, documentation]
requires:
  - phase: 05-04
    provides: "same-thread local adjustment, safe snapshot/SSE projection, bounded recovery, and memory capture"
  - phase: 05-05
    provides: "owner-scoped profile CRUD and deletion cache semantics"
  - phase: 05-09
    provides: "three-meal H5 report, controlled MealCard, and safe status UI"
  - phase: 05-10
    provides: "H5 adjustment, relaxation, limit, and refusal projections"
provides:
  - "isolated, public register → Mailpit → login → planning/profile Playwright regression evidence"
  - "profile deletion empty-state route back to the single plan intake"
  - "Chinese teaching material for deterministic planning, safe graph recovery, deletion, and testing"
affects: [phase-05-acceptance, phase-06, h5-regression, security-review]
tech-stack:
  added: []
  patterns: ["validated dedicated E2E ports", "exact accessible E2E locators", "safe public user-path regression"]
key-files:
  created:
    - docs/learning/05-diet-planning-subgraph.md
  modified:
    - frontend/playwright.config.ts
    - frontend/tests/e2e/plans.spec.ts
    - frontend/tests/e2e/profile.spec.ts
    - frontend/src/features/plans/components/PersonalProfilePage.tsx
    - frontend/src/features/plans/components/PersonalProfilePage.test.tsx
    - docs/learning/README.md
key-decisions:
  - "Playwright defaults remain 8000/5178, but validated E2E_BACKEND_PORT/E2E_FRONTEND_PORT allow an isolated owned service when those ports are occupied."
  - "删除后的个人资料空态只链接到 /app/plans，保持首次资料录入的单一入口。"
  - "内置浏览器不在未取得即时确认时创建账号、提交合成健康资料或确认删除。"
patterns-established:
  - "E2E must target the full data-slot=card container and exact accessible names, rather than broad labels or heading parents."
  - "Browser acceptance uses a dedicated local stack and public authentication/API boundaries; unknown local services are never reused or stopped."
requirements-completed: [PLN-01, PLN-02, PLN-03, PLN-04, PLN-05, PLN-06]
duration: 35min
completed: 2026-09-01
---

# Phase 5 Plan 06: 最终回归、教学文档与浏览器验收 Summary

**规划三餐、局部调整和个人资料删除现有隔离的公开 E2E 证据；维护者可通过中文文档追踪确定性目标、受控菜谱、图恢复与敏感数据边界。**

## Performance

- **Duration:** 35 min
- **Completed:** 2026-09-01T09:39:31Z
- **Tasks:** 2/2（内置浏览器写操作因即时确认要求如实标记为待确认）
- **Files modified:** 7

## Accomplishments

- 运行后端 51 项跨层回归、前端类型/lint、9 项 plans 组件测试，以及隔离 8001/5179 上公开注册→Mailpit→登录→生成→调整→资料删除的 Playwright 3/3。
- 修正删除 profile 后仍在 detail 页面填写的职责偏差；空态现在真实链接到 `/app/plans`，不会形成第二条首次资料写入路径。
- Playwright 可通过受校验的 `E2E_BACKEND_PORT` 与 `E2E_FRONTEND_PORT` 启动自己的服务，避开并保留未知的 8000/5178 进程。
- 新增索引化中文教学文档，说明 API/Service/Repository/Model、Graph/tools、Decimal、checkpoint、Phase 4 memory authority、安全 SSE、拒绝与测试方式。

## Task Commits

1. **Task 1: 补齐跨层安全、D-08 和可访问性回归矩阵** — `a04afa4` (`test`), `9557cbd` (`fix`), `7162280` (`test`)
2. **Task 2: 执行真实浏览器验收并写中文教学文档** — `cc741b6` (`docs`); 内置浏览器的写操作等待即时确认，见下文。

## Files Created/Modified

- `frontend/playwright.config.ts` — 保留安全默认端口，支持经校验的隔离端口和 Vite 代理目标。
- `frontend/tests/e2e/{plans,profile}.spec.ts` — 公开用户路径、完整餐卡、局部替换、320/375/430/768 宽度与删除后计划入口。
- `frontend/src/features/plans/components/PersonalProfilePage.{tsx,test.tsx}` — 删除后的空态回归与唯一计划页入口。
- `docs/learning/05-diet-planning-subgraph.md`、`docs/learning/README.md` — 中文架构、安全与测试教学材料及索引。

## Verification

- PASS — `cd backend && uv run pytest tests/planning/test_planning_service.py tests/unit/test_diet_planning_graph.py tests/integration/test_planning_profile_api.py tests/integration/test_diet_planning_agent_api.py -q` — 51 passed。
- PASS — `cd frontend && npm run typecheck && npm run lint`。
- PASS — `cd frontend && npm test -- --run src/features/plans/components/PlanPage.test.tsx src/features/plans/components/PersonalProfilePage.test.tsx` — 9 passed。
- PASS — `cd frontend && E2E_BACKEND_PORT=8001 E2E_FRONTEND_PORT=5179 npm exec playwright test tests/e2e/plans.spec.ts tests/e2e/profile.spec.ts` — 3 passed；服务自行启动并关闭，未复用 8000/5178。

## Browser Verification Pending

已连接 Codex 内置浏览器和隔离的 `http://127.0.0.1:5179/app/plans` 服务，但没有执行写操作。浏览器安全策略要求在下列动作发生前取得用户即时确认：创建合成账号、向本地测试服务提交合成身体/目标资料，以及确认删除这个合成 profile。自动化 Playwright 已从公开认证和 API 证明该路径；本摘要不把它误报为内置浏览器验收通过。

恢复后应仅使用合成测试账号，验证：`/app/plans` 资料复核和三餐卡（标准名、份量、标签、约束、持续免责声明）→ 一次午餐局部调整 → `/app/me/profile` 删除 → 刷新空态与“去计划页填写”。不得删除既有用户资料或提交真实健康数据。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 删除资料后保留了第二条资料录入路径**
- **Found during:** Task 1
- **Issue:** 空态文案说应在计划页填写，却仍渲染“填写个人资料”按钮并进入 detail 内编辑，违反 D-05 的单一资料入口。
- **Fix:** 改为真实 `/app/plans` 链接，并以组件测试固定删除后的路由合同。
- **Files modified:** `frontend/src/features/plans/components/PersonalProfilePage.tsx`, `PersonalProfilePage.test.tsx`
- **Verification:** RED 测试先失败；修复后组件、typecheck 与 lint 通过。
- **Committed in:** `a04afa4`, `9557cbd`

**2. [Rule 1 - Bug] Playwright 使用模糊标签和标题父节点，无法证明完整餐卡**
- **Found during:** Task 1 的真实 E2E 首次运行。
- **Issue:** `体重` 匹配到了“维持体重”，标题父节点只包含标题；文本标准化还会让不变餐次比较误失败。
- **Fix:** 使用精确 spinbutton、精确标题和 `data-slot=card` 完整卡片 locator；以 rendered `innerText` 比较不变卡片。
- **Files modified:** `frontend/tests/e2e/plans.spec.ts`, `profile.spec.ts`
- **Verification:** 8001/5179 公开 E2E 3/3 通过。
- **Committed in:** `7162280`

**3. [Rule 3 - Blocking] E2E 端口硬编码会强迫复用或终止未知服务**
- **Found during:** Task 1
- **Issue:** 8000 和 5178 已被未知进程占用，`reuseExistingServer: false` 正确拒绝复用，但配置不能启动本计划自有服务。
- **Fix:** 增加格式校验的端口环境变量，并向 Vite 明确传入隔离 API proxy target；默认端口不变。
- **Files modified:** `frontend/playwright.config.ts`
- **Verification:** 配置单测、typecheck、lint 和 8001/5179 E2E 通过。
- **Committed in:** `7162280`

**Total deviations:** 3 auto-fixed（Rule 1: 2；Rule 3: 1）。所有变更都用于恢复真实用户路径、测试正确性或隔离安全，没有扩张产品功能。

## Issues Encountered

- sandbox 无权访问既有 uv cache 和 Docker；获授权后按既有依赖执行，代码未安装任何新包。
- 8000/5178 由未知进程占用；未停止、未复用，改用本计划拥有的 8001/5179。
- Vite 构建提示现有主 bundle 超过 500 kB；未由本计划引入，未在本计划范围内修改。

## Known Stubs

None — 新增的入口、配置和教学文档不含流向 UI 的 mock 数据或 placeholder。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 自动化回归与教学材料已具备；未来测试可在端口冲突时使用隔离端口，不触碰并行或用户服务。
- 内置浏览器的真实写路径只差用户即时确认；确认前不能宣称人工浏览器验收完成。

## Self-Check: PASSED

- 已确认 `docs/learning/05-diet-planning-subgraph.md`、`frontend/playwright.config.ts`、plans/profile E2E 和 profile 空态测试存在。
- 已确认 `a04afa4`、`9557cbd`、`7162280`、`cc741b6` 存在于 Git 历史。

---
*Phase: 05-diet-planning-subgraph*
*Completed: 2026-09-01*
