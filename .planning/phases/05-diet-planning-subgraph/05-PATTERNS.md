# Phase 5: 饮食规划子图 - Pattern Map

**Mapped:** 2026-09-01
**Files analyzed:** 29 planned/modified file responsibilities
**Analogs found:** 24 / 29

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/planning/__init__.py`, `README.md` | config / documentation | n/a | `backend/app/nutrition/README.md` | role-match |
| `backend/app/planning/schemas.py` | model | transform / request-response | `backend/app/nutrition/schemas.py` | exact |
| `backend/app/planning/ports.py` | service port | CRUD / transform | `backend/app/nutrition/ports.py` | exact |
| `backend/app/planning/models.py` | model | CRUD | `backend/app/records/models.py` | role-match |
| `backend/app/planning/repository.py` | repository | CRUD | `backend/app/records/repository.py` | exact |
| `backend/app/planning/service.py` | service | transform / CRUD | `backend/app/nutrition/service.py` | role-match |
| `backend/app/planning/api.py` | route / controller | request-response CRUD | `backend/app/records/api.py` | exact |
| `backend/app/planning/data/*` and `data/README.md` | config / seed data | file-I/O / batch | `backend/app/nutrition/data/*`, `importer.py` | role-match |
| `backend/app/agent/state.py` | model | state-machine / streaming | `backend/app/agent/state.py` (`MealAgentState`) | partial — must add a separate planning state, not reuse meal state |
| `backend/app/agent/graph.py` | controller | event-driven / state-machine | `MealAnalysisGraph` in the same file | role-match |
| `backend/app/agent/tools.py` | middleware / port adapter | request-response / transform | `NutritionToolAdapter` and `SessionNutritionToolAdapter` | exact |
| `backend/app/agent/service.py` | service | event-driven / streaming | `AgentService.execute_run` | role-match |
| `backend/app/agent/api.py`, `schemas.py` | route / model | SSE request-response | existing Agent API and snapshot DTO | role-match |
| `backend/app/main.py` | config | event-driven | `PersistedAgentRuntimeFactory.create` | exact |
| `backend/migrations/versions/0010_*planning*.py` | migration | batch / CRUD | `0007_meal_records_memory_ledger.py` | exact |
| `backend/tests/planning/test_*` | test | CRUD / transform | `backend/tests/records/test_record_service.py`, `backend/tests/unit/test_nutrition.py` | role-match |
| `backend/tests/integration/test_planning_*.py` | test | CRUD / isolation | `backend/tests/integration/test_meal_records.py` | role-match |
| `backend/tests/unit/test_diet_planning_graph.py` | test | state-machine / event-driven | `backend/tests/unit/test_agent_memory_context.py` | role-match |
| `docs/learning/05-diet-planning-subgraph.md` | documentation | n/a | `docs/learning/README.md` | partial |
| `frontend/src/features/plans/README.md` | documentation | n/a | `frontend/src/features/agent/README.md` | role-match |
| `frontend/src/features/plans/api/schemas.ts` | model | request-response | `frontend/src/features/records/api/schemas.ts` | exact |
| `frontend/src/features/plans/api/client.ts` | service | request-response CRUD | `frontend/src/features/records/api/client.ts` | exact |
| `frontend/src/features/plans/components/PlanPage.tsx` | component | request-response / streaming | `features/agent/components/AnalyzePage.tsx` | role-match |
| `frontend/src/features/plans/components/ProfileGoalForm.tsx` | component | request-response | `features/records/components/MealRecordEditPage.tsx` | role-match |
| `frontend/src/features/plans/components/{PlanOverview,MealCard,PlanningStatus}.tsx` | component | transform / streaming | `AnalyzePage.tsx`, `MealRecordDetailPage.tsx` | role-match |
| `frontend/src/features/plans/components/PersonalProfilePage.tsx` | component | CRUD | `features/memory/components/MemoryEditPage.tsx` | role-match |
| `frontend/src/features/plans/format.ts` and tests | utility / test | transform | `features/records/format.ts` | exact |
| `frontend/src/App.tsx`, `routePaths.ts`, `app/MePage.tsx` | route / component | request-response | same files | exact |
| feature/API/component/route tests plus `frontend/tests/e2e/plans.spec.ts` | test | request-response / streaming | `App.test.tsx`, `agent.spec.ts` | role-match |

## Pattern Assignments

### `backend/app/planning/{schemas.py,service.py,ports.py}` (deterministic domain service, transform)

**Analogs:** `backend/app/nutrition/schemas.py`, `backend/app/nutrition/service.py`, `backend/app/nutrition/ports.py`.

Use a closed action enum and frozen, `extra="forbid"` DTOs. The planning graph must branch on the returned action; it must never calculate targets or decide relaxations itself.

**DTO/version pattern** — `backend/app/nutrition/schemas.py:17-29,32-40`:

```python
TOOL_VERSION = "nutrition-tools-v1"
CALCULATION_RULE_VERSION = "per-100g-v1"

class NutritionAction(str, Enum):
    RECALCULATE = "RECALCULATE"
    ASK = "ASK"
    BLOCK = "BLOCK"
    WARN = "WARN"
    PASS = "PASS"

class NutritionValues(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    energy_kcal: Decimal
    protein_g: Decimal
    fat_g: Decimal
    carbohydrate_g: Decimal
```

**Result invariants pattern** — `backend/app/nutrition/schemas.py:123-140`:

```python
class NutritionCalculationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    action: NutritionAction
    food: QualifiedFood | None = None
    grams: Decimal | None = None
    nutrients: NutritionValues | None = None
    calculation_rule_version: str = CALCULATION_RULE_VERSION
    safe_message: str

    @model_validator(mode="after")
    def keeps_partial_and_completed_results_unambiguous(self) -> NutritionCalculationResult:
        has_nutrition = self.food is not None and self.grams is not None and self.nutrients is not None
        if self.action is NutritionAction.PASS and not has_nutrition:
            raise ValueError("a PASS calculation requires food, grams, and nutrients")
        if self.action is not NutritionAction.PASS and has_nutrition:
            raise ValueError("only PASS may expose calculated nutrition")
        return self
```

**Deterministic calculation then validation pattern** — `backend/app/nutrition/service.py:72-123,125-203`:

```python
food = self._repository.get_qualified_food(
    food_id=request.food_id, catalog_version=request.catalog_version
)
if food is None:
    return NutritionCalculationResult(
        action=NutritionAction.BLOCK,
        safe_message="所选食物不属于当前可计算的营养目录版本。",
    )

factor = grams / HUNDRED_GRAMS
return NutritionCalculationResult(
    action=NutritionAction.PASS,
    food=food,
    grams=grams,
    nutrients=NutritionValues(
        energy_kcal=source.energy_kcal * factor,
        protein_g=source.protein_g * factor,
        fat_g=source.fat_g * factor,
        carbohydrate_g=source.carbohydrate_g * factor,
    ),
    safe_message="营养值已按目录每 100 克基准确定性计算。",
)
```

Planning equivalents should be `TargetCalculationResult` and `PlanValidationResult` with a closed `PASS | REPLAN | RELAX | BLOCK_HEALTH_SCOPE | NEEDS_INPUT` action, rule/policy version, safe reason, and only safe public values. Aggregate unrounded `Decimal` values first; round only when building the report DTO.

**Port pattern** — `backend/app/nutrition/ports.py:12-19`:

```python
class NutritionRepository(Protocol):
    def search_qualified_foods(self, *, normalized_query: str, limit: int) -> list[QualifiedFood]: ...

    def get_qualified_food(
        self, *, food_id: uuid.UUID, catalog_version: str
    ) -> QualifiedFood | None: ...
```

Keep planning service dependencies behind `PlanningRepository` protocol methods; do not pass SQLAlchemy sessions or repositories into graph nodes.

---

### `backend/app/planning/{models.py,repository.py,api.py}` (tenant-bound profile CRUD)

**Analogs:** `backend/app/records/models.py`, `backend/app/records/repository.py`, `backend/app/records/api.py`, `backend/app/records/service.py`.

**Model/constraint pattern** — `backend/app/records/models.py:15-44`:

```python
class MealRecord(Base):
    __tablename__ = "meal_records"
    __table_args__ = (
        CheckConstraint("energy_kcal >= 0 AND protein_g >= 0 AND fat_g >= 0 AND carbohydrate_g >= 0", name="ck_meal_records_nonnegative_totals"),
        UniqueConstraint("user_id", "command_key", name="uq_meal_records_user_command_key"),
        Index("ix_meal_records_user_consumed_active", "user_id", "consumed_at", "id", postgresql_where=text("deleted_at IS NULL")),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Create one minimal planning profile authority for body fields and goal policy choice. Do **not** add avoidance or taste fields: those belong solely to `PreferenceMemoryLedger`/MemoryService. Persist policy/formula version and timestamps; use DB checks for enum/range facts that must remain true even outside API paths.

**Tenant-filtered query pattern** — `backend/app/records/repository.py:64-84`:

```python
def get_record_for_user(self, *, record_id: uuid.UUID, user_id: uuid.UUID, for_update: bool = False) -> MealRecord | None:
    statement = self._record_statement(user_id=user_id).where(MealRecord.id == record_id)
    if for_update:
        statement = statement.with_for_update()
    return self._session.scalar(statement)

@staticmethod
def _record_statement(*, user_id: uuid.UUID, include_deleted: bool = False):
    statement = select(MealRecord).options(selectinload(MealRecord.items)).where(MealRecord.user_id == user_id)
    if not include_deleted:
        statement = statement.where(MealRecord.deleted_at.is_(None))
    return statement
```

Every profile get/update/delete must take `user_id` in the SQL predicate. Foreign, missing, and deleted resources map to the same unavailable result.

**HTTP dependency/error mapping pattern** — `backend/app/records/api.py:25-35,69-101`:

```python
router = APIRouter(prefix="/api/v1/meal-records", tags=["meal-records"])
SessionDependency = Annotated[Session, Depends(get_session)]

def get_meal_record_service(session: SessionDependency) -> Generator[MealRecordService, None, None]:
    yield MealRecordService(
        repository=SqlAlchemyMealRecordRepository(session), commit=session.commit, rollback=session.rollback
    )

@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meal_record(record_id: uuid.UUID, principal: AuthenticatedPrincipal, service: ServiceDependency) -> None:
    try:
        service.delete_record(record_id=record_id, user_id=principal)
    except MealRecordUnavailable:
        raise _unavailable() from None

def _unavailable() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal record is unavailable.")
```

Use the same dependency shape for `/api/v1/planning/profile`; API only maps Pydantic HTTP DTOs to the service. Return 404 for a missing/foreign/deleted profile without revealing existence. Do not add an unauthenticated `user_id` path parameter.

**Transaction/soft-delete pattern** — `backend/app/records/service.py:105-135`:

```python
record = self._repository.get_record_for_user(record_id=record_id, user_id=user_id, for_update=True)
if record is None:
    raise MealRecordUnavailable("meal record is unavailable")
try:
    record.deleted_at = now
    record.updated_at = now
    self._commit()
except Exception:
    self._rollback()
    raise
```

Apply this to profile deletion so future planning reads see no profile. The service, not Repository, owns commit/rollback.

---

### `backend/app/agent/{state.py,graph.py,tools.py}` (planning subgraph and tool boundary)

**Analogs:** `MealAgentState` and `MealAnalysisGraph` in `backend/app/agent`, plus `NutritionToolAdapter`.

**Independent bounded state pattern** — `backend/app/agent/state.py:14-49,158-178`:

```python
STATE_VERSION = "meal-agent-state.v3"

class AgentBudget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    graph_steps: int = Field(default=0, ge=0, le=12)
    model_calls: int = Field(default=0, ge=0, le=4)
    tool_calls: int = Field(default=0, ge=0, le=12)
    active_elapsed_ms: int = Field(default=0, ge=0, le=45_000)
    estimated_cost_usd: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), le=Decimal("0.02"))

class MealAgentState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    state_version: str = STATE_VERSION
    user_id: uuid.UUID
    thread_id: uuid.UUID
    run_id: uuid.UUID
```

Create a separately versioned `DietPlanningState` with profile snapshot, three immutable meal slots, target/validation summaries, `replan_count <= 3`, safe interrupt payload, tool summaries, budget, next action, and safe report. Do not append planning fields to `MealAgentState`: research identifies the current state codec/checkpoint namespace as meal-analysis-specific.

**Graph construction and resume semantics** — `backend/app/agent/graph.py:111-145,165-183`:

```python
class MealAnalysisGraph:
    def __init__(self, *, provider: ReasoningModelProvider, tools: NutritionToolAdapter, ...) -> None:
        self._provider = provider
        self._tools = tools

    async def ainvoke(self, state: MealAgentState, *, resume: dict[str, object] | None = None) -> MealAgentState:
        # Invalid/no-answer resumes are a no-op, not a graph transition.
        if state.next_action is AgentNextAction.ASK_USER:
            if resume is None:
                return state
            preview = self._apply_resume(state, resume)
            if preview is state:
                return state
            state = preview
```

Planning `ainvoke` must accept only validated JSON resume payloads. An ambiguous meal target enters a contained `needs_input` state; invalid resumes leave the checkpoint untouched. Any state-changing side effect before interrupt must have a durable idempotency key.

**Only call narrow tools / account for budget** — `backend/app/agent/graph.py:502-561`:

```python
if tool_calls >= 12:
    return _limit_state(state)
search = self._tools.search_food_catalog(FoodSearchInput(query=item.search_query or item.normalized_name))
tool_calls += 1
summaries.append(_summary(item.item_id, "search", search.action.value, search))

calculation = self._tools.calculate_nutrition(...)
tool_calls += 1
validation = self._tools.validate_nutrition_result(NutritionValidationInput(calculation=calculation))
tool_calls += 1
```

`DietPlanningGraph` calls only planning/context/memory methods exposed by the tool port. For every target/candidate/validate/replan operation, increment the inherited budget and store only action/version/digest summaries. On the fourth requested replan, return a terminal safe result; never issue another composition call.

**Tool adapter pattern** — `backend/app/agent/tools.py:34-53,56-99`:

```python
class NutritionToolAdapter(Protocol):
    def search_food_catalog(self, request: FoodSearchInput) -> FoodSearchResult: ...
    def calculate_nutrition(self, request: NutritionCalculationInput) -> NutritionCalculationResult: ...
    def validate_nutrition_result(self, request: NutritionValidationInput) -> NutritionValidationResult: ...
    def retrieve_personal_context(self, *, user_id: uuid.UUID, query: str, catalog_version: str | None = None) -> list[RetrievedContextItem]: ...
    def capture_explicit_preferences(self, *, user_id: uuid.UUID, run_id: uuid.UUID, statement: str) -> tuple[CapturedPreferenceSummary, ...]: ...

class NutritionServiceToolAdapter:
    def calculate_nutrition(self, request: NutritionCalculationInput) -> NutritionCalculationResult:
        return self._service.calculate_nutrition(request)
```

Extend this **single** narrow boundary (or rename it only with all callers migrated) with planning operations. Do not let graph code import `PlanningRepository`, SQLAlchemy models, or MemoryService directly.

---

### `backend/app/agent/{service.py,api.py,schemas.py,main.py}` (thread ownership, checkpoint and safe SSE)

**Analogs:** existing Agent run lifecycle and event replay.

**Idempotent owned run pattern** — `backend/app/agent/service.py:116-168`:

```python
existing = self._repository.get_run_for_command_for_user(
    thread_id=thread_id, user_id=user_id, command_key=command_key, for_update=True,
)
if existing is not None:
    if existing.command_hash != command_hash:
        raise AgentCommandConflict("idempotency key payload mismatch")
    return existing
run = self._repository.add_run(AgentRun(
    id=uuid.uuid4(), thread_id=thread_id, user_id=user_id,
    command_key=command_key, command_hash=command_hash, status="accepted", ...,
))
```

Plan creation and feedback resume must reuse this ledger and `thread_id` ownership path. New plans create a new owned thread; adjustment commands reuse the selected plan thread with a new idempotency command key.

**Resume/checkpoint/fail-closed pattern** — `backend/app/agent/service.py:205-262`:

```python
previous = await self._load_checkpoint(checkpointer=checkpointer, thread_id=run.thread_id)
if resume_payload is not None and previous is not None:
    command: Command = Command(resume=resume_payload)
    state = previous.model_copy(update={"run_id": run.id, "status": AgentRuntimeStatus.ACCEPTED})
    finished = await graph.ainvoke(state, resume=command.resume)
...
try:
    await self._persist_checkpoint(checkpointer=checkpointer, state=finished)
except Exception:
    return await self._fail_run(run=run, user_id=user_id, code="CHECKPOINT_PERSIST_FAILED")
```

Refactor only enough to select a **validated planning state codec and distinct checkpoint namespace**; do not make the existing meal loader deserialize planning checkpoints. Preserve ownership, budget accounting and fail-closed persistence.

**Safe event ledger pattern** — `backend/app/agent/service.py:446-490`, `backend/app/agent/api.py:316-329`:

```python
event = self._repository.add_event(AgentEvent(
    thread_id=thread_id, run_id=run_id, user_id=user_id,
    seq=self._repository.next_event_seq_for_thread_for_user(thread_id=thread_id, user_id=user_id),
    event_type=event_type, payload=payload, safe_summary=safe_summary,
))

body = json.dumps({"type": event.event_type, "summary": event.safe_summary}, ensure_ascii=False)
yield f"id: {event.seq}\\nevent: agent\\ndata: {body}\\n\\n"
```

Planning events must be a closed safe enum (`reading_context`, `calculating_targets`, `composing_plan`, `validating_plan`, `complete`, `needs_input`) and must never expose prompt text, tool output, candidate ranking, token/cost data, checkpoint IDs, exclusions beyond the safe report, or model reasoning.

**Runtime wiring pattern** — `backend/app/main.py:54-73`:

```python
session_factory = create_session_factory(self._settings)
memory_provider = create_memory_provider(self._settings)
tools = SessionNutritionToolAdapter(session_factory=session_factory, memory_provider=memory_provider)
provider = create_reasoning_provider(self._settings)
graph = MealAnalysisGraph(provider=provider, vision_provider=vision_provider, tools=tools)
```

Wire PlanningService and DietPlanningGraph at the lifespan factory; preserve the existing one `AgentRuntime`, provider factory, checkpointer and supervisor. Register the independent planning profile router in `app/main.py` alongside `meal_records_router` and `memories_router`.

---

### `backend/app/memory/*` integration (explicit feedback capture only)

**Analog:** `backend/app/memory/service.py` and adapter use in `backend/app/agent/tools.py`.

**Explicit-only capture pattern** — `backend/app/memory/service.py:83-96,244-266`:

```python
def capture_explicit_preferences(self, *, user_id: uuid.UUID, source_run_id: uuid.UUID, statement: str) -> list[PreferenceMemoryLedger]:
    """Persist only deterministic first-person statements; guesses stay proposals."""
    captured: list[PreferenceMemoryLedger] = []
    for category, canonical_text in self._extract_explicit_preferences(statement):
        ledger = self.create_direct(
            user_id=user_id, source_run_id=source_run_id,
            category=category, canonical_text=canonical_text,
        )
        captured.append(ledger)
    return captured

if category not in ALLOWED_CATEGORIES or not normalized:
    raise MemoryValidationError("invalid preference memory")
```

Planning feedback such as “不吃某菜” or “换清淡” must travel through this existing method and its durable request key/outbox semantics. Do not create a profile-preferences column, a parallel preferences table, or a direct Mem0 call.

---

### `backend/migrations/versions/0010_*planning*.py` (migration)

**Analog:** `backend/migrations/versions/0007_meal_records_memory_ledger.py:13-39`.

```python
revision: str = "0007"
down_revision: str | None = "0006"

def upgrade() -> None:
    op.create_table(
        "meal_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        ...
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_meal_records_user_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_meal_records"),
    )
    op.create_index("ix_meal_records_user_consumed_active", "meal_records", ["user_id", "consumed_at", "id"], unique=False, postgresql_where=sa.text("deleted_at IS NULL"))
```

Migration is the only schema-change path. Match current naming (`pk_`, `fk_`, `ck_`, `ix_`), `Uuid`, timezone-aware timestamps, user FK, and an active-row index. Write a complete reverse-order downgrade.

---

### `frontend/src/features/plans/api/{schemas.ts,client.ts}` (validated public API client)

**Analog:** `frontend/src/features/records/api/schemas.ts:1-5`, `client.ts:1-13`.

```typescript
export const mealRecordSchema = z.object({
  id: z.string().uuid(),
  consumed_at: z.string(),
  nutrition_catalog_version: z.string(),
  calculation_version: z.string(),
  energy_kcal: z.string(),
  ...
}).strict()

async function parsed(response: Response): Promise<MealRecord> {
  return mealRecordSchema.parse(await response.json())
}

export async function getMealRecord(request: ApiRequest, id: string): Promise<MealRecord> {
  const response = await request(`/meal-records/${id}`)
  if (!response.ok) throw new Error('record unavailable')
  return parsed(response)
}
```

Define strict Zod schemas for profile, safe plan report, metric target range, meal slot, safe relaxation/refusal, and Agent snapshot projection. Keep JSON decimals as the server contract provides; presentation formatting belongs in `plans/format.ts`. All requests use `AuthenticatedRequest`, never raw `fetch`, and route through only `/api/v1` via the AuthProvider request wrapper.

---

### `frontend/src/features/plans/components/PlanPage.tsx` (plan tab, snapshot-first stream)

**Analogs:** `frontend/src/features/agent/components/AnalyzePage.tsx:71-126`, `frontend/src/features/agent/stream/useAgentEventStream.ts:32-97`.

```typescript
const applySnapshot = useCallback(async (response: Response) => {
  const body = await response.json().catch(() => undefined)
  if (!response.ok) throw new Error('agent snapshot request failed')
  const next = agentThreadSnapshotSchema.parse(body)
  setSnapshot(next)
  setStatus(next.status === 'completed' ? 'completed' : ...)
}, [])

useAgentEventStream({
  threadId: snapshot?.thread_id,
  request,
  onEvent: (event) => setProgress(event.summary),
  onSnapshot: applySnapshot,
})
```

Reuse `useAgentEventStream`; do not create another event parser. Map only the six planning business event names to the UI-SPEC copy. Snapshot parsing remains authoritative; SSE only updates the polite current-state summary. Preserve form values, disclaimer and shell during loading/error.

**Safe SSE protocol pattern** — `frontend/src/features/agent/stream/useAgentEventStream.ts:39-90`:

```typescript
const response = await request(snapshotPath, { signal: controller.signal })
if (!response.ok) return false
await snapshotCallbackRef.current?.(response)
...
if (sequence !== lastSequenceRef.current + 1) {
  observedGap = true
  return
}
const payload = JSON.parse(event.data) as { type?: string; summary?: string }
if (typeof payload.type !== 'string' || typeof payload.summary !== 'string') return
eventCallbackRef.current({ id: String(sequence), type: payload.type, summary: payload.summary })
```

Do not surface the generic raw `summary` blindly. The plans component accepts only the known enum and renders the contract copy with `aria-live="polite"`.

---

### `frontend/src/features/plans/components/{ProfileGoalForm,PersonalProfilePage}.tsx` (form and profile CRUD)

**Analogs:** `MealRecordEditPage.tsx`, `MemoryEditPage.tsx`, `AccountDetailsPage.tsx`.

**Visible labels, mutation and destructive confirmation** — `frontend/src/features/records/components/MealRecordEditPage.tsx:1-11`:

```tsx
const { recordId = '' } = useParams()
const navigate = useNavigate()
const { request } = useAuth()
const [value, setValue] = useState('')
const [open, setOpen] = useState(false)
...
<Label htmlFor="consumed-at">用餐时间</Label>
<Input className="h-11" id="consumed-at" ... />
<AlertDialog onOpenChange={setOpen} open={open}>
  <AlertDialogContent>...</AlertDialogContent>
</AlertDialog>
```

Implement the Phase 5 profile/goal form with React Hook Form + Zod (the project-standard requirement, even though earlier small edit pages are hand-managed). Preserve the analog's label/id, `h-11` minimum target, local error/loading state, authenticated mutation, navigation and AlertDialog structure. The plan form must show memory as read-only summary plus a link; the personal profile page must not render avoidance/taste controls.

**Label-value read view pattern** — `frontend/src/app/AccountDetailsPage.tsx:26-42`:

```tsx
<section aria-label="账号资料">
  <dl className="grid gap-4 text-[15px] leading-6">
    <div>
      <dt className="text-[13px] leading-5 text-muted-foreground">邮箱</dt>
      <dd className="break-all font-medium text-foreground">{user.email}</dd>
    </div>
  </dl>
</section>
```

Use the same `dl/dt/dd` presentation for the profile view state. Empty, edit, deletion-success, refusal and API-error modes remain explicit components/states rather than overloading one `undefined` branch.

---

### `frontend/src/features/plans/components/{PlanOverview,MealCard,PlanningStatus}.tsx` and `format.ts` (safe result presentation)

**Analogs:** `MealRecordDetailPage.tsx:1-10`, `BottomNavigation.tsx:23-45`, and current shadcn primitives.

**Card and tabular number pattern** — `frontend/src/features/records/components/MealRecordDetailPage.tsx:1-10`:

```tsx
<Card>
  <CardHeader><CardTitle className="tabular-nums">合计 {formatNutrition(record.energy_kcal)} kcal</CardTitle></CardHeader>
  <CardContent className="space-y-3">
    {record.items.map((item) => <div key={item.id}>...</div>)}
  </CardContent>
</Card>
```

Build exactly three ordered cards (早餐 → 午餐 → 晚餐), plus a daily overview with target range/value/status rows. `format.ts` owns whole-number/range rendering. Cards are informational: no dish-row buttons. Status always includes text and icon, not color alone. Use only semantic Tailwind/shadcn tokens, no hard-coded health palette or model/tool details.

**Route-derived active tab pattern** — `frontend/src/layouts/BottomNavigation.tsx:23-45`:

```tsx
<NavLink
  className={({ isActive }) => [
    'inline-flex min-h-11 flex-col items-center justify-center ...',
    isActive ? 'font-semibold text-primary' : 'font-normal',
  ].join(' ')}
  end
  to={to}
>
```

`/app/plans` must stay inside `AppShell`; `NavLink` supplies real “计划，当前页面” semantics. `/app/me/profile` belongs to `DetailLayout`, so it has no Tab bar and inherits the one scroll area.

---

### `frontend/src/{App.tsx,routePaths.ts,app/MePage.tsx}` (route registration and settings entry)

**Analogs:** current route composition and settings links.

**Route composition pattern** — `frontend/src/App.tsx:48-74`:

```tsx
<Route element={<RequireAuthentication />}>
  <Route path="/app">
    <Route element={<AppShell />}>
      <Route path="plans" element={<PlaceholderTabPage title="计划" />} />
      <Route path="me" element={<MePage />} />
    </Route>
    <Route element={<DetailLayout title="饮食偏好与记忆" />}>
      <Route path="me/memories" element={<MemoryManagementPage />} />
    </Route>
  </Route>
</Route>
```

Replace only the `plans` placeholder with PlanPage, add `me/profile` under `DetailLayout title="个人资料"`, and keep App.tsx composition-only.

**Central static path pattern** — `frontend/src/routePaths.ts:6-16`:

```typescript
export const routePaths = {
  app: '/app',
  analyze: '/app/analyze',
  records: '/app/records',
  plans: '/app/plans',
  me: '/app/me',
} as const

export const protectedRoutePaths = new Set<string>(Object.values(routePaths))
```

Add `profile: '/app/me/profile'` here and use it from the Me link and plan actions; do not scatter string literals.

**Native settings link pattern** — `frontend/src/app/MePage.tsx:20-37`, `SettingsLinkRow.tsx:15-27`:

```tsx
<SettingsLinkRow
  description="查看和管理会影响后续建议的偏好。"
  icon={Brain}
  title="饮食偏好与记忆"
  to="/app/me/memories"
/>

<Link className="flex min-h-14 items-center gap-3 ..." to={to}>
  <Icon aria-hidden="true" className="h-5 w-5 ..." />
  ...
</Link>
```

Add “个人资料 / 管理身体资料与计划目标” as another `SettingsLinkRow` with a suitable Lucide icon. Keep the memory link unchanged and separate.

---

### Tests, migration verification and documentation

**Service fake/graph fake pattern** — `backend/tests/unit/test_agent_memory_context.py:48-81`:

```python
tools = NutritionServiceToolAdapter(
    service=NutritionService(repository=FakeNutritionRepository(food)),
    context_service=FakeContextService(),
    explicit_preference_capture_service=capture,
)
graph = MealAnalysisGraph(provider=RiceOnlyFakeReasoningModelProvider(), tools=tools)
result = asyncio.run(graph.ainvoke(state))
assert result.report is not None
assert result.explicit_preference_capture_completed is True
```

Use fake PlanningRepository + Fake Provider for deterministic target policy, `PASS/REPLAN/RELAX/BLOCK_HEALTH_SCOPE`, slot-local replacement, no fourth replan, interrupt/resume and no raw feedback/internal IDs in serialized state/events. Use real PostgreSQL integration tests for profile isolation and deletion-before-read. Add HTTPX tests for 401/404/422 and frontend Zod/API/component tests plus Playwright real route coverage.

**Route/a11y test pattern** — `frontend/src/App.test.tsx:84-118`:

```tsx
expect(await screen.findByRole('heading', { name: '分析这餐' })).toBeInTheDocument()
expect(screen.getByRole('navigation', { name: '主要导航' })).toBeInTheDocument()
...
expect(await screen.findByRole('heading', { level: 1, name: '账号资料' })).toHaveFocus()
```

Extend this pattern for `/app/plans`, `/app/me/profile`, back navigation, bottom-tab presence/absence, focus after replacement/refusal/delete, and the UI-SPEC loading/empty/error/relaxation/replan-limit states.

All new directories require a README with responsibility, permitted dependencies and file index; update direct parent indexes. Add the required Chinese learning document explaining deterministic data flow, tool boundary, checkpoint/resume, profile/privacy deletion, tests and common mistakes.

## Shared Patterns

### Authentication and resource isolation

**Sources:** `backend/app/records/api.py:38-46`, `backend/app/records/repository.py:64-84`.

Use `AuthenticatedPrincipal` only at protected API boundaries and SQL predicates containing `user_id` for every profile/thread/run/event read or write. UUID alone is never authorization.

### Deterministic numerical truth

**Sources:** `backend/app/nutrition/service.py:110-123,168-203`; `backend/app/agent/tools.py:34-53`.

Compute through versioned services with Decimal; Graphs and browser consume action-bearing DTOs only. The UI renders safe target ranges and outcomes, never formulas/model output.

### Explicit-memory audit and idempotency

**Sources:** `backend/app/memory/service.py:48-96,269-281`; `backend/app/agent/service.py:116-168`.

Only explicit feedback reaches MemoryService. Use existing user/run/category/text-derived opaque keys and AgentRun command-key uniqueness for retry safety.

### Safe snapshot-first SSE

**Sources:** `backend/app/agent/api.py:316-329`; `frontend/src/features/agent/stream/useAgentEventStream.ts:32-97`.

Persist safe events; replay them after a tenant-filtered snapshot; handle a one-time sequence-gap reconnect; never drive the graph from the browser stream.

### H5 shell and accessible controls

**Sources:** `frontend/src/layouts/AppShell.tsx:11-24`, `frontend/src/layouts/DetailLayout.tsx:14-21`, `frontend/src/app/SettingsLinkRow.tsx:15-27`.

Tab roots use AppShell’s sole scroll region and bottom navigation. Profile detail uses DetailLayout. Use native `Link`/`NavLink`, visible labels, `h-11`/`min-h-11` controls, semantic token classes, focus handling and AlertDialog for irreversible deletion.

## No Analog Found

| File / responsibility | Role | Data Flow | Reason and planner guidance |
|---|---|---|---|
| `backend/app/planning/*` as a complete domain | service/module | deterministic composition | No existing profile + recipe + target-policy module. Compose the documented nutrition, records and memory patterns; do not clone any module wholesale. |
| `DietPlanningState` plus separate checkpoint namespace/codec | model | state-machine | Meal state and checkpoint helpers are analysis-specific. Design a parallel validated state/namespace and add regression tests proving no cross-subgraph deserialization. |
| controlled recipe schema/seed data | model/config | batch/transform | Nutrition contains qualified foods but no Phase-5 recipe aggregate. Use versioned food references and recompute nutrition from the catalog. |
| planning-safe SSE projection | schema | streaming | Existing event type is generic. Add a closed planning enum and UI mapper; do not expose generic internal summary text. |
| `frontend/src/features/plans/*` | feature | request-response/streaming | Directory is intentionally reserved but has no implementation. Follow agent/records/memory boundaries, not a page-level global API/hook directory. |
| optional `radio-group`, `select`, `textarea` primitives | UI config | request-response | These primitives are not present. Only add official shadcn/Base UI blocks if native controls cannot satisfy UI-SPEC; no third-party registry blocks. |

## Metadata

**Analog search scope:** `backend/app/{agent,nutrition,records,memory}`, `backend/migrations/versions`, `backend/tests`, `frontend/src/{app,features,layouts}`, `frontend/tests`, `docs/learning`
**Files scanned:** 61
**Pattern extraction date:** 2026-09-01
