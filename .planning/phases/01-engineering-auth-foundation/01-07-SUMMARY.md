---
phase: 01-engineering-auth-foundation
plan: 07
subsystem: frontend-tooling
tags: [react, vite, tailwindcss, typescript, eslint, vitest, shadcn, base-ui]

requires:
  - phase: 01-engineering-auth-foundation/01-02
    provides: 独立 Vite React SPA、受审核前端依赖锁与 Playwright 生命周期
provides:
  - 真实执行的 TypeScript、ESLint、Vitest、React 与 Tailwind CSS v4 工具链
  - main.tsx 明确导入的 UI-SPEC Slate/Teal、0.5rem radius 与可访问性全局样式
  - 仅使用官方 shadcn Base UI registry 的配置、aliases 与可测试 cn utility
affects: [01-09, 01-10, 01-12, frontend-ui, authentication-ui]

tech-stack:
  added: [clsx 2.1.1, tailwind-merge 3.6.0]
  patterns: [single Vite build and test config, source-root aliases, official-registry-only shadcn]

key-files:
  created: [frontend/eslint.config.js, frontend/tsconfig.json, frontend/vite.config.ts, frontend/src/styles.css, frontend/src/test-setup.ts, frontend/components.json, frontend/src/components/ui/utils.ts]
  modified: [frontend/package.json, frontend/package-lock.json, frontend/src/main.tsx, frontend/src/App.tsx, frontend/README.md]

key-decisions:
  - "Vite 同时承载 React、Tailwind CSS v4 和 Vitest 配置，避免构建与测试解析出两套 alias 或插件行为。"
  - "shadcn 固定 base-nova/Base UI，components.json 不声明第三方 registries；Slate/Teal 与 0.5rem radius 由受版本控制的 styles.css 覆盖。"
  - "cn utility 放在 src/components/ui/utils.ts，alias 直接指向该文件，不创建无职责的 lib 目录。"

patterns-established:
  - "真实门禁：lint、typecheck、Vitest 与 production build 均必须执行并产生可观察证据。"
  - "目录即契约：components 与 components/ui 分层记录职责、允许依赖和文件索引。"

requirements-completed: [ARC-01, ARC-07]

duration: 13 min
completed: 2026-08-27
---

# Phase 1 Plan 7: 前端工具链与官方 shadcn 基座 Summary

**严格 TypeScript/ESLint/Vitest 与 Tailwind v4 共享同一 Vite 配置，UI-SPEC tokens 和官方 Base UI `cn` utility 已由生产构建与行为测试证明。**

## Performance

- **Duration:** 13 min
- **Started:** 2026-08-27T08:18:45Z
- **Completed:** 2026-08-27T08:31:32Z
- **Tasks:** 2
- **Files modified:** 17

## Accomplishments

- 建立可执行的 ESLint 10、TypeScript 6、Vitest 4/jsdom 与 Vite 8 配置；两项真实 Testing Library/utility 测试通过，而不是空测试套件假绿。
- `main.tsx` 明确导入 `styles.css`；Tailwind v4 production build 生成 CSS，包含 Slate/Teal、0.5rem radius、focus-visible 与 reduced-motion 契约。
- `components.json` 被 shadcn CLI 解析为 Vite、Tailwind v4、base-nova/Base UI，registry 只有官方 `@shadcn`；`cn` alias、依赖与冲突合并行为均验证通过。
- `npm ci` 从锁文件完整重建 571 个包，新增的两个直接依赖版本、registry URL 和 integrity 均精确核对，`npm audit` 为 0 vulnerabilities。

## Task Commits

1. **Task 1: 配置 Tailwind、ESLint、TypeScript 与 Vitest** - `ae4fbd9` (chore)
2. **Task 2: 建立官方 shadcn 配置与 cn utility** - `20bdffe` (feat)

## Files Created/Modified

- `frontend/eslint.config.js` - TypeScript、React Hooks 与 Vite refresh flat config。
- `frontend/tsconfig.json` - 浏览器、测试、严格空值与 `@/*` source alias 合约。
- `frontend/vite.config.ts` - React、Tailwind v4、Vitest/jsdom 和 alias 的单一配置入口。
- `frontend/src/styles.css` - Tailwind 入口、UI-SPEC tokens、focus 与 reduced-motion 全局基线。
- `frontend/src/main.tsx` - 在 React 挂载前明确接入生产样式入口。
- `frontend/src/App.test.tsx` - 真实健康响应与可访问状态的 Testing Library 测试。
- `frontend/src/test-setup.ts` - jest-dom 断言与测试后 DOM 清理。
- `frontend/components.json` - 官方 base-nova/Base UI registry、CSS 路径和 aliases。
- `frontend/src/components/ui/utils.ts` - 官方 `clsx` + `tailwind-merge` `cn` 实现。
- `frontend/src/components/ui/utils.test.ts` - 条件 class 与 Tailwind 冲突合并测试。
- `frontend/package.json` / `frontend/package-lock.json` - 可执行命令与 30 个精确直接依赖锁。
- frontend、src、components、components/ui README - 同步职责、允许依赖和文件索引。

## Decisions Made

- 不为 TypeScript 6 保留已废弃的 `baseUrl` 或用 `ignoreDeprecations` 压警告；`paths` 相对 tsconfig 解析，Vite 显式镜像同一 `@` alias。
- Vitest 只收集 `src/**/*.{test,spec}.{ts,tsx}`，避免把 Playwright spec 当 Vitest 用例加载；E2E 仍由独立 `test:e2e` 命令执行。
- shadcn 不创建通用 `lib/` 目录；官方组件需要的 utility 直接放入有明确安全边界的 `components/ui/`。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking strictness] 修复健康壳的可空响应访问**
- **Found during:** Task 1（首次 TypeScript strict typecheck）
- **Issue:** 原 `App.tsx` 在布尔别名之后访问 `health.data.version`，TypeScript 无法证明异步数据存在，真实 typecheck 失败。
- **Fix:** 在同一判别表达式内生成 `healthLabel`，让 `status === 'ok'` 直接收窄响应对象。
- **Files modified:** `frontend/src/App.tsx`
- **Verification:** `npm run typecheck`、Vitest 与 production build 全部通过。
- **Committed in:** `ae4fbd9`

**2. [Rule 2 - Missing critical test wiring] 增加真实 Vitest 收集边界与行为测试**
- **Found during:** Task 1（验证 test 脚本必须实际执行配置）
- **Issue:** 计划要求 Vitest 可执行，但原仓库没有单元测试；默认 `*.spec.ts` 收集还会错误加载 Playwright E2E，无法证明 jsdom/Testing Library 配置正确。
- **Fix:** 增加 App 行为测试、jest-dom/cleanup setup，并将 Vitest 收集限定到 `src/`；Task 2 再用 `cn` 测试证明 alias 与 utility 行为。
- **Files modified:** `frontend/src/App.test.tsx`, `frontend/src/test-setup.ts`, `frontend/src/components/ui/utils.test.ts`, `frontend/vite.config.ts`
- **Verification:** Vitest 2 files / 2 tests passed；Playwright spec 不再被错误收集。
- **Committed in:** `ae4fbd9`, `20bdffe`

---

**Total deviations:** 2 auto-fixed（1 Rule 2，1 Rule 3）。
**Impact on plan:** 两项均用于让计划声明的严格检查和测试成为真实门禁，没有扩展产品功能。

## Issues Encountered

- TypeScript 6 将 `baseUrl` 标记为将停止工作的废弃选项；删除该选项后保留标准相对 `paths`，没有用 suppression 掩盖升级问题。
- 沙箱内 npm/shadcn 无法解析外部 registry；在限定联网授权下执行相同精确命令后，安装、官方 registry 解析与漏洞审计通过。
- npm 重新求解 lockfile 中 AJV 的 hoist 位置；`npm ci --ignore-scripts` 完整重建成功，直接依赖版本与 integrity 未漂移。

## Authentication Gates

None.

## Known Stubs

None. 既有健康运行壳是 01-02 已交付的明确阶段边界，不阻碍本计划的工具链、CSS 与 UI utility 目标。

## User Setup Required

None - 不需要外部账号、密钥或手工生成步骤。

## Verification Evidence

- `npm ci --ignore-scripts` → 571 packages 从 lockfile 完整重建。
- `npm run lint` → ESLint 10 flat config 通过。
- `npm run typecheck` → TypeScript 6 strict/noEmit 通过。
- `npm test` → Vitest 2 files / 2 tests passed，无 skip。
- `npm run build` → Vite 8.2.2，69 modules transformed，CSS 5.34 kB，production build 通过。
- CSS 产物检查 → `--primary:#0d9488` 与 `--radius:.5rem` 存在；`main.tsx` 显式 import 存在。
- `shadcn info --json` → Vite、Tailwind v4、base-nova/Base UI、官方 `@shadcn` registry 与 `@/components/ui/utils` alias 均匹配。
- lockfile 审计 → 30 个直接依赖；`clsx@2.1.1`、`tailwind-merge@3.6.0` 的版本、官方 registry URL 与 integrity 通过；`npm audit` 0 vulnerabilities。

## Next Phase Readiness

- 01-09/01-10 可直接生成官方 Button、Input、Label、Card、Alert 等 Base UI 封装，并使用统一 `cn` 与 tokens。
- 前端功能计划必须维持 lint → typecheck → Vitest → production build 门禁，不得让 Vitest 收集 Playwright E2E。
- 无阻塞项。

## Self-Check: PASSED

- 17 个关键创建/修改文件均存在，`components/` 与 `components/ui/` 同次包含 README 索引。
- `ae4fbd9`、`20bdffe` 均可从 Git 历史解析，无意外删除。
- 计划级 lint、typecheck、2 项 Vitest、CSS wiring、production build、官方 registry、lockfile integrity 与 npm audit 全部通过。
- 未发现阻碍目标的 stub 或计划外新网络/auth/file/schema 威胁面。

---
*Phase: 01-engineering-auth-foundation*
*Completed: 2026-08-27*
