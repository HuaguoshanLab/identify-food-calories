# Phase 6: 用户看板与后台管理 - Pattern Map

**Mapped:** 2026-09-02  
**Files classified:** 49 file paths / file families  
**Analogs found:** 46 / 49

## File Classification

| New / modified file or family | Role | Data flow | Closest analog | Match |
|---|---|---|---|---|
| `backend/app/dashboard/{__init__,README,models,schemas,ports,repository,service}.py` | model/service/repository/API DTO | CRUD, transform | `app/records/*` | exact domain-layer match |
| `backend/app/dashboard/weekly_review_{dto,graph}.py` | DTO / graph | bounded async request-response | `app/agent/{state,graph}.py` + `providers/reasoning/*` | role match |
| `backend/app/dashboard/weekly_review.py` | application service | request-response / event-driven ledger | `app/agent/service.py` | role match |
| `backend/app/records/{models,schemas,ports,repository,service,api}.py` | model/API/service/repository | CRUD, database aggregation | existing same files | exact extension |
| `backend/app/agent/{models,service,repository,schemas}.py` | ledger model/service/repository | event-driven | existing same files | exact extension |
| `backend/app/providers/reasoning/{ports,dto,deepseek,fake,factory}.py` | provider port/adapter/fake | async request-response | existing same files | exact extension |
| `backend/app/admin/{models,schemas,ports,repository,service,api}.py` | RBAC/API/service/repository | CRUD, request-response | existing same files | exact extension |
| `backend/app/nutrition/{models,ports,repository,service,schemas}.py` | catalog model/service | CRUD, deterministic transform | existing same files | exact extension |
| `backend/app/planning/{models,ports,repository,service,schemas}.py` | qualification/eligibility port | request-response, deterministic transform | existing same files | exact extension |
| `backend/app/main.py` | config / router composition | request-response | current router registration | exact |
| `backend/migrations/versions/0013_*.py` (or ordered successors) | migration | batch/schema evolution | `0010_planning_profiles.py`, `0011_controlled_recipes.py` | exact |
| `backend/tests/{dashboard,admin,unit,integration,evals}/test_*.py` | test | CRUD / async / event-driven | `tests/records/test_record_service.py`, `tests/unit/test_meal_record_api.py`, `tests/integration/test_agent_checkpoint.py` | role match |
| `frontend/src/features/records/api/{schemas,client}.ts` | API DTO/client | request-response | existing records API files | exact extension |
| `frontend/src/features/records/components/{RecordsPage,TodaySummaryCard,WeeklyTrend,HistorySection,WeeklyReview}.tsx` | component/page | request-response / transform | `RecordsPage.tsx`, `plans/components/{PlanPage,PlanningStatus}.tsx` | role match |
| `frontend/src/features/records/{format,*.test}.ts(x)` | utility/test | transform | `records/format.ts`, adjacent tests | exact |
| `frontend/src/App.tsx` | route composition | request-response UI | current `App.tsx` | exact (no admin route) |
| `admin-frontend/{README,AGENTS,package.json,vite.config.ts,components.json,index.html}` | independent Vite config/docs | request-response | `frontend/{README,AGENTS,package.json,vite.config.ts,components.json}` | exact project template |
| `admin-frontend/src/{main,App,styles}.tsx` | SPA composition | request-response | `frontend/src/{main,App}.tsx` | role match |
| `admin-frontend/src/auth/{AuthContext,AuthProvider,RouteGuards,api,returnTo}.ts(x)` | auth/provider/guard | request-response | `frontend/src/auth/*` | exact adaptation |
| `admin-frontend/src/features/{overview,catalog,runs,config,audit}/{api,components}/*` | feature API/component | request-response, cursor paging | `frontend/src/features/{records,plans}` | role match |
| `admin-frontend/src/components/ui/*`, `admin-frontend/src/layouts/*`, `admin-frontend/src/**/*.test.tsx`, `admin-frontend/tests/e2e/*` | primitives/layout/tests | UI request-response | `frontend/src/components/ui`, `layouts`, tests | role match |
| `README.md`, `backend/README.md`, `frontend/README.md`, `admin-frontend/README.md`, module `README.md`, `docs/learning/phase-06-*.md` | documentation | documentation | existing directory READMEs / teaching docs | exact convention |

### Explicitly absent analogue

`admin-frontend/` has no existing sibling SPA. Copy the *scaffolding and security boundaries* of `frontend/`, but do **not** import its feature components or H5 layouts. Its desktop shell, admin-table primitives, and admin route guard are new implementations governed by `06-UI-SPEC.md`.

## Pattern Assignments

### Dashboard aggregate read path

**Target:** `backend/app/dashboard/{models,schemas,ports,repository,service,api}.py`, plus the records extension that freezes `consumed_local_date` / IANA zone at write time.

**Primary analog:** `backend/app/records/{api,service,repository,models,ports}.py`.

**HTTP wiring** — [records/api.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/app/records/api.py:25) uses a domain service dependency and the shared `AuthenticatedPrincipal`; handlers only call the service, validate the response, and map domain exceptions. Dashboard endpoints must use the identical layering, but a new `/api/v1/dashboard` router registered from `app/main.py`.

```python
def get_meal_record_service(session: SessionDependency) -> Generator[MealRecordService, None, None]:
    yield MealRecordService(
        repository=SqlAlchemyMealRecordRepository(session), commit=session.commit, rollback=session.rollback
    )

@router.get("", operation_id="listMealRecords", response_model=list[MealRecordResponse])
def list_meal_records(principal: AuthenticatedPrincipal, service: ServiceDependency) -> list[MealRecordResponse]:
    return [MealRecordResponse.model_validate(record) for record in service.list_records(user_id=principal)]
```

**Ownership / soft-delete query** — [records/repository.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/app/records/repository.py:72) orders in SQL, and its shared statement applies `MealRecord.user_id == user_id` plus `deleted_at IS NULL` before materialising anything. The dashboard repository must aggregate and cursor-page from that predicate, not fetch records then group in Python or the H5.

```python
return list(self._session.scalars(
    self._record_statement(user_id=user_id).order_by(MealRecord.consumed_at.desc(), MealRecord.id.desc())
))

statement = select(MealRecord).options(selectinload(MealRecord.items)).where(MealRecord.user_id == user_id)
if not include_deleted:
    statement = statement.where(MealRecord.deleted_at.is_(None))
```

**Immutable nutrition input** — [records/models.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/app/records/models.py:15) and [records/service.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/app/records/service.py:73) model confirmed totals/items as a snapshot. Add local-time attribution to this source record and only aggregate persisted totals. Do not re-run the current catalog for historical meals.

**Target eligibility cross-module port:** use a narrow planning-owned read capability; do not let dashboard query `PlanningProfile` or planning tables directly. This follows the explicit `PlanningNutritionPort` form in [planning/ports.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/app/planning/ports.py:31). The port should return only “complete-profile-and-completed-plan eligibility + target ranges/version”, never health narratives.

**Runtime contracts:** copy `ConfigDict(extra="forbid", frozen=True)` public projection DTOs from [planning/schemas.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/app/planning/schemas.py:127). Decimal totals remain `Decimal` server-side; the frontend validates strings, not browser-computed values.

### Weekly review: facts first, then bounded provider call

**Target:** `backend/app/dashboard/weekly_review.py`, `weekly_review_dto.py`, `weekly_review_graph.py`; modify `agent` ledger and `providers/reasoning` only at their declared ports.

**Primary analogs:** [agent/service.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/app/agent/service.py:134), [agent/models.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/app/agent/models.py:44), [providers/reasoning/deepseek.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/app/providers/reasoning/deepseek.py:84), [providers/reasoning/fake.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/app/providers/reasoning/fake.py:41).

**Ledger and idempotency** — use `AgentService.create_or_reuse_run` as the shape: owner-filtered `for_update`, canonical command hash, same-key conflict, version fields, then one transaction. The new review run needs a kind/config/facts digest extension, never a prompt, output text, email, image, or complete state. Existing model constraints make the data-minimisation boundary explicit:

```python
class AgentRun(Base):
    # ... UniqueConstraint("thread_id", "command_key", name="uq_agent_runs_thread_command_key")
    graph_version: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    model_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(80))
```

**Provider adapter:** extend the existing narrow async `ReasoningModelProvider` port, typed DTO, DeepSeek adapter and scripted Fake together. The existing adapter uses JSON schema, `reasoning: {"effort": "none"}`, bounded output, usage-derived cost, and deliberately safe logging at [deepseek.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/app/providers/reasoning/deepseek.py:84) and [deepseek.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/app/providers/reasoning/deepseek.py:244). Keep its no-replay policy for unknown outcomes at lines 120–125.

```python
# Fake adapter pattern: consume request but do not retain sensitive request bodies.
async def parse_meal(self, request: ParseMealRequest) -> ParseMealResult:
    del request
    outcome = _next_parse_outcome(self._parse_outcomes)
    self._record_call("parse_meal", outcome)
    if isinstance(outcome, ProviderCallError):
        raise outcome
    return outcome
```

**Required phase-specific order:** deterministic `WeeklyAggregateFactsDTO` → validate timezone/coverage/facts size → return `INSUFFICIENT_COVERAGE` with **zero provider calls**, or create/reuse run → freeze enabled non-secret configuration → `await graph.ainvoke` with max two calls / eight seconds → schema and semantic validation → safe result or stable abstention. The graph may invoke Provider only; it cannot import an ORM repository. This is the same boundary declared in [backend/ARCHITECTURE.md](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/ARCHITECTURE.md:52).

### Admin RBAC, commands, audit and minimal read projections

**Target:** all `backend/app/admin/*`; integration extensions in nutrition, planning, agent and migrations.

**Primary analog:** [admin/api.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/app/admin/api.py:22) and [admin/service.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/app/admin/service.py:22).

**Authorization must be endpoint-local:** every `/api/v1/admin/*` handler validates bearer session then calls `AdminService.require_role`, which loads the active user from PostgreSQL. Never trust a frontend guard or JWT role claim.

```python
try:
    user_id, _session_id = authentication_service.authenticated_session(credentials.credentials)
except (InvalidAccessToken, AuthenticatedUserUnavailable):
    return _authentication_required()
try:
    admin_service.require_role(user_id=user_id, required_role=UserRole.ADMIN)
except AdminPermissionDenied:
    return _forbidden()
```

**Transaction + audit:** follow [admin/service.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/app/admin/service.py:89): normalize required reason, mutate command target, create append-only audit evidence, commit once, rollback both on failure. The repository stays flush-only ([admin/repository.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/app/admin/repository.py:14)). Draft/review/publish/disqualify/config mutation must also require `If-Match` revision and idempotency key; expected revision conflict is an HTTP 409, never a silent retry.

```python
normalized_reason = reason.strip()
if not normalized_reason:
    raise AdminRoleChangeDenied("a non-empty reason is required")
# mutation + add_audit(...) occur before the sole commit
try:
    self._commit()
except Exception:
    self._rollback()
    raise
```

**ORM constraints / indexes:** use [admin/models.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/app/admin/models.py:14) as the audit model pattern: nonblank DB reason checks, role/status checks, foreign key, chronological index. Add append-only generic audit fields as a separate model; do not bend `AdminRoleAudit` into unrelated catalog events.

**Catalog eligibility:** retain the existing SQL qualification style from [nutrition/repository.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/app/nutrition/repository.py:66): qualification is enforced by SQL predicates. Publication adds immutable version/pointer/overlay semantics; disqualification must alter the overlay used by *future* nutrition searches and recipe eligibility while leaving `MealRecord` snapshots untouched. Planning’s fail-closed ingredient-chain predicate at [planning/repository.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/app/planning/repository.py:74) is the exact downstream guard to extend.

**Run queries:** project only ledger identifiers, status, versions, failure code, counts, elapsed/cost, safe summary, and provider/tool names. `AgentEvent.payload` is not an admin DTO; [agent/models.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/app/agent/models.py:93) documents it as client-safe metadata but the phase contract further forbids raw State and detail leakage. Use keyset cursor filtering and identical terminal-run UTC window in both P50/P95 metric query and runs list.

### Frontend records dashboard

**Target:** `frontend/src/features/records/api/*`, new feature components/tests, `RecordsPage.tsx`; keep `App.tsx` and `BottomNavigation.tsx` unchanged except imports/route remain unnecessary.

**Primary analogs:** [records/api/client.ts](/Users/mina/Documents/ChatGPT/identify-food-calories/frontend/src/features/records/api/client.ts:1), [records/api/schemas.ts](/Users/mina/Documents/ChatGPT/identify-food-calories/frontend/src/features/records/api/schemas.ts:1), [records/components/RecordsPage.tsx](/Users/mina/Documents/ChatGPT/identify-food-calories/frontend/src/features/records/components/RecordsPage.tsx:14), [plans/api/profile.ts](/Users/mina/Documents/ChatGPT/identify-food-calories/frontend/src/features/plans/api/profile.ts:44), [plans/components/PlanningStatus.tsx](/Users/mina/Documents/ChatGPT/identify-food-calories/frontend/src/features/plans/components/PlanningStatus.tsx:17).

**API boundary:** inject `AuthenticatedRequest`, check `response.ok`, then Zod-parse a strict DTO. Define query-key factories containing timezone, week and cursor; mutation success invalidates only the matching records-dashboard prefix. Pages never fetch or aggregate records directly.

```ts
export async function getPlanningProfile(request: PlanningApiRequest): Promise<PlanningProfile | null> {
  const response = await request('/planning/profile')
  if (response.status === 404) return null
  if (!response.ok) throw await getPlanningApiError(response, '无法读取个人资料。')
  return planningProfileSchema.parse(await response.json())
}
```

**Page composition:** preserve the focusable H1 / empty-state / real `Link` pattern in `RecordsPage`; replace its raw `useEffect` list with independently recoverable TanStack Query projections. Render exactly: today summary → SVG-plus-semantic-table weekly trend → cursor-paged history → weekly review. Preserve the four navigation items at [BottomNavigation.tsx](/Users/mina/Documents/ChatGPT/identify-food-calories/frontend/src/layouts/BottomNavigation.tsx:12); this phase must not add a dashboard or admin Tab.

**Safe review states:** componentise the three mutually exclusive server outcomes. Reuse `PlanningStatus`’s safe-message/`aria-live` approach, but do not expose a Provider code, budgets, or technical error. `INSUFFICIENT_COVERAGE` and safety abstention expose no regenerate control; only a retryable service failure exposes “重新生成本周复盘”. SVG is visual enhancement only: fixed seven points, `role="img"`, keyboard reachable points, and an always-present data table.

### Independent admin SPA

**Target:** the complete new `admin-frontend/` tree.

**Scaffolding analog:** [frontend/main.tsx](/Users/mina/Documents/ChatGPT/identify-food-calories/frontend/src/main.tsx:17), [frontend/vite.config.ts](/Users/mina/Documents/ChatGPT/identify-food-calories/frontend/vite.config.ts:26), [frontend/package.json](/Users/mina/Documents/ChatGPT/identify-food-calories/frontend/package.json:9).

Copy the independent `BrowserRouter → QueryClientProvider → AuthProvider → App` composition and production API-base validation, then give it its own package name, lockfile, port/base configuration, `components.json`, docs, QueryClient, and feature tree. Do not link filesystem imports to `frontend/src`.

**Auth guard analog:** [frontend/auth/AuthProvider.tsx](/Users/mina/Documents/ChatGPT/identify-food-calories/frontend/src/auth/AuthProvider.tsx:38) keeps access only in memory and clears `queryClient` on logout/identity change; [RouteGuards.tsx](/Users/mina/Documents/ChatGPT/identify-food-calories/frontend/src/auth/RouteGuards.tsx:16) owns bootstrap/loading/error/redirect once. Admin adaptation is: bootstrap token → request admin `probe` → allow nested admin routes only after positive probe; on 401 clear cache/token and redirect to admin login; on 403 clear cached admin data and render the specified forbidden view. This guard is UX only; backend RBAC remains authoritative.

**Feature composition:** replicate records’ `api/schemas.ts` + `api/client.ts` split per admin feature. `runs` owns metric/list/detail and opaque cursor; `catalog` owns draft/editor/diff/commands; `config` owns non-secret config versions; `audit` owns readonly timeline. All server DTOs use strict Zod schemas. High-risk commands use the existing [MealRecordEditPage.tsx](/Users/mina/Documents/ChatGPT/identify-food-calories/frontend/src/features/records/components/MealRecordEditPage.tsx:11) controlled-dialog pattern, with reason validation, cancel-first focus, disabled duplicate submit, server diff preview, and 409 preservation—not client-computed diffs.

## Shared Patterns

### Dependency direction

Source: [backend/ARCHITECTURE.md](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/ARCHITECTURE.md:43) and [frontend/ARCHITECTURE.md](/Users/mina/Documents/ChatGPT/identify-food-calories/frontend/ARCHITECTURE.md:41).

```text
Backend API → Service → Port ← Repository → Model/PostgreSQL
Weekly graph → State + narrow tool/provider ports (never repository/ORM)
Frontend page → feature API client → AuthenticatedRequest → public /api/v1
```

### Validation and public-data minimisation

- Pydantic HTTP DTOs: `extra="forbid"`, frozen when appropriate; separately define ORM, Graph State, and Provider DTOs.
- Zod browser DTOs: use `.strict()` as in [records/api/schemas.ts](/Users/mina/Documents/ChatGPT/identify-food-calories/frontend/src/features/records/api/schemas.ts:3).
- Map missing/foreign user resources to the same 404 shape, per [records/api.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/app/records/api.py:91).
- No response, ledger, Fake trace, audit entry, dashboard review facts or admin detail may include email, source text, image/base64, secret, Provider body, complete Graph State, or reasoning chain.

### Tests, migrations, README and browser verification

- **Service fake:** imitate [tests/records/test_record_service.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/tests/records/test_record_service.py:40): a minimal in-memory port that verifies tenant filters, snapshots, commits and rollback behavior.
- **HTTPX/FastAPI contract:** imitate [tests/unit/test_meal_record_api.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/tests/unit/test_meal_record_api.py:56): override principal + service and assert OpenAPI/request/tenant/404 contracts.
- **Repository integration:** use real PostgreSQL only. Cover `AT TIME ZONE` day/week membership, backfill, soft deletes, cursor ordering, P50/P95, terminal-run window, locks, `If-Match`, eligibility overlay and snapshot stability.
- **Graph/Provider/eval:** extend the scripted `FakeReasoningModelProvider`; frozen 14-case weekly-review fixtures prove zero low-coverage calls, ≤2 calls, timeout/budget/disabled/outcome-unknown abstention, schema + semantic rejection, and safe ledger fields.
- **Migration:** use revision metadata and explicit `upgrade`/`downgrade` table/index operations as in [0010_planning_profiles.py](/Users/mina/Documents/ChatGPT/identify-food-calories/backend/migrations/versions/0010_planning_profiles.py:14). Do not seed versioned catalog data in migrations.
- **Documentation:** every newly created directory receives a Chinese README with responsibility, allowed dependencies and file index; update direct parents. Add `docs/learning/` Phase 6 Chinese request/data-flow/testing/pitfalls material; update root, backend, frontend and admin README architecture/state/sequence diagrams, commands and interview evidence.
- **Browser:** after unit/API/Playwright gates, use the actual public UI/API: verified user records including near-midnight/backdated meals → `/app/records`; real admin login → independent admin SPA; ordinary/expired sessions denied; catalog lifecycle and config snapshot verified. Do not seed database or forge tokens for this acceptance path.

## No Analog Found

| File / concern | Reason / planner instruction |
|---|---|
| `backend/app/dashboard/weekly_review_graph.py` | Existing graph is meal-analysis/planning, not a facts-only single-purpose review graph. Use `agent` lifecycle/provider boundary but freeze the AI-SPEC limits and payload whitelist. |
| `admin-frontend/src/layouts/AdminShell.tsx` and desktop data-table/drawer components | No desktop admin UI exists. Copy frontend provider/feature isolation, then implement `06-UI-SPEC.md`’s 768/1024/1280 breakpoints and semantic table/Sheet contracts. |
| generic catalog draft/review/publish/eligibility ORM family | Existing version import is immutable but lacks workflow/overlay. Preserve immutable catalog model + SQL fail-closed qualification; do not mutate released rows. |

## Metadata

**Analog search scope:** `backend/app/{admin,agent,records,nutrition,planning,providers}`, `backend/tests`, `backend/migrations`, `frontend/src/{auth,features,layouts}`, `frontend/tests`, architecture/UI contracts.  
**Strong analogs read:** 14.  
**Pattern extraction date:** 2026-09-02.
