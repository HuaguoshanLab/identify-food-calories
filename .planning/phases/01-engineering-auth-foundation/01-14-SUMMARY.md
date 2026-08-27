---
phase: 01-engineering-auth-foundation
plan: 14
subsystem: teaching-and-auth-quality-gates
tags: [documentation, architecture-contract, security-contract, playwright, mailpit, recovery]
dependency_graph:
  requires: [01-13-password-recovery]
  provides: [Chinese-auth-teaching, tracked-directory-contract, reproducible-full-stack-auth-e2e]
  affects: [frontend, backend, local-development, phase-1-verification]
tech_stack:
  added: [ruff-0.12.12, mypy-1.18.2]
  patterns: [Mailpit-code-retrieval, isolated-schema-reset, OpenAPI-disclosure-contract, README-index-contract]
key_files:
  created:
    - docs/learning/01-auth-and-backend-foundation.md
    - backend/tests/architecture/test_directory_contract.py
    - backend/tests/auth/test_phase1_security_contract.py
    - frontend/tests/e2e/auth-skeleton.spec.ts
  modified:
    - frontend/playwright.config.ts
    - frontend/src/auth/api.ts
    - frontend/src/auth/ForgotPasswordPage.tsx
    - frontend/src/auth/ResetPasswordPage.tsx
    - backend/pyproject.toml
decisions:
  - Playwright resets only food_agent_test and performs an explicit 0001-to-head Alembic migration before FastAPI starts.
  - Browser recovery uses existing public endpoints and HttpOnly context cookies; code and token values are neither hardcoded nor exposed to React state.
  - README completeness is enforced from git-tracked source directories so generated folders cannot create false failures.
metrics:
  duration: 14m 28s
  completed: 2026-08-27
  tasks_completed: 2
  files_created_or_modified: 22
---

# Phase 1 Plan 14: Teaching, Directory Contracts, and Full-Stack Auth Evidence Summary

提供可追踪的中文认证教学、自动化目录文档合同，并以真实 Mailpit 邮件和隔离 PostgreSQL 完整证明注册、恢复和会话安全链路。

## Completed Tasks

### Task 1: 中文教学文档与目录索引合同

- 新增中文学习指南，按真实代码路径解释 React→API→Service 事务→Repository→PostgreSQL、Argon2/HMAC 摘要差异、access/refresh、`/users/me`、RBAC/audit 和调试方法。
- 补齐根、前端、后端、`docs/`、`docs/learning/` 与架构测试目录的运行说明和三段式 README 索引。
- 目录合同基于 `git ls-files` 的源文件目录，排除缓存、构建输出与依赖目录，并检查 README 必有“职责 / 允许依赖 / 文件索引”以及父索引。

### Task 2: 最终安全、OpenAPI 与真实 E2E 门禁

- 增加 OpenAPI 脱敏、用户 H5 无 admin surface 与敏感认证代码无原始日志的合同测试。
- Playwright 从空的 `food_agent_test` schema 显式迁移 `0001` 到 `head`，FastAPI 只连接隔离测试库。
- 浏览器通过公开产品 API 和 Mailpit test API 完成注册、验证码激活、登录、安全 `returnTo`、refresh 后 `/users/me`、第二会话撤销、logout/back protection、密码恢复和新密码登录；测试没有硬编码验证码或令牌。
- 补齐原先仅为安全 shell 的密码恢复前端，凭 HttpOnly recovery context 调用既有 `/auth/password-recovery/*` API。

## Verification

| Gate | Result |
|---|---|
| `backend/.venv/bin/python -m pytest -q` | PASS — 98 passed (7 third-party TestClient deprecation warnings) |
| `backend/.venv/bin/ruff check .` | PASS |
| `backend/.venv/bin/mypy app` | PASS — 30 source files |
| `frontend npm run lint` | PASS |
| `frontend npm run typecheck` | PASS |
| `frontend npm run test` | PASS — 7 files, 27 tests |
| `frontend npm run build` | PASS |
| `frontend npm run test:e2e` | PASS — 2 Playwright tests, including real Mailpit auth flow |
| `backend/tests/architecture/test_directory_contract.py` | PASS — 2 tests |

## Decisions Made

- E2E 的应用进程使用 `DATABASE_URL=food_agent_test`；仅 Alembic 子进程临时保留独立开发 URL，以通过测试隔离 guard。这样避免了“迁移在测试库、应用却连接开发库”的假绿色差错。
- 密码恢复不在浏览器保存 context、验证码或 access token；React 只提交用户输入，服务端 HttpOnly Cookie 保持恢复上下文。
- Phase 6 才创建同级 `admin-frontend/`（ARC-08）；本阶段用户 H5 继续没有 `/admin` 路由或 admin API 客户端。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] E2E 迁移与应用数据库指向不同目标**
- **Found during:** Task 2 RED
- **Issue:** 旧 Playwright 生命周期只尝试 `upgrade head`，空测试库没有表；补迁移后 FastAPI 仍默认连接开发库。
- **Fix:** 清空且仅清空 `food_agent_test` schema，显式执行 `0001`→`head`，并让 E2E FastAPI 使用测试 URL。
- **Files modified:** `frontend/playwright.config.ts`
- **Verification:** 全量 Playwright 通过。

**2. [Rule 2 - Missing critical functionality] 恢复 API 没有可用浏览器界面**
- **Found during:** Task 2 RED
- **Issue:** 后端 recovery contract 已存在，但 Forgot/Reset 页面仍固定显示“服务暂时不可用”，无法完成计划要求的真实 recovery E2E。
- **Fix:** 通过公开 recovery API 实现请求、验证码验证和重置表单；上下文继续由 HttpOnly Cookie 持有。
- **Files modified:** `frontend/src/auth/api.ts`, `frontend/src/auth/ForgotPasswordPage.tsx`, `frontend/src/auth/ResetPasswordPage.tsx`
- **Verification:** Mailpit 真实恢复旅程通过。

**3. [Rule 2 - Missing critical functionality] 质量工具未成为可安装开发依赖**
- **Found during:** Task 2 final gate
- **Issue:** 计划要求 Ruff/Mypy，但 `pyproject.toml` 未声明它们，干净 venv 无法执行质量门禁。
- **Fix:** 固定 Ruff 0.12.12 与 Mypy 1.18.2 为 `dev` 依赖，并验证静态检查。
- **Files modified:** `backend/pyproject.toml`, `backend/app/auth/repository.py`
- **Verification:** Ruff 和 Mypy 全绿。

**4. [Rule 1 - Bug] 目录与健康 E2E 合同过期**
- **Found during:** Task 2 final gate
- **Issue:** `backend/tests/README.md` 漏掉新 architecture 目录；health E2E 断言了当前 UI 从未渲染的 heading/status。
- **Fix:** 更新父索引，health E2E 改为断言真实 landing heading，并保留直接 health API 验证。
- **Files modified:** `backend/tests/README.md`, `frontend/tests/e2e/health.spec.ts`
- **Verification:** 目录合同和全量 Playwright 通过。

**5. [Rule 1 - Bug] 新启用的 Ruff/Mypy 暴露现有静态错误**
- **Found during:** Task 2 final gate
- **Issue:** 测试存在未使用 import/lambda 规则问题，Repository 的 UPDATE 结果缺少 affected-row 类型断言。
- **Fix:** 移除未使用 import、改为命名 factory，并为原子 `rowcount` 权限证明使用 `CursorResult` 类型收窄。
- **Files modified:** `backend/tests/auth/test_refresh_api.py`, `backend/tests/integration/test_admin_audit.py`, `backend/app/auth/repository.py`
- **Verification:** Ruff 与 Mypy 通过。

**Total deviations:** 5 auto-fixed (2 Rule 1, 2 Rule 2, 1 Rule 3). **Impact:** 所有修复都使计划要求的可复现质量证据真正可运行，没有扩大产品架构。

## Known Stubs

None. 现有 admin-frontend 延后是明确路线图边界，不是阻断本计划目标的 stub。

## Threat Flags

None. 本计划只为现有认证/恢复 API 增加浏览器消费、测试与文档；没有新增网络端点、信任边界 schema 或文件访问面。

## Self-Check: PASSED

- 已确认四个关键产物存在。
- 已确认 `1a7b57f`、`bcf75f0` 和 `6ef2be5` 均在 Git 历史中。
- 文档中的仓库相对 Markdown 链接均指向已提交的代码或 README。
