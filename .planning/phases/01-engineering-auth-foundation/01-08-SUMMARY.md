---
phase: 01-engineering-auth-foundation
plan: 08
subsystem: frontend-ui
tags: [react, vite, tailwindcss, shadcn, base-ui, vitest, testing-library, accessibility]

requires:
  - phase: 01-engineering-auth-foundation/01-07
    provides: Vite/Tailwind v4 toolchain, official Base UI registry configuration, shared cn utility, and UI-SPEC tokens
provides:
  - All nine UI-SPEC-required official shadcn Base UI primitives
  - Tested AlertDialog keyboard/focus behavior and status component rendering evidence
  - Scoped lint rule that preserves documented shadcn variant helper exports
affects: [01-09, 01-10, 01-12, frontend-ui, authentication-ui]

tech-stack:
  added: [class-variance-authority 0.7.1]
  patterns: [official shadcn base-nova generation, Base UI dialog behavior tests, scoped generated-primitive lint exception]

key-files:
  created: [frontend/src/components/ui/button.tsx, frontend/src/components/ui/input.tsx, frontend/src/components/ui/label.tsx, frontend/src/components/ui/card.tsx, frontend/src/components/ui/separator.tsx, frontend/src/components/ui/alert.tsx, frontend/src/components/ui/alert-dialog.tsx, frontend/src/components/ui/badge.tsx, frontend/src/components/ui/skeleton.tsx, frontend/src/components/ui/components.test.tsx]
  modified: [frontend/package.json, frontend/package-lock.json, frontend/eslint.config.js, frontend/src/README.md, frontend/src/components/README.md, frontend/src/components/ui/README.md]

key-decisions:
  - "直接使用已核验的 shadcn base-nova 官方源码；Card 和全部状态原语继续通过 components/ui/utils.ts 的 cn 对齐现有 tokens。"
  - "class-variance-authority 作为 Button/Badge 的直接生产依赖锁定为 0.7.1，禁止依赖 shadcn CLI 的开发依赖树偶然解析。"
  - "Fast Refresh 例外只作用于 src/components/ui/*.tsx，因为官方组件需要公开导出 variants；业务组件仍保留完整规则。"

patterns-established:
  - "官方 UI 原语必须以 registry 查询、CLI info 和 production build 三重证据证明来源与可用性。"
  - "对话框测试覆盖可访问名称、focus guard、Escape 关闭及焦点返回，而非只检查静态 DOM。"

requirements-completed: [ARC-01, ARC-07]

duration: 8 min
completed: 2026-08-27
---

# Phase 1 Plan 8: 官方 Base UI 组件闭合 Summary

**九个 UI-SPEC 指定的官方 shadcn/Base UI 原语已生成：表单、布局、状态与可键盘操作的 AlertDialog 均通过真实 Vitest 行为测试和 production build。**

## Performance

- **Duration:** 8 min
- **Started:** 2026-08-27T08:41:00Z
- **Completed:** 2026-08-27T08:49:21Z
- **Tasks:** 2/2
- **Files modified:** 16

## Accomplishments

- 从唯一官方 `@shadcn` base-nova registry 生成 Button、Input、Label、Card、Separator、Alert、AlertDialog、Badge 与 Skeleton；`shadcn info` 明确列出全部九项已安装组件。
- Card、状态组件和对话框全部沿用 `components/ui/utils.ts` 的 `cn` 与 UI-SPEC Slate/Teal token 体系，没有引入第三方 registry 或整页 auth block。
- Testing Library 覆盖 `role=alert`、可见 focus ring class、AlertDialog 的 focus guards、Escape 关闭、焦点返回 trigger，以及 Skeleton 尺寸/动画 class；全量 Vitest 为 3 files / 5 tests 通过。

## Task Commits

1. **Task 1: 生成官方表单与布局组件** - `4d4142b` (feat)
2. **Task 2 RED: 生成并测试状态与对话框组件** - `11ac447` (test)
3. **Task 2 GREEN: 生成并测试状态与对话框组件** - `ac1109f` (feat)

## Files Created/Modified

- `frontend/src/components/ui/button.tsx`, `input.tsx`, `label.tsx`, `card.tsx`, `separator.tsx` - 官方 Base UI 表单与布局原语。
- `frontend/src/components/ui/alert.tsx`, `alert-dialog.tsx`, `badge.tsx`, `skeleton.tsx` - 官方状态、确认对话框和加载原语。
- `frontend/src/components/ui/components.test.tsx` - 原语真实渲染与对话框键盘/焦点行为测试。
- `frontend/package.json` / `frontend/package-lock.json` - Button/Badge 所需的直接生产依赖与可复现锁定。
- `frontend/eslint.config.js` - 仅针对官方 UI 原语 variants 导出的 Fast Refresh lint 覆盖。
- `frontend/src/README.md`, `frontend/src/components/README.md`, `frontend/src/components/ui/README.md` - 同步目录职责、允许依赖与文件索引。

## Decisions Made

- 不手写替代组件或引入 auth block；shadcn CLI 的 registry `view`、`add`、`info` 都指向官方 `ui.shadcn.com` Base UI 来源。
- 维持官方 Button/Badge variants 导出。移除它们只为让 lint 安静是垃圾做法，会破坏后续页面的官方组件 API；最小范围规则覆盖才是正确修复。
- Base UI 在 jsdom 中通过两个 focus guards 表达 tab trap；测试验证该结构与关闭恢复焦点的用户可见结果，避免伪造浏览器焦点循环。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical dependency] 补齐官方 Button/Badge 的生产依赖**
- **Found during:** Task 1（官方生成源码检查）
- **Issue:** shadcn CLI 生成的 Button/Badge 直接 import `class-variance-authority`，但没有把它写入项目的直接生产依赖；开发环境可能从 CLI 的依赖树偶然解析，production install 会损坏。
- **Fix:** 从 npm 官方 registry 核验并锁定 `class-variance-authority@0.7.1`，更新 package lock。
- **Files modified:** `frontend/package.json`, `frontend/package-lock.json`
- **Verification:** production build、`npm ls @base-ui/react class-variance-authority --depth=0`、`npm audit --omit=dev --audit-level=high` 全部通过。
- **Committed in:** `4d4142b`

**2. [Rule 3 - Blocking lint compatibility] 限定官方 variants 导出的 Fast Refresh 例外**
- **Found during:** Task 2（全量 ESLint）
- **Issue:** 官方 `button.tsx` 与 `badge.tsx` 同时导出组件和 documented variants，通用 `react-refresh/only-export-components` 规则错误阻断 lint。
- **Fix:** 仅对 `src/components/ui/*.tsx` 关闭此规则，并保留业务组件规则；没有改写或删除官方 API。
- **Files modified:** `frontend/eslint.config.js`
- **Verification:** `npm run lint`、`npm run typecheck`、全量 Vitest 与 production build 均通过。
- **Committed in:** `ac1109f`

---

**Total deviations:** 2 auto-fixed（1 Rule 2，1 Rule 3）。
**Impact on plan:** 修复只保证官方生成组件在干净 production 依赖图和现有 lint 门禁下可靠运行，没有扩展产品功能。

## Issues Encountered

- 初次无联网沙箱不能解析 `ui.shadcn.com`；在限定联网授权后对相同官方命令复验，registry `view`、`add`、`info` 全部成功。
- RED 测试先因计划创建的组件不存在而失败；GREEN 阶段以官方 Base UI 实际 class 和 focus guard 行为校正断言，未跳过任何可访问性验证。

## Authentication Gates

None.

## Known Stubs

None. 原语均是可直接导入的官方实现；Skeleton 只提供布局占位，不伪造业务数据。

## Threat Flags

None. 本计划只新增本地 UI 原语，没有新增网络端点、认证路径、文件访问或 schema 信任边界。

## Verification Evidence

- `npm exec shadcn -- view ...` → 九个组件均从官方 `ui.shadcn.com/r/styles/base-nova` registry 核验并生成。
- `npm exec shadcn -- info` → Vite、Tailwind v4、`@shadcn` 官方 registry、Base UI 以及全部九项 installed components 通过。
- `npm run lint` → 通过。
- `npm run typecheck` → 通过。
- `npm run test` → Vitest 3 files / 5 tests passed，无 skip。
- `npm run build` → Vite 8.2.2 production build 通过，69 modules transformed。
- `npm audit --omit=dev --audit-level=high` → 0 vulnerabilities。
- `git diff --check` → 无 whitespace 错误。

## Next Phase Readiness

- 01-09、01-10 与 01-12 可直接使用九个受验证的 Base UI 原语实现认证与会话页面。
- 后续页面必须保留 Label、文字按钮、AlertDialog 及全局 focus/reduced-motion 契约；不得改用第三方 registry 或未审查 block。
- 无阻塞项。

## Self-Check: PASSED

- 十个计划指定的 UI 源文件和测试文件均存在。
- `4d4142b`、`11ac447`、`ac1109f` 均可从 Git 历史解析，且没有意外文件删除。
- lint、typecheck、全量 Vitest、production build、官方 registry/source 配置、npm audit 与 diff 检查全部通过。

---
*Phase: 01-engineering-auth-foundation*
*Completed: 2026-08-27*
