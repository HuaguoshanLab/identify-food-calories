---
phase: 06-user-dashboard-admin
plan: 13
subsystem: full-stack-admin
tags: [react, typescript, zod, react-hook-form, base-ui, vitest, msw, fastapi, pydantic]
requires:
  - phase: 06-12
    provides: DB-RBAC-protected catalog draft create and patch endpoints
  - phase: 06-25
    provides: admin frontend directory documentation baseline
provides:
  - Strict catalog draft API client and accessible create/edit workspace
  - DB-RBAC-protected catalog draft read and server-computed preview projections
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
  - "预览基线、字段差异和影响类别只能由服务端从当前数据库草稿计算。"
patterns-established:
  - "Admin feature: API 命令接受瞬时 access token，绝不存储或返回 token。"
  - "Admin mutation: 严格校验服务端投影、使用 Idempotency-Key，并按 401/403/409 进入安全状态。"
requirements-completed: [ADM-01, ADM-02, ADM-05, ARC-08]
duration: 125min
completed: 2026-09-03
---

# Phase 06 Plan 13: 营养目录草稿后台 UI Summary

**独立后台目录草稿工作台通过严格 Zod 合约、带理由的取消优先确认和授权安全状态提交公开 admin API。**

## Performance

- **Duration:** 125 min
- **Started:** 2026-09-02T22:44:00Z
- **Completed:** 2026-09-02T23:49:18Z
- **Original plan tasks:** 2/2
- **Authorized follow-up units:** 2/2
- **Files modified:** 16

## Accomplishments

- 新建按 feature 归属的严格 DTO/API 客户端，POST 使用 `Idempotency-Key`，PATCH 支持 `If-Match` revision。
- 交付有标签的目录字段表单、理由输入、取消优先的 Base UI `AlertDialog` 和重复提交防护。
- 锁定 MSW/Testing Library 契约：键盘可达、冲突保留编辑、401 清空会话、403 不展示缓存/目录数据，以及敏感字段不渲染。
- 新增只读 `POST /api/v1/admin/catalog-drafts/preview` 和 `GET /api/v1/admin/catalog-drafts/{id}`：每次都做当前 PostgreSQL RBAC，服务端返回允许列表字段 diff、影响类别和 revision 基线。
- 确认框仅渲染严格校验后的服务端 diff/impact；PATCH 409 后读取当前草稿并重新请求预览，保留本地编辑而不自动覆盖。

## Task Commits

1. **Task 1: 写 catalog form/diff/授权状态 RED 测试** - `6410783` (`test`)
2. **Task 2: 实现 catalog feature 和目录 README** - `7221f02` (`feat`)
3. **授权扩展：锁定服务端预览/读取合约** - `f2b533f` (`test`)
4. **授权扩展：实现 server preview/read 与冲突刷新** - `35c26fd` (`feat`)

## Files Created/Modified

- `admin-frontend/src/features/catalog/api/index.ts` - 严格草稿命令、响应投影与安全 HTTP 错误分类。
- `admin-frontend/src/features/catalog/CatalogDraftPage.tsx` - 目录草稿表单、确认与授权安全体验。
- `admin-frontend/src/components/ui/AlertDialog.tsx` - 官方 Base UI 的受控确认原语。
- `admin-frontend/src/features/catalog/CatalogDraftPage.test.tsx` - 可访问交互、安全状态与重复提交回归测试。
- `admin-frontend/src/features/catalog/api/README.md` - API DTO 与请求边界索引。
- `backend/app/admin/schemas.py` - 严格 preview 请求、字段 diff 和 impact 运行时 Schema。
- `backend/app/admin/service.py` - DB-RBAC 后的只读读取与服务端 diff/impact 计算。
- `backend/app/admin/api.py` - 公开、只读 preview/read HTTP 翻译与安全错误映射。

## Decisions Made

- HTTP 请求与 Zod DTO 位于 `features/catalog/api/`，满足后台架构的 feature 所有权与安全边界。
- 仅渲染严格校验的服务器确认投影；不渲染响应错误体、raw JSON、令牌或敏感原文。
- 401 调用 `AdminAuthProvider.clearSession`，由 Provider 清空 Query cache；403 进入无数据固定页。
- 预览请求不带 reason、idempotency 或客户端 revision；PATCH 只使用服务端 preview 的 `base_revision` 作为 `If-Match`。

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

## Authorized Follow-up

用户明确授权扩展后端 API，以消除原计划无法诚实提供“server diff/impact”的合约缺口。扩展遵守现有 `API → Service → Repository → Model` 方向，没有新增表、迁移、持久化敏感数据或前端令牌存储。

## Issues Encountered

- 当前 `App.tsx` 仍只注册占位根，`/admin/catalog` 尚未由后续认证/路由计划接入；即使浏览器可用，也不能以真实管理员会话走页面路径。
- 已启动本地 Vite 服务并尝试通过 Codex 内置浏览器打开 `http://127.0.0.1:5179/admin/catalog`。内置 `iab` 与 Chrome 控制面均返回 “Browser is not available”，因此无法进行真实公开 API 的浏览器操作；未伪造 token、直写数据库或绕过 API。

## Browser Verification

- **Attempted path:** `http://127.0.0.1:5179/admin/catalog`
- **Observed result:** 本地 Vite 服务成功启动；内置 `iab` 与 Chrome 控制面均不可用，未能加载页面。
- **Not verified:** 真实管理员登录、公开 preview/read/create/edit、409 刷新和 401/403 浏览器拒绝路径。
- **Reason:** 浏览器控制面不可用，且认证壳与 `/admin/catalog` 路由注册仍属于后续计划；没有使用直写数据库、伪造 token 或内部调用绕过该限制。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `06-14`/`06-15` 可复用 catalog API 所有权、受控确认和严格投影模式。
- `06-22` 必须将 `AdminCatalogDraftPage` 注册到受保护 `/admin/catalog` 路由并以真实管理员会话完成浏览器验收。
- 后续目录审核/发布功能可复用 `CatalogDraftPreviewResponse` 的严格服务端字段差异与影响范围模式。

## Self-Check: PASSED

- `CatalogDraftPage.tsx`、`catalog/api/index.ts`、`AlertDialog.tsx` 均存在。
- `6410783`、`7221f02`、`f2b533f` 和 `35c26fd` 均存在于 Git 历史。

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-03*
