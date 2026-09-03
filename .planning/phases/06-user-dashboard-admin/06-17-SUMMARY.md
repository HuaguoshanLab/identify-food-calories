---
phase: 06-user-dashboard-admin
plan: 17
subsystem: admin-frontend
tags: [react, typescript, zod, tanstack-query, rbac, vitest, fastapi]
requires:
  - phase: 06-13
    provides: 独立后台内存 token 与 feature-owned HTTP/Zod 边界
  - phase: 06-16
    provides: append-only 的非密钥运行配置版本与 DB-RBAC 命令
  - phase: 06-25
    provides: 管理后台目录 README 合同
provides:
  - memory-token admin probe route guard
  - strict non-secret runtime-config review and future-policy command UI
  - DB-RBAC-protected runtime config read plus optimistic If-Match command contract
affects: [06-22, admin-auth, admin-model-configs]
tech-stack:
  added: []
  patterns: [probe-before-nested-route, feature-owned-zod-api, future-policy-optimistic-version]
key-files:
  created:
    - admin-frontend/src/auth/AdminRouteGuard.tsx
    - admin-frontend/src/features/config/ConfigSummaryPage.tsx
    - admin-frontend/src/features/config/api/index.ts
  modified:
    - admin-frontend/src/App.tsx
    - backend/app/admin/api.py
    - backend/app/admin/service.py
decisions:
  - "后台 guard 仅延迟页面渲染；每个 admin API 仍以 PostgreSQL 当前角色作为唯一授权真相。"
  - "运行配置读取和写入仅含非密钥 allowlist；If-Match 在 advisory lock 下比较当前 append-only version。"
metrics:
  duration: 42min
  completed: 2026-09-03
---

# Phase 06 Plan 17: 后台 probe guard 与运行配置界面 Summary

**独立后台在内存 token 的 probe 成功后才渲染受保护路由，并通过严格白名单 DTO 审阅和变更未来非密钥运行策略。**

## Accomplishments

- `AdminRouteGuard` 用内存 access token 调用 `/api/v1/admin/probe`；401/403 均清空 `AdminAuthProvider` 会话与 Query cache，403 保留固定无权体验，guard 从不承担授权真相。
- 新增 `features/config/api/`：严格 Zod DTO 只接受 provider、固定 alias、启停、价格、上限和时间；没有 token、密钥、endpoint 或 Provider body 字段。
- `/admin/model-configs` 在 guard 后登记配置页；页面提供 skip link、焦点目标、reduced-motion 兼容样式复用、理由确认、取消优先 Dialog、重复提交禁用和 409 编辑保留。
- 经用户授权补齐 `GET /api/v1/admin/runtime-config` 和 POST `If-Match`：Service 每次重读 DB-RBAC，在 advisory lock 内验证版本，拒绝并发旧基线；原有 append-only/audit 策略不变。

## Task Commits

1. **Task 1: 写 guard/config RED 测试** - `41803b3` (`test`)
2. **Task 2: 实现 probe guard/config feature 与目录索引** - `0fdc5d6` (`feat`)

## Verification

- `cd admin-frontend && npm test` → **3 files, 10 tests passed**。
- `cd admin-frontend && npm run typecheck` → **passed**。
- `cd admin-frontend && VITE_ADMIN_API_BASE_URL=/api/v1/admin npm run build` → **passed**。无变量的构建失败是既有生产 API-base 安全门禁。
- `cd backend && UV_CACHE_DIR=/private/tmp/food-agent-uv uv run pytest tests/admin/test_runtime_config_service.py tests/unit/test_admin_rbac_api.py -q` → **7 passed**。
- `cd backend && UV_CACHE_DIR=/private/tmp/food-agent-uv uv run ruff check app/admin/service.py app/admin/api.py tests/admin/test_runtime_config_service.py tests/unit/test_admin_rbac_api.py` → **All checks passed**。

## Decisions Made

- Guard 的 probe 只优化路由体验；读取和 mutation 都继续依赖后端每请求的 PostgreSQL RBAC。
- 浏览器以 `If-Match: 当前 version` 和 UUID Idempotency-Key 变更未来策略；409 不覆盖本地编辑。
- `features/config/api/` 是唯一 HTTP/Zod 所有者，符合后台 feature 边界；access token 只作为瞬时请求参数传入。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Directory contract] 将配置 HTTP 边界置于 feature 专属 api 目录**
- **Found during:** Task 2
- **Issue:** 计划文件名列出 `config/api.ts`，但 `admin-frontend/AGENTS.md` 要求 HTTP 与 DTO 位于 `features/<feature>/api/`。
- **Fix:** 创建 `config/api/index.ts` 和本级 README，并更新 config 与 features 父索引。
- **Verification:** Vitest、typecheck、production build 通过。
- **Commit:** `0fdc5d6`

**2. [Rule 1 - Bug] 阻断严格表单被响应元数据污染**
- **Found during:** Task 2
- **Issue:** 将完整服务端响应 reset 进 strict React Hook Form 会把 `id/version/created_at` 作为未知字段带入命令，导致确认永远无法提交。
- **Fix:** 仅映射允许写入的字段到表单默认值。
- **Verification:** MSW 断言 POST payload 精确为白名单命令，重复提交测试通过。
- **Commit:** `0fdc5d6`

**Total deviations:** 2 auto-fixed（Rule 1: 1，Rule 2: 1）。

## User-authorized API Extension

用户明确选择“扩展后端 API”并重复确认允许。因此增加受现有 DB-RBAC 保护的 config 读取，以及 POST 的 `If-Match` 并发基线。没有新增表、迁移、secret 存储、endpoint 配置或前端 token 持久化。

## Browser Verification

- **Attempted path:** `http://127.0.0.1:5179/admin/model-configs`。
- **Observed result:** 本地端口 5179 已被占用；启动受限进程时也确认该端口已有服务。随后 Codex 内置浏览器在 subagent 环境返回 `IAB visibility is not supported in a subagent thread`，无法加载并交互页面。
- **Not verified:** 真实管理员登录、refresh/bootstrap、公开 probe、GET/POST runtime-config 的端到端路径。
- **Integrity:** 未伪造 token、直写数据库、调用内部函数或把 MSW 测试当成浏览器验收。

## Known Stubs

无。`/admin/login` 的真实登录页和 session menu 仍明确由后续 Plan 22 在同一 guard 之上接线；本计划没有用假登录或假 token 绕过 probe。

## Next Phase Readiness

- Plan 22 可在 `AdminRouteGuard` 外建立登录/refresh bootstrap，再安全进入 `/admin/model-configs`。
- 后续后台壳可复用 guard 与 config feature 的 401/403/409 契约，但不得把其状态当作后端授权替代品。

## Self-Check: PASSED

- 已确认 `AdminRouteGuard.tsx`、`ConfigSummaryPage.tsx`、`config/api/index.ts` 与目录 README 存在。
- 已确认 `41803b3`、`0fdc5d6` 存在于 Git 历史；任务提交未删除受跟踪文件。
