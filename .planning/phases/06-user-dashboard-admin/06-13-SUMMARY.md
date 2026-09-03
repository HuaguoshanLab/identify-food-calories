---
phase: 06-user-dashboard-admin
plan: 13
subsystem: ui
tags: [react, typescript, zod, react-hook-form, base-ui, vitest, msw]
requires:
  - phase: 06-12
    provides: DB-RBAC-protected catalog draft create and patch endpoints
  - phase: 06-25
    provides: admin frontend directory documentation baseline
provides:
  - Strict catalog draft API client and accessible create/edit workspace
  - Controlled Base UI confirmation with in-memory-token request handling
  - Component contracts for conflict and unauthorized admin states
affects: [06-14, 06-15, 06-22, admin-catalog]
tech-stack:
  added: []
  patterns: [feature-owned api directory, strict Zod response parsing, cancel-first confirmation]
key-files:
  created:
    - admin-frontend/src/features/catalog/CatalogDraftPage.tsx
    - admin-frontend/src/features/catalog/api/index.ts
    - admin-frontend/src/components/ui/AlertDialog.tsx
  modified:
    - admin-frontend/src/features/catalog/CatalogDraftPage.test.tsx
    - admin-frontend/src/features/README.md
key-decisions:
  - "后台 HTTP 请求和 Zod DTO 固定归属 features/catalog/api，避免 feature 外的通用 API 垃圾桶。"
  - "401 通过 AdminAuthProvider 的 clearSession 清空内存会话和 Query cache；403 只渲染固定无权页。"
  - "确认对话框焦点初始落在取消按钮，确认请求期间禁用重复提交。"
patterns-established:
  - "Admin feature: API 命令接受瞬时 access token，绝不存储或返回 token。"
  - "Admin mutation: 严格校验服务端投影、使用 Idempotency-Key，并按 401/403/409 进入安全状态。"
requirements-completed: [ADM-01, ADM-02, ADM-05, ARC-08]
duration: 65min
completed: 2026-09-03
---

# Phase 06 Plan 13: 营养目录草稿后台 UI Summary

**独立后台目录草稿工作台通过严格 Zod 合约、带理由的取消优先确认和授权安全状态提交公开 admin API。**

## Performance

- **Duration:** 65 min
- **Started:** 2026-09-02T22:44:00Z
- **Completed:** 2026-09-02T23:49:18Z
- **Tasks:** 2/2
- **Files modified:** 10

## Accomplishments

- 新建按 feature 归属的严格 DTO/API 客户端，POST 使用 `Idempotency-Key`，PATCH 支持 `If-Match` revision。
- 交付有标签的目录字段表单、理由输入、取消优先的 Base UI `AlertDialog` 和重复提交防护。
- 锁定 MSW/Testing Library 契约：键盘可达、冲突保留编辑、401 清空会话、403 不展示缓存/目录数据，以及敏感字段不渲染。

## Task Commits

1. **Task 1: 写 catalog form/diff/授权状态 RED 测试** - `6410783` (`test`)
2. **Task 2: 实现 catalog feature 和目录 README** - `7221f02` (`feat`)

## Files Created/Modified

- `admin-frontend/src/features/catalog/api/index.ts` - 严格草稿命令、响应投影与安全 HTTP 错误分类。
- `admin-frontend/src/features/catalog/CatalogDraftPage.tsx` - 目录草稿表单、确认与授权安全体验。
- `admin-frontend/src/components/ui/AlertDialog.tsx` - 官方 Base UI 的受控确认原语。
- `admin-frontend/src/features/catalog/CatalogDraftPage.test.tsx` - 可访问交互、安全状态与重复提交回归测试。
- `admin-frontend/src/features/catalog/api/README.md` - API DTO 与请求边界索引。

## Decisions Made

- HTTP 请求与 Zod DTO 位于 `features/catalog/api/`，满足后台架构的 feature 所有权与安全边界。
- 仅渲染严格校验的服务器确认投影；不渲染响应错误体、raw JSON、令牌或敏感原文。
- 401 调用 `AdminAuthProvider.clearSession`，由 Provider 清空 Query cache；403 进入无数据固定页。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] 将目录 API 归入 feature 专属 api 目录**
- **Found during:** Task 2
- **Issue:** 计划列出 `features/catalog/api.ts`，但后台 `AGENTS.md` 强制所有 HTTP 请求和 Zod DTO 位于 `features/<feature>/api/`。
- **Fix:** 建立 `features/catalog/api/index.ts` 和本级 README，并同步 feature 父索引。
- **Files modified:** `admin-frontend/src/features/catalog/api/*`、相关 README。
- **Verification:** 组件测试、TypeScript typecheck 和 production build 通过。
- **Committed in:** `7221f02`

**2. [Rule 1 - Bug] 修复表单字段 id 与小数输入有效性**
- **Found during:** Task 2
- **Issue:** 初始字段 id 重复，且 HTML 数字输入默认整数步进会阻止小数营养值的表单提交。
- **Fix:** 使用字段注册名生成稳定 id，并为营养输入声明 `step="any"`。
- **Files modified:** `admin-frontend/src/features/catalog/CatalogDraftPage.tsx`。
- **Verification:** Testing Library 通过 label 查询、键盘导航和包含小数营养值的提交路径。
- **Committed in:** `7221f02`

---

**Total deviations:** 2 auto-fixed（Rule 1: 1，Rule 2: 1）。
**Impact on plan:** 两项均为目录约束和可访问表单正确性所必需，无功能范围扩张。

## Issues Encountered

- `06-12` 的 POST/PATCH 响应只含当前草稿投影，不提供服务器计算的 field diff、impact 或冲突后的最新草稿；也没有草稿读取/预览端点。因此本计划只能在命令前展示待提交的可读字段、成功后展示严格校验的服务器确认投影，并在 409 时保留编辑内容而不自动覆盖。后续后端合约必须补齐预览/读取能力，才能诚实交付 UI-SPEC 所述的“服务器最新差异”。
- 已尝试真实浏览器访问 `http://127.0.0.1:5179/admin/catalog`。本地独立 SPA 可启动，但当前 `App.tsx` 仅注册占位根，页面显示“管理后台”，目录工作台尚未由后续认证/路由计划注册；在不修改计划外路由或伪造管理员 token 的前提下，无法走真实公开 API 的表单路径。

## Browser Verification

- **Attempted path:** `http://127.0.0.1:5179/admin/catalog`
- **Observed result:** 独立 Vite SPA 成功加载，但只显示当前路由占位页“管理后台”。
- **Not verified:** 真实管理员登录、公开 `/api/v1/admin/catalog-drafts` 创建/编辑、401/403 浏览器拒绝路径。
- **Reason:** 认证壳与 `/admin/catalog` 路由注册属于后续计划；没有使用直写数据库、伪造 token 或内部调用绕过该限制。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `06-14`/`06-15` 可复用 catalog API 所有权、受控确认和严格投影模式。
- `06-22` 必须将 `AdminCatalogDraftPage` 注册到受保护 `/admin/catalog` 路由并以真实管理员会话完成浏览器验收。
- 后续后端计划需提供非敏感的 server-computed diff/impact 与 conflict refresh 合约；否则不得把本地待提交字段称为服务器差异。

## Self-Check: PASSED

- `CatalogDraftPage.tsx`、`catalog/api/index.ts`、`AlertDialog.tsx` 均存在。
- `6410783` 和 `7221f02` 均存在于 Git 历史。

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-03*
