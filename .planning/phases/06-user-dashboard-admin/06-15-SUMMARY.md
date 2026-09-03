---
phase: 06-user-dashboard-admin
plan: 15
subsystem: full-stack-admin
tags: [react, typescript, zod, vitest, msw, fastapi, pydantic, sqlalchemy, postgresql, rbac]
requires:
  - phase: 06-13
    provides: strict catalog draft API ownership and cancel-first confirmation primitive
  - phase: 06-14
    provides: immutable catalog publication, active pointer, eligibility history, and lifecycle commands
provides:
  - server-derived lifecycle projection with an allowlisted comparison baseline and impact count
  - accessible review/publish/disqualify confirmation flow with conflict preservation
  - read-only audit timeline that filters event diffs to safe catalog fields
affects: [06-22, admin-catalog, admin-audit, nutrition]
tech-stack:
  added: []
  patterns: [server-derived command projection, current-DB-RBAC readonly evidence, allowlisted audit rendering]
key-files:
  created:
    - admin-frontend/src/features/catalog/CatalogLifecyclePage.tsx
    - admin-frontend/src/features/audit/AuditTimeline.tsx
    - admin-frontend/src/features/audit/README.md
  modified:
    - admin-frontend/src/features/catalog/api/index.ts
    - backend/app/admin/schemas.py
    - backend/app/admin/service.py
    - backend/app/admin/api.py
key-decisions:
  - "生命周期确认投影由服务端以 active immutable publication 对比当前草稿生成；浏览器不生成可信 before 值、impact 或 eligibility。"
  - "即使字段未变也返回九个白名单行并标为无变更，避免正常发布因空 diff 失去可审计预览。"
  - "审计时间线只渲染固定 catalog 字段，未允许的响应 key 会被丢弃且不会进入 DOM。"
patterns-established:
  - "High-risk catalog UI: read server lifecycle projection → require nonblank reason → cancel-first AlertDialog → idempotent command → refresh projection/audit on success or 409."
  - "Readonly admin projection: require current DB role before reading draft/publication/eligibility and expose no snapshots, command keys, tokens, or raw JSON."
requirements-completed: [ADM-02, ADM-05]
duration: 57min
completed: 2026-09-03
---

# Phase 06 Plan 15: 目录生命周期治理后台 Summary

**管理员可在严格服务端 lifecycle projection 上阅读两列字段差异、影响数和安全审计，并通过带理由、取消优先的确认执行审核、发布与失格。**

## Performance

- **Duration:** 57 min
- **Completed:** 2026-09-03
- **Original plan tasks:** 2/2
- **Authorized follow-up units:** 2/2
- **Files modified:** 17

## Accomplishments

- 实现两列 `FieldDiffPreview`、影响范围、审计时间线、可访问的高风险对话框和 `401`/`403` fail-closed 状态；`409` 会保留理由并刷新最新服务端 diff。
- 目录 API 客户端对 lifecycle projection、发布响应和审计页执行严格 Zod 校验；access token 仅由调用方暂存，未持久化或记录。
- 经用户明确授权，新增 `GET /api/v1/admin/catalog-drafts/{draft_id}/lifecycle-preview`：服务端当前 DB-RBAC 后读取草稿、active immutable publication 与最新 eligibility，仅输出九个允许字段的变更、影响数量和安全后果。
- 通过 Fake service、HTTPX 和真实 PostgreSQL 覆盖首次发布、已发布无字段变更、失格 eligibility、普通用户拒绝与敏感字段排除。

## Task Commits

1. **Task 1: lifecycle review/publish/disqualify RED 测试** — `582a2a7` (`test`)
2. **Task 2: 人类可读生命周期 UI** — `6659f7f` (`feat`)
3. **授权扩展：server lifecycle projection RED 测试** — `97db702` (`test`)
4. **授权扩展：严格 DB-RBAC lifecycle preview API** — `26bccdc` (`feat`)
5. **授权扩展：前端处理无字段变更的安全投影** — `a1888df` (`fix`)

## Files Created/Modified

- `admin-frontend/src/features/catalog/CatalogLifecyclePage.tsx` — lifecycle 投影、理由确认、幂等命令与冲突恢复。
- `admin-frontend/src/features/catalog/api/index.ts` — 严格 lifecycle/audit DTO、命令和错误分类。
- `admin-frontend/src/features/audit/AuditTimeline.tsx` — 仅白名单字段的只读语义时间线。
- `backend/app/admin/{schemas,ports,repository,service,api}.py` — DB-RBAC 只读 projection、最新 eligibility 查询和 HTTP 映射。
- `backend/tests/admin/`、`backend/tests/unit/`、`backend/tests/integration/` — service、HTTP 和真实 PostgreSQL projection 证据。

## Decisions Made

- active publication 是“当前值”唯一基线，draft 的当前类型化 snapshot 是“拟发布值”；两者都由服务端读取并转换为可读标量。
- 每次 lifecycle projection 都先做当前 PostgreSQL role 检查，避免前端缓存的旧管理员会话读取目录或审计证据。
- 无变更仍展示九个字段并标为“无变更”，因为发布同一个冻结 revision 是合法流程，空 diff 会错误阻断确认界面。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] 补充服务端 lifecycle projection 合约**
- **Found during:** Task 2
- **Issue:** 06-14 仅有 lifecycle command；没有服务端 current-versus-proposed diff、impact 或 eligibility projection。前端自行拼造这些值会违反 UI-SPEC 和 T-06-28。
- **Fix:** 在用户明确授权后补充 schema → port → repository → service → API，并增加 service/API/PostgreSQL 测试。
- **Files modified:** `backend/app/admin/{schemas,ports,repository,service,api}.py`、backend lifecycle tests。
- **Verification:** 10 个隔离 PostgreSQL/service/API 测试、Ruff 与 mypy 全部通过。
- **Committed in:** `97db702`、`26bccdc`

**2. [Rule 2 - Missing Critical] 对正常发布保留无变更字段行**
- **Found during:** 授权扩展
- **Issue:** immutable publication 与当前 draft 相同是正常发布前状态；只返回 changed rows 会产生空 projection，既不能通过严格最小数组校验，也无法向管理员展示完整审核基线。
- **Fix:** 服务端返回九个白名单字段并以 `unchanged` 显式标注；前端严格解析并显示“无变更”。
- **Files modified:** `backend/app/admin/{schemas,service}.py`、`admin-frontend/src/features/catalog/{api,index.ts,CatalogLifecyclePage.tsx}`。
- **Verification:** Fake、HTTPX、PostgreSQL 及 Vitest 均覆盖并通过。
- **Committed in:** `26bccdc`、`a1888df`

---

**Total deviations:** 2 auto-fixed（Rule 2: 2）。
**Impact on plan:** 均为受权后的安全/正确性补足；未新增依赖、表、迁移或令牌持久化。

## Verification

- `cd admin-frontend && npm test -- --run` — 7 passed。
- `cd admin-frontend && npm run typecheck` — passed。
- `cd admin-frontend && VITE_ADMIN_API_BASE_URL=/api/v1/admin npm run build` — passed。
- `cd backend && uv run python tests/run_pg.py --env-file .env.test.example -- uv run pytest tests/admin/test_catalog_lifecycle_service.py tests/unit/test_admin_catalog_api.py tests/integration/test_catalog_publish_eligibility.py -q` — 10 passed。
- `cd backend && uv run ruff check app/admin tests/admin/test_catalog_lifecycle_service.py tests/unit/test_admin_catalog_api.py tests/integration/test_catalog_publish_eligibility.py` — passed。
- `cd backend && uv run mypy app/admin` — passed.

## Threat Flags

| Flag | File | Description |
| --- | --- | --- |
| `threat_flag: readonly-admin-api` | `backend/app/admin/api.py` | 新增只读 lifecycle projection；通过当前 DB-RBAC、严格 Pydantic whitelist、无 snapshot/command key 响应缓解。 |

## Browser Verification

- **Attempted path:** `http://127.0.0.1:5179/admin/catalog`。
- **Observed result:** 首次真实打开显示现有 `App.tsx` 的“管理后台”占位根，未注册 lifecycle 页面；随后重新验收时内置浏览器控制面不可用。
- **Not verified:** 真实管理员登录、公开 lifecycle preview/read、审核/发布/失格命令和 401/403/409 浏览器路径。
- **Reason:** 受保护后台路由/登录壳由后续 06-22 接入；没有伪造 token、直写数据库或绕过公开 API。

## Known Stubs

None. `CatalogLifecyclePage` 未被当前占位 `App.tsx` 注册是已规划的 06-22 路由装配工作，不是页面内假数据或替代服务端 projection。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 06-22 可将 `CatalogLifecyclePage` 接入受保护 `/admin/catalog` 路由，并以真实管理员会话完成浏览器验收。
- 后续 audit 页面可复用只读 `AuditTimeline`，但必须继续在自己的 feature API 层严格校验数据。

## Self-Check: PASSED

- `CatalogLifecyclePage.tsx`、`AuditTimeline.tsx`、`CatalogLifecyclePreviewResponse` 和 lifecycle API 路由均存在。
- `582a2a7`、`6659f7f`、`97db702`、`26bccdc`、`a1888df` 均存在于 Git 历史。

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-03*
