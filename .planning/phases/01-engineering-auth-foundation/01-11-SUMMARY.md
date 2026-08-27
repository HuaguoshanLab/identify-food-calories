---
phase: 01-engineering-auth-foundation
plan: 11
subsystem: auth-ui
tags: [react, tanstack-query, base-ui, authentication, session-management]

requires:
  - phase: 01-engineering-auth-foundation/01-05
    provides: 数据库权威的 Bearer /users/me 合约
  - phase: 01-engineering-auth-foundation/01-10
    provides: HttpOnly refresh 轮换、logout 与会话列表/撤销 API
provides:
  - refresh 后以 /users/me 建立的内存认证身份
  - 安全的 /app 深链守卫和已登记 returnTo 白名单
  - 用户会话列表、当前设备退出和确认式远端撤销 UI
affects: [phase-2, user-h5, auth, session-management]

tech-stack:
  added: []
  patterns: [runtime-only-access-token, refresh-then-me, single-flight-401-replay, allowlisted-returnTo, pessimistic-session-revoke]

key-files:
  created:
    - frontend/src/auth/AuthContext.ts
    - frontend/src/auth/AuthProvider.tsx
    - frontend/src/auth/RouteGuards.tsx
    - frontend/src/auth/returnTo.ts
    - frontend/src/auth/SessionList.tsx
    - frontend/src/auth/RevokeSessionDialog.tsx
  modified:
    - frontend/src/auth/api.ts
    - frontend/src/auth/LoginPage.tsx
    - frontend/src/App.tsx
    - frontend/src/main.tsx
    - frontend/src/auth/AuthSession.test.tsx
    - frontend/src/auth/ProtectedRoutes.test.tsx

key-decisions:
  - "浏览器只把 access token 保存在 AuthProvider 运行时内存；refresh 成功后必须再请求 /users/me，绝不从 JWT claims 推断最终 email、active 或 role。"
  - "returnTo 仅接受以 /app 开头的同源相对已登记受保护路径；认证页、未知路径、片段和绝对/协议相对 URL 一律回退 /app。"
  - "当前会话只能退出，远端会话必须经过 Base UI AlertDialog 的明确确认后才撤销。"

patterns-established:
  - "刷新风暴防护：并发 401 共享一个 refresh flight，每个原请求仅 replay 一次。"
  - "会话变更：TanStack Query 负责列表缓存；远端撤销悲观提交、成功后失效查询并播报结果。"

requirements-completed: [AUTH-01, AUTH-03, AUTH-04, ARC-01, ARC-07]
duration: 10min
completed: 2026-08-27
---

# Phase 01 Plan 11: 认证启动、受保护深链与会话 UI Summary

**用户 H5 现在以 refresh→数据库权威 `/users/me` 建立内存身份，安全恢复 `/app` 深链，并管理当前及远端登录会话。**

## Performance

- **Duration:** 10 min
- **Started:** 2026-08-27T17:45:43+08:00
- **Completed:** 2026-08-27T09:55:28Z
- **Tasks:** 2/2
- **Files modified:** 19

## Accomplishments

- AuthProvider 对 refresh、`/users/me` 和并发 401 采用单飞刷新协议；email、role 与 active 不再从 JWT payload 推断，access token 不会写入浏览器存储。
- `/app` 在 bootstrap 完成前显示 skeleton；未登录用户带安全深链进入登录，恶意或未知 returnTo 无法变成开放跳转或 admin 入口。
- 账号页显示服务器身份与精简会话元数据；当前设备执行 logout，其他设备经可键盘操作、可取消的确认对话框撤销。

## Task Commits

1. **Task 1: 实现 AuthProvider、users/me 与安全 returnTo (RED)** — `5504e44` (test)
2. **Task 1: 实现 AuthProvider、users/me 与安全 returnTo (GREEN)** — `666fa35` (feat)
3. **Task 2: 实现精确会话列表与撤销对话框 (RED)** — `83e3d3a` (test)
4. **Task 2: 实现精确会话列表与撤销对话框 (GREEN)** — `ddeb5c5` (feat)
5. **补充深链回跳验收测试** — `3f9e3da` (test)

## Files Created/Modified

- `frontend/src/auth/AuthProvider.tsx` — 内存会话、refresh 单飞、`/users/me` 权威身份和一次 401 重放。
- `frontend/src/auth/returnTo.ts` — `/app` 白名单 returnTo 解析器。
- `frontend/src/auth/RouteGuards.tsx` — bootstrap/网络错误状态、`/app` 守卫和账号摘要。
- `frontend/src/auth/SessionList.tsx` — TanStack Query 会话列表、错误重试、当前设备退出和远端撤销调度。
- `frontend/src/auth/RevokeSessionDialog.tsx` — 官方 Base UI AlertDialog 的撤销确认与错误反馈。
- `frontend/src/auth/AuthSession.test.tsx`、`frontend/src/auth/ProtectedRoutes.test.tsx` — bootstrap、DB 身份、攻击性 returnTo、无 admin 路由、深链回跳及 dialog 可访问性证据。

## Decisions Made

- `/users/me` 网络失败进入可重试的身份错误状态；refresh 或权威身份认证失败才进入登录，不把网络故障伪装成用户登出。
- logout 网络失败仍立即清理本地内存状态，并在登录页展示服务器未确认撤销的诚实警告。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Regression] 为既有 App 与登录表单测试补齐 AuthProvider 边界**
- **Found during:** Task 2（完整 Vitest 门禁）
- **Issue:** 既有测试直接渲染 App/LoginPage；新增认证 context 后会在无 Provider 时抛错。
- **Fix:** 测试渲染器按真实运行时组合 QueryClient 与 AuthProvider，并为受保护路由模拟标准 401 refresh 失败。
- **Files modified:** `frontend/src/App.test.tsx`, `frontend/src/auth/AuthForms.test.tsx`, `frontend/src/auth/PublicRoutes.test.tsx`
- **Verification:** `npm test` 27/27 通过。
- **Committed in:** `ddeb5c5`

---

**Total deviations:** 1 auto-fixed（Rule 1: 1）
**Impact on plan:** 修复仅保持新增认证运行时边界下的既有测试有效，不扩展产品范围。

## Issues Encountered

- 本机没有可执行的 `gsd-sdk` 命令；计划追踪会使用仓库可见的 `.planning` 文件顺序更新，并在元数据提交中记录。

## Known Stubs

None. 会话元数据缺失时明确显示“未知设备”，不伪造数据。

## Verification

- `cd frontend && npm run test -- AuthSession.test.tsx ProtectedRoutes.test.tsx` — PASS（2 files, 12 tests）
- `cd frontend && npm run lint` — PASS
- `cd frontend && npm run typecheck` — PASS
- `cd frontend && npm test` — PASS（7 files, 27 tests）
- `cd frontend && npm run build` — PASS

## Self-Check: PASSED

- AuthProvider、returnTo、RouteGuards、SessionList、RevokeSessionDialog 和两组认证测试文件均存在。
- `5504e44`, `666fa35`, `83e3d3a`, `ddeb5c5`, `3f9e3da` 均可在 Git 历史中解析。
