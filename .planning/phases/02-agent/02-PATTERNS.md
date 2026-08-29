# Phase 2: 可追问的 Agent 核心 - Pattern Map

**Mapped:** 2026-08-28
**范围:** 从 `02-CONTEXT.md`、`02-AI-SPEC.md`、`02-RESEARCH.md` 推导的 29 个文件/模块组
**强类比来源:** 5 组（认证 API、分层事务、Provider port、迁移/真实 PostgreSQL、认证 H5）
**覆盖:** 25 / 29 个模块组存在 exact 或 role-match；4 组必须建立新模式

> 上游没有冻结逐文件清单。下表中的路径是研究建议与现有仓库结构共同推导出的规划边界；规划器可以拆分文件，但不能合并 API Schema、ORM Model、LangGraph State 与 Provider DTO。

## File Classification

| New/Modified File or Module | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/agent/api.py` | route/controller | request-response + SSE | `backend/app/admin/api.py`、`backend/app/auth/api.py` | role-match |
| `backend/app/agent/schemas.py` | schema | request-response transform | `backend/app/auth/schemas.py` | exact |
| `backend/app/agent/service.py` / `supervisor.py` | service | event-driven + transactional | `backend/app/admin/service.py` | role-match |
| `backend/app/agent/ports.py` | port | CRUD + event append/read | `backend/app/admin/ports.py` | exact |
| `backend/app/agent/repository.py` | repository | CRUD + lease/row lock | `backend/app/auth/repository.py`、`backend/app/admin/repository.py` | exact |
| `backend/app/agent/models.py` | model | CRUD + append-only audit | `backend/app/admin/models.py` | exact |
| `backend/app/agent/state.py` | state | event-driven transform | none | no analog |
| `backend/app/agent/graph.py`、`meal_graph.py`、`nodes.py`、`routing.py` | graph/hook/utility | event-driven + interrupt/resume | none | no analog |
| `backend/app/agent/events.py` | schema/utility | pub-sub + streaming | none | no analog |
| `backend/app/nutrition/schemas.py` | schema | transform | `backend/app/auth/schemas.py` | exact |
| `backend/app/nutrition/service.py` | service | CRUD + deterministic transform | `backend/app/auth/service.py` | role-match |
| `backend/app/nutrition/ports.py` | port | CRUD | `backend/app/auth/ports.py` | exact |
| `backend/app/nutrition/repository.py` | repository | read-heavy CRUD | `backend/app/auth/repository.py` | exact |
| `backend/app/nutrition/models.py` | model | CRUD | `backend/app/auth/models.py` | exact |
| `backend/app/providers/reasoning/ports.py`、`dto.py` | provider/schema | request-response | `backend/app/notifications/ports.py` | role-match |
| `backend/app/providers/reasoning/deepseek.py`、`fake.py` | provider/test double | async request-response | `backend/app/notifications/smtp.py` | role-match |
| `backend/app/core/config.py` | config | validation/transform | same file | exact modification |
| `backend/app/main.py` | config/provider | lifecycle + request-response | same file | role-match modification |
| `backend/migrations/versions/0004_*.py` | migration | batch schema change | `0001_auth_foundation.py`、`0003_admin_audit.py` | exact |
| `backend/scripts/nutrition_catalog/*` | utility/importer | file-I/O + batch | none | no analog |
| `backend/tests/unit/agent/*`、`unit/nutrition/*` | test | transform + event-driven | `tests/auth/test_login_me_service.py` | role-match |
| `backend/tests/api/test_agent.py` | test | request-response + streaming | `tests/auth/test_login_me_api.py` | exact |
| `backend/tests/integration/agent/*`、`integration/nutrition/*` | test | CRUD + persistence | `tests/integration/test_auth_migration.py`、`tests/conftest.py` | exact |
| `frontend/src/features/agent/api/*` | client/service/schema | request-response | `frontend/src/auth/api.ts` | exact |
| `frontend/src/features/agent/stream/*` | hook/utility | streaming + event-driven | none | no analog |
| `frontend/src/features/agent/AnalyzePage.tsx`、`components/*` | component | request-response + event-driven | `frontend/src/auth/SessionList.tsx` | role-match |
| `frontend/src/App.tsx`、`routePaths.ts` | route/config | request-response | same files | exact modification |
| `frontend/src/features/agent/*.test.tsx` | test | event-driven UI | `frontend/src/app/AppPages.test.tsx` | role-match |
| `frontend/tests/e2e/agent*.spec.ts` | test | end-to-end request-response + streaming | `frontend/tests/e2e/auth-skeleton.spec.ts` | role-match |

## Pattern Assignments

### 1. `backend/app/agent/api.py` — HTTP/SSE 边界

**Primary analog:** `backend/app/admin/api.py` 22–55；错误壳补充参考 `backend/app/auth/api.py` 426–440。

**Router、请求级组合和权威认证模式** (`backend/app/admin/api.py:22-55`):

```python
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

def get_admin_service(session: Session = Depends(get_session)) -> AdminService:
    return AdminService(
        repository=SqlAlchemyAdminRepository(session),
        commit=session.commit,
        rollback=session.rollback,
    )

@router.get("/probe", response_model=AdminProbeResponse)
def probe(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    authentication_service: AuthenticationService = Depends(get_authentication_service),
    admin_service: AdminService = Depends(get_admin_service),
) -> AdminProbeResponse | JSONResponse:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return _authentication_required()
    user_id, _session_id = authentication_service.authenticated_session(
        credentials.credentials
    )
```

复制点：route 只解析 HTTP、组合依赖、把稳定领域异常映射为状态码；认证必须经现有 `AuthenticationService.authenticated_session()` 回查 PostgreSQL。Agent route 取得 `user_id` 后还要让 Agent Service 校验 `(thread_id, user_id)`，且必须在读取 Checkpoint 前完成。

**稳定错误 envelope** (`backend/app/auth/api.py:426-440`):

```python
def _error(*, status_code: int, code: str, message: str,
           retry_after: int | None = None) -> JSONResponse:
    error: dict[str, str | int] = {
        "code": code,
        "message": message,
        "request_id": str(uuid.uuid4()),
    }
    if retry_after is not None:
        error["retry_after"] = retry_after
    return JSONResponse(status_code=status_code, content={"error": error})
```

不要复制的缺陷：不要把认证、线程所有权、SSE 编码分别写成多套私有 helper。Phase 2 endpoint 多，规划应抽取共享 authenticated-user dependency 与公共错误 presenter，否则错误语义必然漂移。

### 2. Agent Run Service、Repository、ORM — 权威账本与事务

**Primary analog:** `backend/app/admin/service.py`、`backend/app/admin/repository.py`、`backend/app/admin/models.py`。

**Service 拥有规则与事务** (`backend/app/admin/service.py:22-36,89-117`):

```python
class AdminService:
    def __init__(self, *, repository: AdminRepository,
                 now: Callable[[], datetime] | None = None,
                 commit: Callable[[], None] | None = None,
                 rollback: Callable[[], None] | None = None) -> None:
        self._repository = repository
        self._now = now or (lambda: datetime.now(UTC))
        self._commit = commit or (lambda: None)
        self._rollback = rollback or (lambda: None)

    def _commit_promotion(...):
        audit = self._repository.add_audit(AdminRoleAudit(...))
        try:
            self._commit()
        except Exception:
            self._rollback()
            raise
        return audit
```

复制点：把 clock、commit、rollback 注入 Service；run 接受、线程 revision、event append、invocation ledger 与 lease 状态变更必须在 Service 规定的事务中提交。Repository 不决定 `LIMIT_REACHED`、重试资格或 HTTP 404。

**Repository 只 flush/lock，不 commit** (`backend/app/admin/repository.py:14-34,48-51`):

```python
class SqlAlchemyAdminRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_user_for_update(self, user_id: uuid.UUID) -> User | None:
        return self._session.scalar(
            select(User).where(User.id == user_id).with_for_update()
        )

    def add_audit(self, audit: AdminRoleAudit) -> AdminRoleAudit:
        self._session.add(audit)
        self._session.flush()
        return audit
```

对 Agent 的直接映射：分配单线程 `event.seq`、更新 snapshot revision、领取 lease、读取/完成 invocation 都需 `with_for_update()` 或唯一约束提供并发证明；`session.commit()` 仍只能由 Service 调用。

**ORM 约束与索引模式** (`backend/app/admin/models.py:14-47`):

```python
class AdminRoleAudit(Base):
    __tablename__ = "admin_role_audit"
    __table_args__ = (
        CheckConstraint(..., name="ck_admin_role_audit_reason"),
        Index("ix_admin_role_audit_target_occurred_at", "target_user_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    target_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
```

现有跨模块 Base 惯例是 `from app.auth.models import Base`（`admin/models.py:11`）。这是架构债，但它是当前真实模式；除非计划显式包含 Base 迁移，不要在 Phase 2 顺手再造第二个 metadata root。

### 3. `backend/app/nutrition/*` — 确定性领域分层

**Primary analog:** `backend/app/auth/ports.py`、`repository.py`、`service.py`、`schemas.py`。

**窄 Repository Protocol** (`backend/app/auth/ports.py:12-15,29-39`):

```python
class AuthRepository(Protocol):
    def get_login_blocked_until(... ) -> datetime | None: ...
    def add_user(self, user: User) -> User: ...
    def get_user_by_id(self, user_id: uuid.UUID) -> User | None: ...
    def get_current_challenge_for_update(...) -> VerificationChallenge | None: ...
```

Nutrition 应复制“Service 依赖 Protocol、SQLAlchemy adapter 实现它”的形状。Graph node 只能依赖 `search_food_catalog` / `calculate_nutrition` / `validate_nutrition_result` 三个窄 Application Service adapter，不能持有该 Repository Protocol。

**运行时 schema 与 ORM 分离** (`backend/app/auth/schemas.py:23-36,59-75`):

```python
class LoginRequest(BaseModel):
    email: EmailAddress
    password: str = Field(min_length=12, max_length=128)

class PublicUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: EmailAddress
```

Nutrition tool input/output、资格候选、内部精度结果、校验 action 都应为独立 Pydantic DTO；`Decimal` 计算发生在 Service，展示舍入只在 API response presenter。不要让 ORM row、API response 或 LangGraph State 充当工具 DTO。

**所有权过滤应进 SQL 条件** (`backend/app/auth/repository.py:154-162`):

```python
def get_session_for_user(self, *, session_id: uuid.UUID,
                         user_id: uuid.UUID) -> AuthSession | None:
    return self._session.scalar(
        select(AuthSession).where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id,
        )
    )
```

Agent thread lookup必须同样用 `(thread_id, user_id)` 一次查询，不能先按 thread_id 读取再在 Python 比较；统一“不存在/越权”安全语义。

### 4. `backend/app/providers/reasoning/*` — Port、Adapter、Fake、DTO

**Primary analog:** `backend/app/notifications/ports.py` 与 `smtp.py`。

**Protocol port** (`backend/app/notifications/ports.py:5-11`):

```python
from typing import Protocol

class MailProvider(Protocol):
    def send_verification_code(
        self, *, recipient: str, code: str, expires_in_minutes: int
    ) -> None: ...
```

Reasoning Provider 应复制结构隔离，而不是方法语义：定义窄 `parse_meal()` / `apply_correction()` async port，入参与返回值使用 Provider DTO；Fake 实现同一 Protocol，测试不得导入 DeepSeek client。

**Adapter 只从已验证 settings 构造** (`backend/app/notifications/smtp.py:53-70`):

```python
def create_smtp_mail_provider(settings: Settings) -> SMTPMailProvider:
    if not settings.smtp_from_email:
        raise ConfigurationError("SMTP_FROM_EMAIL is required for the mail provider")
    return SMTPMailProvider(
        host=settings.smtp_host,
        port=settings.smtp_port,
        ...
    )
```

差异必须显式实现：DeepSeek adapter 是 async HTTP、需 JSON Schema + Pydantic 二次校验、稳定错误分类、一次瞬时重试、token/cost/latency 元数据和 `PROVIDER_OUTCOME_UNKNOWN`；SMTP analog 不提供这些能力。

### 5. `backend/app/core/config.py` 与 `backend/app/main.py` — fail-closed 配置和生命周期

**Settings pattern** (`backend/app/core/config.py:17-40,40-70`):

```python
class Settings(BaseSettings):
    app_env: Literal["local", "test", "production"] = "local"
    secret_key: SecretStr = SecretStr(...)
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_runtime_boundaries(self) -> Settings:
        ...
        if self.app_env != "production":
            return self
        ...
```

Provider secret、model alias、checkpoint conninfo、graph/model/tool/time/cost budget、SSE heartbeat/lease 参数进入同一 Settings 边界。生产缺 secret/价格快照/保留配置时必须失败，不能回退 Fake Provider 或开发值。

**App factory、router、稳定全局错误** (`backend/app/main.py:18-39,41-69`):

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    application = FastAPI(...)
    application.state.settings = active_settings
    ...
    application.include_router(auth_router)

@application.exception_handler(Exception)
async def internal_error(...) -> JSONResponse:
    return JSONResponse(status_code=500, content={"error": {
        "code": "INTERNAL_ERROR",
        "message": "服务暂时不可用，请稍后重试。",
        "request_id": str(uuid.uuid4()),
    }})
```

需要建立的新模式：现有 `create_app()` 没有 lifespan。Phase 2 必须把 `AsyncPostgresSaver`、共享 `httpx.AsyncClient`、编译图和 supervisor 生命周期放入 FastAPI lifespan；`setup()` 作为显式初始化步骤，不在每次请求或每个 worker 启动中运行。

### 6. Alembic 与真实 PostgreSQL

**Primary analog:** `backend/migrations/versions/0001_auth_foundation.py`、`0003_admin_audit.py`。

**显式命名约束、索引与可逆 downgrade** (`0003_admin_audit.py:19-58`):

```python
def upgrade() -> None:
    op.create_table(
        "admin_role_audit",
        sa.Column("id", sa.Uuid(), nullable=False),
        ...,
        sa.CheckConstraint(..., name="ck_admin_role_audit_reason"),
        sa.PrimaryKeyConstraint("id", name="pk_admin_role_audit"),
    )
    op.create_index("ix_admin_role_audit_target_occurred_at", ...)

def downgrade() -> None:
    op.drop_index(...)
    op.drop_table("admin_role_audit")
```

业务表（threads/runs/invocations/events/catalog）全部进下一条 Alembic revision。Checkpointer 自有表不伪装成业务 migration；两者在测试清理与部署初始化中分别管理。

### 7. 后端测试 — fake Service、HTTPX/TestClient 合约、真实 PostgreSQL

**Fake Repository + 注入 clock/commit** (`backend/tests/auth/test_login_me_service.py:26-67,87-99`):

```python
class FakeAuthRepository:
    def __init__(self, users: list[User]) -> None:
        self.users = {user.id: user for user in users}
        self.sessions: list[AuthSession] = []

def _service(repository: FakeAuthRepository, *, commit: list[bool] | None = None):
    return AuthenticationService(
        repository=repository,
        now=lambda: NOW,
        commit=(lambda: commit.append(True)) if commit is not None else None,
    )
```

Agent/Nutrition 单测复制依赖注入和可观察调用轨迹；Fake clock/token/cost/provider/tool 必须用于预算边界，禁止 `sleep`。图测试要断言 State diff、路由、interrupt/resume、脏项和“终态后零新增调用”。

**Dependency override + 稳定错误断言** (`backend/tests/auth/test_login_me_api.py:37-86,118-130`):

```python
application = create_app(_settings(...))
application.dependency_overrides[get_authentication_service] = lambda: service
client = TestClient(application)

assert response.json()["error"]["code"] == "AUTHENTICATION_FAILED"
assert set(response.json()["error"]) == {"code", "message", "request_id"}
assert submitted not in response.text
```

Agent API 测试应同样替换 Service/Provider，但所有权、thread/run/event 表仍用真实 PostgreSQL；SSE 断言公开 allowlist 和事件序列，禁止内部 node/state/provider body。

**数据库 fail-closed fixture** (`backend/tests/conftest.py:44-69`):

```python
@pytest.fixture(scope="session")
def test_engine():
    test_url = validate_test_database_configuration(_guarded_test_settings())
    _upgrade_test_database()
    engine = create_engine(test_url, pool_pre_ping=True)
    ...

@pytest.fixture
def db_session(test_engine: Engine):
    connection = test_engine.connect()
    outer_transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
```

Checkpointer 是独立提交连接，不能依赖上面 transaction rollback；其测试必须每例唯一 `thread_id/checkpoint_ns`，显式清理 saver 表，并至少关闭重建一次 saver/graph 后 resume。

### 8. `frontend/src/features/agent/api/*` — 认证 fetch 与公开契约

**Primary analog:** `frontend/src/auth/api.ts`、`AuthProvider.tsx`。

**公开 API URL 与网络错误边界** (`frontend/src/auth/api.ts:102-135`):

```typescript
export function apiUrl(path: string) {
  if (!path.startsWith('/')) throw new Error('API paths must begin with a slash.')
  return `${apiBaseUrl}${path}`
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  ...
}
```

**一次 refresh、一次 replay** (`frontend/src/auth/AuthProvider.tsx:103-120`):

```typescript
const request = useCallback(async (path: string, init?: RequestInit) => {
  const active = sessionRef.current
  if (!active) return new Response(null, { status: 401 })
  const firstResponse = await requestWithAccess(path, active.accessToken, init)
  if (firstResponse.status !== 401) return firstResponse
  const refreshed = await refresh()
  if (!refreshed) return firstResponse
  return requestWithAccess(path, refreshed.accessToken, init)
}, [refresh])
```

所有 Agent command、snapshot 和 SSE 都走 `useAuth().request`。SSE 不得用原生 `EventSource`、query token 或扩大 refresh cookie path；401 只允许现有的一次 replay。

### 9. TanStack Query、页面状态与 SSE hook

**Primary analog:** `frontend/src/auth/SessionList.tsx`。

**权威 snapshot query + mutation invalidation** (`SessionList.tsx:23-43`):

```typescript
const { request, user } = useAuth()
const queryClient = useQueryClient()
const sessionsQuery = useQuery({
  enabled: Boolean(user?.id),
  queryFn: () => readSessions(request),
  queryKey: ['auth', 'sessions', user?.id],
  retry: false,
})
const revokeMutation = useMutation({
  mutationFn: async (...) => { ... },
  onSuccess: async () => {
    await queryClient.invalidateQueries({ queryKey: [...] })
  },
})
```

Agent query key 至少包含 `['agent-thread', user.id, threadId]`。Query 只保存权威 snapshot；无限 SSE 由独立 `useAgentEventStream` effect 管理。业务事件只能更新短暂进度或使 snapshot 失效；最终报告不得以事件流本地拼装为真值。

**可访问状态模式** (`SessionList.tsx:55-66,88-104`): 使用 `role="status"`/`aria-live`、明确 loading/error/empty/retry、44px 触控按钮。Agent 页面必须覆盖 `idle/running/waiting/reconnecting/partial/completed/retryable-failed/terminal-failed`，且 partial 明列未计入项。

### 10. Route 与 Layout 集成

**Route replacement** (`frontend/src/App.tsx:42-50`):

```tsx
<Route element={<RequireAuthentication />}>
  <Route path="/app">
    <Route index element={<Navigate replace to="me" />} />
    <Route element={<AppShell />}>
      <Route path="analyze" element={<PlaceholderTabPage title="分析" />} />
```

Phase 2 只替换 `analyze` element，并把 `/app` index 改到 `analyze`；仍在 `RequireAuthentication` 与同一个 `AppShell` 下，不新建第二套 H5 shell。

**唯一滚动区** (`frontend/src/layouts/AppShell.tsx:11-25`):

```tsx
<MobileFrame>
  <a href="#main-content" className="sr-only ...">跳到主要内容</a>
  <PageScrollArea contentId="main-content"><Outlet /></PageScrollArea>
  <BottomNavigation />
</MobileFrame>
```

AnalyzePage 不得再造固定底栏、外层滚动容器或路由级 QueryClient。全局 QueryClient 已由 `frontend/src/main.tsx:17-25` 提供。

### 11. 前端测试与跨栈验收

**Component harness** (`frontend/src/app/AppPages.test.tsx:15-31,70-95`):

```tsx
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
})
render(
  <QueryClientProvider client={queryClient}>
    <AuthContext.Provider value={createAuthValue({ request })}>
      <SessionsDetailsPage />
    </AuthContext.Provider>
  </QueryClientProvider>,
)
```

复制 Provider harness 和 role-based assertions；Phase 2 增加 MSW 时要让它模拟公开 HTTP/SSE 契约，不能直接注入最终组件状态。现仓库没有 MSW handler 类比，这是新增测试基础设施。

**真实用户路径** (`frontend/tests/e2e/auth-skeleton.spec.ts:22-41`):

```typescript
test('uses public APIs ...', async ({ browser, page, request }) => {
  await page.goto('/')
  await registerAndActivate(page, request, account)
  await login(page, account, '/app/me/sessions')
  await page.reload()
  ...
})
```

Agent E2E 必须复用真实注册/登录帮助器，从 `/app/analyze` 输入餐食，经公开 API 完成 interrupt/resume；另测刷新/断流后 snapshot 恢复、partial、可重试失败和跨用户不可见。不得直接写数据库或伪造 token。

## Shared Patterns

### Authentication and Ownership

- 身份：`AuthenticationService.authenticated_session()` 验证 access token、会话与权威 PostgreSQL 状态。
- 所有权：Agent Repository 以 `(thread_id, user_id)` 过滤；任何 Checkpoint/snapshot/events/resume 前执行。
- 不存在与越权使用同一安全错误语义；`thread_id` 从来不是凭证。

### Error Handling

- API 只返回 `{error: {code, message, request_id, retry_after?}}`。
- Provider body、堆栈、完整 Pydantic errors、State、思维链不进响应。
- 领域稳定错误由 route 映射；未处理异常交给 `main.py` 全局 500 envelope。

### Transactions and Idempotency

- Repository `flush()`，Service `commit()/rollback()`。
- client command key 绑定 canonical body hash；同 key/同 hash 返回既有 run，同 key/异 hash 为 409。
- Provider/tool invocation 以 run/node/item/input/version/request hash 去重；Checkpoint 本身不提供外部调用 exactly-once。

### Runtime Validation Boundaries

- API Schema、Provider DTO、tool DTO、LangGraph State/event DTO 分开验证。
- ORM 约束是最后防线，不替代 Pydantic/Service 规则。
- React 端类型不是运行时验证；公开 snapshot/event payload 需在 feature API/stream 边界校验。

### Documentation Contract

新增 `agent/`、`nutrition/`、`providers/reasoning/`、`features/agent/`、脚本和测试目录时，同批新增各自 README（职责/允许依赖/文件索引），并同步直接父级索引。Phase 2 另需 `docs/learning/phase-02-agent-core.md` 中文教学文档；这些是实施伴随项，不是可推迟清理。

## No Analog Found

| File/Module | Role | Data Flow | Required New Pattern |
|---|---|---|---|
| `backend/app/agent/state.py`、graph/node/routing files | state/graph | interrupt/resume | LangGraph v2、主图+餐食子图、JSON-safe State、可重入 interrupt、预算条件边；按 AI-SPEC/RESEARCH 实现 |
| `backend/app/agent/events.py` 与持久 event stream | schema/pub-sub | append/replay/tail | PostgreSQL event log + safe event allowlist；SSE 只读事件，不执行或取消 graph |
| `frontend/src/features/agent/stream/*` | hook/utility | authenticated streaming | `fetch()` + `eventsource-parser`、snapshot-first、seq gap recovery、401 单次 refresh/replay |
| `backend/scripts/nutrition_catalog/*` | importer | file-I/O + batch | FDC 离线 manifest/hash/license/version/qualification；null 不得转 0，运行时不调用 FDC |

## Mismatches Planner Must Not Hide

1. `backend/app/main.py` 目前没有 lifespan/supervisor；这是实质性新生命周期，不是简单 `include_router`。
2. 现有 Provider analog 是同步 SMTP；DeepSeek 的 async、schema validation、费用账本和未知调用结果都需新实现。
3. 现有 TanStack Query 只处理有限 JSON 请求；无限 SSE 必须独立 hook，不能塞入 query function。
4. 现有测试没有 MSW 或 LangGraph/Checkpointer fixture；两者是新增基础设施，真实 Checkpointer 不能靠 `db_session` rollback 清理。
5. 研究提出的 PostgreSQL lease/supervisor/event-log 属于 `[ASSUMED]` 架构建议；规划必须把并发、崩溃窗口和清理测试写成验证门，不能当已证明行为。
6. AI-SPEC 的 `deepseek-chat` 示例已被 RESEARCH 判定过期；实施默认必须使用经再次合法性核验的 `deepseek-v4-flash` 配置。

## Metadata

**Analog search scope:** `backend/app/{auth,admin,accounts,notifications,core}`、`backend/migrations`、`backend/tests`、`frontend/src/{auth,app,layouts,components}`、`frontend/tests/e2e`
**Concrete source files read:** 27
**Pattern extraction date:** 2026-08-28
**Out of scope ignored:** 图片/Qwen-VL、餐食确认保存/Mem0、真实饮食规划、后台目录维护
