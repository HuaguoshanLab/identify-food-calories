---
phase: 06-user-dashboard-admin
plan: 24
subsystem: admin-frontend
tags: [react, vite, tanstack-query, vitest, msw, admin-auth]
requires:
  - phase: 06-user-dashboard-admin
    provides: 独立后台锁定供应链、Vite 配置和 production admin API fail-closed 边界
provides:
  - BrowserRouter、QueryClientProvider、AdminAuthProvider 的独立后台入口
  - 仅内存 access token 与身份变化/退出 Query cache 清理合同
  - 后台语义样式和 Vitest、Testing Library、MSW 共享运行时
affects: [06-25, admin-auth, admin-routes, admin-features]
tech-stack:
  added: []
  patterns: [memory-only admin authentication, provider composition, strict MSW test lifecycle]
key-files:
  created:
    - admin-frontend/src/main.tsx
    - admin-frontend/src/App.tsx
    - admin-frontend/src/auth/AdminAuthProvider.tsx
    - admin-frontend/src/styles/index.css
    - admin-frontend/src/test/setup.ts
  modified:
    - admin-frontend/index.html
    - admin-frontend/vite.config.ts
    - admin-frontend/README.md
key-decisions:
  - "AdminAuthProvider 仅保存 access token 和最小管理员身份于 React 内存；身份变化及退出均清空 TanStack Query cache。"
  - "入口文档显式加载 src/main.tsx，Provider 顺序固定为 BrowserRouter、QueryClientProvider、AdminAuthProvider、App。"
patterns-established:
  - "后续后台认证 API 通过 AdminAuthProvider 的公开接口更新会话，不能持久化 token 或将前端状态作为授权真相。"
  - "全局 Vitest setup 统一关闭 MSW、重置 handler、DOM 与 mock，feature 测试只注册自己的公开 API handler。"
requirements-completed: [ARC-08, ADM-01]
duration: 9min
completed: 2026-09-02
---

# Phase 06 Plan 24: 独立后台 SPA 运行时 Summary

**独立后台已具备固定 Provider 组合、只存于内存的管理员会话边界、Query cache 隔离，以及可编译的语义样式和测试运行时。**

## Performance

- **Duration:** 9 min
- **Completed:** 2026-09-02T10:24:03Z
- **Tasks:** 1/1
- **Files modified:** 13

## Accomplishments

- 创建 `BrowserRouter → QueryClientProvider → AdminAuthProvider → App` 的唯一后台启动树，且 `index.html` 真实加载 React 入口。
- `AdminAuthProvider` 仅在 React 内存持有 access token 和最小管理员身份；身份切换、清会话与退出都会清空 TanStack Query cache。
- 建立后台 slate 语义 token、可见键盘焦点、数字对齐与 `prefers-reduced-motion` 基线；建立 Testing Library DOM 清理、MSW handler reset/close 与 mock reset。
- 新建的 `src`、`src/auth`、`src/styles`、`src/test` 均在同次提交附带中文 README，并由直接父索引登记。

## Task Commits

1. **Task 1: 创建入口、memory-only Provider、样式和测试 setup** - `8bacb4d` (`feat`)

## Files Created/Modified

- `admin-frontend/src/main.tsx`、`App.tsx`、`vite-env.d.ts` - 独立 React 根、路由装配边界与构建时 API base 类型。
- `admin-frontend/src/auth/AdminAuthProvider.tsx` - 内存会话与 Query cache 清理合同。
- `admin-frontend/src/styles/index.css` - 语义 token、焦点、减弱动画和数值样式基线。
- `admin-frontend/src/test/setup.ts` - MSW、Testing Library、Vitest 的统一清理生命周期。
- `admin-frontend/src/**/README.md`、`admin-frontend/README.md` - 新目录职责、依赖边界与父索引。
- `admin-frontend/index.html` - 真实加载后台 React 入口。
- `admin-frontend/vite.config.ts` - 空测试阶段可运行的 Vitest 验证配置。

## Decisions Made

- access token 只属于 Provider 的内存状态；前端 guard 只是体验层，后端 PostgreSQL RBAC 仍是授权真相。
- App 只保留独立后台路由根，未提前注册用户 H5 路由、后台业务页面或模拟数据。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] 补齐 HTML 到 React 入口的模块加载**
- **Found during:** Task 1（真实浏览器验证）
- **Issue:** 初始 `index.html` 只有 root 容器、没有模块脚本；构建成功但浏览器只显示空白页，无法形成可执行 SPA runtime。
- **Fix:** 增加唯一的 `/src/main.tsx` module script。
- **Files modified:** `admin-frontend/index.html`
- **Verification:** 生产构建转换 70 个模块；内置浏览器在 `http://127.0.0.1:5179/` 显示可访问的“管理后台”一级标题。
- **Committed in:** `8bacb4d`

**2. [Rule 3 - Blocking] 允许尚未拥有 feature 测试的运行时通过 Vitest 门禁**
- **Found during:** Task 1（计划指定的 Vitest 验证）
- **Issue:** 本计划只创建共享 test setup，尚未创建 feature 测试；Vitest 会把“没有匹配测试文件”作为失败，从而阻断计划明确要求的测试运行时验证。
- **Fix:** 在已存在的 Vitest 配置启用 `passWithNoTests`，后续 feature 测试仍按正常匹配规则执行。
- **Files modified:** `admin-frontend/vite.config.ts`
- **Verification:** `npm test -- --run` 以退出码 0 完成；后续计划可直接在 `src/**/*.{test,spec}.{ts,tsx}` 添加测试。
- **Committed in:** `8bacb4d`

---

**Total deviations:** 2 auto-fixed（1 个 Rule 2，1 个 Rule 3）。
**Impact on plan:** 两项均为让计划交付的“可执行入口”和“可运行测试 runtime”真实成立的最小修复；未添加依赖、未扩大后台功能面。

## Issues Encountered

- 计划列出的用户端 `frontend/src/styles/index.css` 与 `frontend/src/test/setup.ts` 在当前仓库不存在；实现时改读现有 `frontend/src/styles.css` 与 `frontend/src/test-setup.ts`，并遵循其已验证的焦点与测试清理模式。
- 无显式 `VITE_ADMIN_API_BASE_URL` 的生产构建按 06-10 的 fail-closed 合同失败；使用合规值 `/api/v1/admin` 后构建成功。

## Browser Verification

- 在 Codex 内置浏览器访问 `http://127.0.0.1:5179/` 并刷新，确认页面标题为“饮食健康 Agent 管理后台”、`main` 的无障碍名称为“管理后台”，且一级标题可见。
- 此计划尚未包含登录或受保护业务页面，因而没有进行凭据、RBAC 或真实后台 API 路径验收；这些必须由后续功能计划通过公开 API 完成。

## User Setup Required

None - no external service configuration required. Production deployment must continue to supply the validated `VITE_ADMIN_API_BASE_URL` value.

## Next Phase Readiness

- 06-25 可在已索引的独立 `src` runtime 上补齐其余预建目录契约。
- 后续管理员认证和 feature API 只能使用 Provider 的公开会话边界与 `/api/v1/admin/*`，不得持久化 token 或导入用户 H5。

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-02*

## Self-Check: PASSED

- 已确认 `main.tsx`、`AdminAuthProvider.tsx` 和本 Summary 均存在。
- 已确认任务提交 `8bacb4d` 存在于 Git 历史，且任务提交未删除受跟踪文件。
- 已扫描本计划创建的源码：未发现会流向 UI 的占位数据或新增网络、授权、文件访问与 schema 信任边界。
