# Phase 1 Research: 工程、身份与权限基座

**Researched:** 2026-08-27  
**Status:** Ready for planning  
**Scope:** React/Vite + FastAPI + PostgreSQL + authentication + RBAC + teaching artifacts

## Executive Summary

Phase 1 should be a secure vertical slice, not a collection of disconnected scaffolds. The slice is: a user registers in React, FastAPI validates and hashes the password, PostgreSQL persists the user, the user logs in, receives an in-memory access token plus a rotating refresh-token cookie, can call a protected endpoint, list/revoke sessions, and is denied an admin endpoint unless the database role is `admin`.

Keep the backend as a modular monolith. Use synchronous SQLAlchemy 2.x with Psycopg 3 for this phase unless an actual concurrency measurement later justifies async conversion. The existing scaffold is already synchronous, FastAPI safely runs normal `def` dependencies in its thread pool, and authentication is mostly short database transactions plus CPU-bound Argon2 work. Introducing async now increases teaching and test complexity without improving the product outcome. Do not mix sync and async SQLAlchemy styles.

The hardest part is refresh-token rotation. Treat it as a transactional security protocol, not a JWT helper function. A consumed token must be replaced exactly once; reuse of an old token revokes the entire token family. The database is the source of truth for session validity.

## Recommended Stack

| Concern | Recommendation | Rationale |
|---|---|---|
| Python | Python 3.11+ with the existing `<3.13` guard initially | Installed locally; stable typing and library support |
| HTTP API | FastAPI, `/api/v1` prefix | Typed contracts and dependency-based auth/RBAC |
| Validation | Pydantic v2 + `pydantic-settings` | Separate request/response schemas from ORM models |
| ORM | SQLAlchemy 2.x typed declarative mappings | Explicit 2.0 query/session style; no legacy `Query` API |
| PostgreSQL driver | `psycopg[binary]` 3.x | Matches existing sync scaffold and real-PostgreSQL tests |
| Migrations | Alembic | Schema history must rebuild an empty database; review generated migrations manually |
| Password hashing | `pwdlib[argon2]` using its recommended Argon2 hasher | FastAPI's current security guide recommends Argon2 through pwdlib |
| Access token | `PyJWT` or equivalent narrow JOSE implementation | Signed short-lived bearer token; keep claims minimal |
| Refresh token | 256-bit opaque random value from `secrets`, not a second JWT | Easy server-side hashing, rotation, revocation, and replay detection |
| IDs | PostgreSQL UUID, generated application-side with UUIDv4 | Non-sequential public identifiers; future Agent ownership key |
| Frontend | React + TypeScript + Vite + React Router + TanStack Query | Clear server-state lifecycle and protected-route UX |
| Forms | React Hook Form + Zod | Shared client validation ergonomics; backend remains authoritative |
| Backend tests | pytest + HTTPX/TestClient + real PostgreSQL | Unit, repository/migration, API contract layers |
| Frontend tests | Vitest + Testing Library; Playwright smoke flow | Component behavior plus one browser-level auth journey |

Do not hardcode exact future package versions in plans. Keep the existing exact pins only after installing the missing auth/test packages and verifying the full suite. SQLAlchemy 2.1 is currently a newer line; staying on the already pinned 2.0 line avoids an unnecessary migration during Phase 1.

## Backend Module Boundaries

Recommended package shape:

```text
backend/app/
  main.py
  api/v1/router.py
  api/v1/auth.py
  api/v1/users.py
  api/v1/admin.py
  core/config.py
  core/database.py
  core/security.py
  domain/auth/entities.py
  domain/auth/errors.py
  application/auth/service.py
  application/auth/ports.py
  infrastructure/auth/models.py
  infrastructure/auth/repository.py
  schemas/auth.py
  cli/create_admin.py
```

The dependency direction is API → application service → repository port → SQLAlchemy adapter. FastAPI dependencies assemble these objects. Repository methods perform persistence operations but do not decide password policy or HTTP status codes. Services own registration, authentication, token rotation, logout, session revocation, and role checks. API routes translate domain/application errors into a stable error schema.

Use one request-scoped SQLAlchemy `Session`. The application service owns transaction boundaries for multi-step operations. Repository methods may `flush()` to obtain IDs, but should not independently `commit()`. This is especially important for refresh rotation, which must consume the old row and insert the successor atomically.

## Authentication Protocol

### Registration

1. Normalize email by trimming surrounding whitespace and applying a documented lowercase policy.
2. Validate password length using Unicode character count; do not silently truncate.
3. Query by normalized email and also enforce a database unique constraint.
4. Hash with Argon2 outside any needlessly long database lock.
5. Insert role=`user` with `email_verified_at=NULL`; the public schema must not contain a role field.
6. Generate a 6-digit email challenge, store only its digest, and send it through `MailProvider`.
7. Activate the account only after `/register/verify` consumes the current unexpired challenge.
8. Map duplicate registration, resend, and invalid login to non-enumerating responses.

Verification challenges expire after 10 minutes, allow at most 5 failed attempts, enforce a 60-second resend cooldown, and are single-use. Issuing a new challenge invalidates the previous one. Local Compose uses the official fixed-version `axllent/mailpit` image on SMTP 1025 and UI 8025; production remains provider-neutral.

### Login

1. Always execute one password verification path. For an unknown email, verify against a fixed dummy Argon2 hash to reduce timing differences.
2. On success, create a session/token family row and a first refresh-token row.
3. Return the short-lived access token in JSON; set the opaque refresh token as a cookie.
4. The React app stores the access token only in runtime memory. A full reload calls refresh once to reconstruct the authenticated session.

### Refresh rotation and replay handling

Use tables equivalent to:

- `users`: `id`, `email_normalized`, `password_hash`, `role`, `is_active`, timestamps.
- `auth_sessions`: `id`, `user_id`, `family_id`, `created_at`, `last_seen_at`, `expires_at`, `revoked_at`, optional safe device metadata.
- `refresh_tokens`: `id`, `session_id`, `token_hash`, `issued_at`, `expires_at`, `consumed_at`, `replaced_by_id`, `revoked_at`.

Store `SHA-256(server_pepper || raw_refresh_token)` or an HMAC digest, never the raw token. A high-entropy random token does not need slow password hashing. Keep the pepper outside the database.

Rotation transaction:

1. Hash the presented cookie and lock the matching token/session row (`SELECT ... FOR UPDATE`).
2. If current, unexpired, unrevoked, and unconsumed: set `consumed_at`, insert successor, link `replaced_by_id`, update session activity, commit, then emit the new cookie.
3. If the digest matches a consumed token: revoke the session/family and all active tokens, clear the cookie, return the uniform unauthenticated error.
4. If unknown or expired: do not reveal which condition occurred; clear the cookie and return unauthenticated.
5. Concurrent refresh requests must not both succeed. A locking/integration test must prove one winner and family revocation or deterministic failure for the loser.

Access-token claims should contain `sub`, `role`, `iat`, `exp`, `jti`, and optionally issuer/audience. Do not place email, preferences, or sensitive profile data in the token. Protected requests must still reject inactive users. Role claims improve fast routing but the backend database remains authoritative for high-value operations.

### Cookie and CSRF boundary

Use `HttpOnly`, `Path=/api/v1/auth`, `SameSite=Lax` by default, and `Secure=true` outside local HTTP development. Restrict CORS to explicit frontend origins and allow credentials only for those origins. Because refresh and logout mutate cookie-authenticated state, also validate `Origin`/`Referer` against the configured frontend origin; do not use wildcard CORS. The access token is a bearer header and is not automatically attached cross-site.

### Session management

Expose routes equivalent to:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/sessions`
- `DELETE /api/v1/auth/sessions/{session_id}`
- `GET /api/v1/users/me`
- `GET /api/v1/admin/probe`

Revocation must be user-scoped. A user cannot enumerate or revoke another user's sessions. The CLI admin creation path may promote/create an admin explicitly; public registration never accepts role input.

## Frontend Session Design

Create one auth boundary/provider responsible for the in-memory access token, current user, bootstrap refresh, login, registration, logout, and a single refresh-and-retry on 401. Prevent refresh storms by sharing one in-flight refresh promise. Never write the access or refresh token to localStorage, sessionStorage, IndexedDB, URLs, logs, or error monitoring.

Routes for Phase 1:

- `/register` and `/login`: public-only forms.
- `/app`: minimal authenticated landing page with current email/role and session management.
- `/admin`: minimal route that calls the admin probe; frontend hiding is UX only.

The client may pre-check password/email for usability, but server errors are authoritative. Use a stable API error envelope such as `{ "error": { "code", "message", "request_id" } }` so UI behavior does not depend on ad-hoc detail strings.

## Existing Scaffold Audit

| File | Verdict | Required change |
|---|---|---|
| `backend/pyproject.toml` | Reuse baseline | Update old calorie-demo description; add pwdlib Argon2, JWT, email validation, coverage/type/lint and API-test dependencies; verify pins together |
| `backend/app/core/config.py` | Reuse concept | Preserve fail-closed test DB guard; add secrets, issuer/audience, lifetimes, cookie/origin settings; reject insecure production defaults |
| `backend/app/core/database.py` | Refactor, do not discard | Keep sync SQLAlchemy and request-scoped session; create engine/sessionmaker once, not on every dependency call; add explicit transaction convention |
| `backend/tests/conftest.py` | Reuse guard pattern | Ensure Alembic receives `TEST_DATABASE_URL`; add per-test rollback/savepoint verification and API dependency override |
| `backend/tests/unit/test_test_database_guards.py` | Reuse | Keep as fast safety evidence; add tests for production secret/cookie configuration |

The scaffold is incomplete product code and must not be counted as delivered until migrated, tested, and documented. Its strongest reusable idea is refusing SQLite and the development database during repository tests.

## Directory Documentation Contract

The repository must be self-describing at every directory boundary. Phase 1 must create the root `README.md`, `frontend/README.md`, `frontend/AGENTS.md`, `backend/README.md`, and `backend/AGENTS.md`. Every new source, test, migration, or documentation directory created by an execution task must receive its own `README.md` in that same task and commit. Each directory README has three mandatory sections: `职责`, `允许依赖`, and `文件索引`. The file index is maintained when files are added, moved, or removed.

Root documentation explains full-stack orchestration and global rules. Frontend documentation may only depend on public API contracts and frontend libraries; backend documentation owns HTTP, application, persistence, security, and Agent boundaries. Child `AGENTS.md` files may add local rules but may never weaken root security, testing, or directory-documentation rules.

## Package Legitimacy Audit

Package names below were checked against their official PyPI/npm registry entries or official project installation documentation on 2026-08-27. `[VERIFIED]` means the name and source are legitimate; it does not waive lockfile review, vulnerability scanning, or compatibility tests during installation.

| Package / install name | Registry or official source | Status | Intended use |
|---|---|---|---|
| `fastapi`, `uvicorn[standard]` | PyPI / FastAPI official docs | [VERIFIED] | API runtime |
| `sqlalchemy`, `alembic`, `psycopg[binary]` | PyPI / SQLAlchemy and Alembic official docs | [VERIFIED] | ORM, migrations, PostgreSQL driver |
| `pydantic-settings`, `email-validator` | PyPI | [VERIFIED] | settings and normalized email validation |
| `pwdlib[argon2]` | PyPI; also used by current FastAPI security guide | [VERIFIED] | Argon2 password hashing |
| `PyJWT` | PyPI / project repository | [VERIFIED] | short-lived access-token signing and validation |
| `pytest`, `httpx`, `pytest-cov`, `ruff`, `mypy` | PyPI / respective official projects | [VERIFIED] | backend test, coverage, lint, typing |
| `react`, `react-dom` | npm / React official project | [VERIFIED] | UI runtime |
| `react-router-dom` | npm / React Router official docs | [VERIFIED] | client routing |
| `@tanstack/react-query` | npm / TanStack official docs | [VERIFIED] | server-state and auth request orchestration |
| `react-hook-form`, `zod`, `@hookform/resolvers` | npm / respective official projects | [VERIFIED] | forms and client validation |
| `vite`, `typescript`, `@vitejs/plugin-react` | npm / Vite official docs | [VERIFIED] | frontend build and typing |
| `tailwindcss`, `@tailwindcss/vite`, `shadcn`, `@base-ui/react`, `lucide-react` | npm / Tailwind, shadcn, Base UI and Lucide official docs | [VERIFIED] | verified UI-SPEC implementation |
| `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `msw` | npm / respective official projects | [VERIFIED] | frontend unit/component/API mocking tests |
| `@playwright/test` | npm / Playwright official docs | [VERIFIED] | browser E2E |
| `eslint`, `typescript-eslint`, `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh` | npm / ESLint and React official tooling | [VERIFIED] | frontend static checks |
| `axllent/mailpit` Docker image | Mailpit official documentation and Docker Hub | [VERIFIED] | local SMTP capture and verification-email E2E |

Do not install similarly named boilerplate packages or third-party shadcn registries. Initialize the frontend from the official Vite path and add only the audited packages. The executor must inspect generated manifests/lockfiles before committing.

## Threat Model

| Threat | Severity | Required mitigation/evidence |
|---|---|---|
| Stolen database exposes passwords | High | Argon2 hashes only; response/schema/log exclusion tests |
| Stolen refresh token remains reusable | High | Hash at rest, rotation, expiry, server-side revocation |
| Old token replay creates parallel session | High | Family revocation and concurrent refresh integration test |
| Public user self-assigns admin | High | No role in public schema; DB default and service constant; API test |
| Frontend-only admin guard bypass | High | Backend RBAC dependency and stable 403 contract |
| CSRF on refresh/logout | High | SameSite cookie, exact CORS, allowed-Origin validation |
| User enumeration | Medium | Uniform login/registration recovery messaging and timing path |
| Secrets committed or insecure production config | High | `.env.example` placeholders, fail-fast production validators, secret scanning in later CI |
| Session fixation | Medium | New session family on login; rotate refresh token every use |
| Logging credentials/tokens | High | Structured redaction and tests/assertions around error output |

No high-severity item may be deferred within Phase 1 because all are intrinsic to the auth goal.

## Testing Strategy

### Fast unit tests

- Password hashing/verification and dummy-hash behavior.
- Access-token claim validation, expiration, issuer/audience, malformed input.
- Auth service with fake repositories: registration, login, inactive user, rotation, replay revocation, logout, role policy.
- Settings fail-closed behavior.

### Real PostgreSQL integration tests

- Alembic upgrades an empty test database to head and can downgrade/upgrade the Phase 1 revision where safe.
- Unique normalized email constraint.
- Repository CRUD and transaction rollback.
- Token digest uniqueness, foreign keys, expiry/revocation queries.
- Two concurrent refresh attempts cannot both mint valid successors.
- User/session ownership filters cannot cross accounts.

### API contract tests

- Status codes and stable error envelope for every auth route.
- Cookie name/path/HttpOnly/SameSite/Secure-by-environment/max-age attributes.
- No password hash or raw refresh token in JSON/OpenAPI schemas.
- `/users/me`, session listing/revocation, inactive-user rejection.
- Ordinary user gets 403 for `/admin/probe`; admin gets 200.
- CORS preflight and disallowed Origin behavior.

### Frontend tests

- Form validation and server-error mapping.
- Bootstrap refresh, authenticated redirect, logout, session revocation.
- Single-flight refresh on simultaneous 401 responses.
- No storage API receives token values.
- Playwright smoke: register → login/app → protected fetch → logout → protected denial.

## Validation Architecture

| Layer | Command/evidence | Gate |
|---|---|---|
| Backend static | Ruff format/check plus a Python type checker configured in `pyproject.toml` | No lint/type errors |
| Backend unit | `pytest tests/unit` | All pass without PostgreSQL |
| Migration/repository | Docker PostgreSQL + `alembic upgrade head` + integration tests | No SQLite/fallback; empty DB rebuilds |
| API contract | HTTPX/TestClient auth and RBAC suite | Rotation, replay, cookies, 401/403 proven |
| Frontend static | TypeScript build and ESLint | No type/lint errors |
| Frontend behavior | Vitest/Testing Library | Auth state and forms pass |
| End-to-end | Playwright against running frontend/backend/PostgreSQL | One real auth journey passes |
| Documentation | README command smoke test and learning-doc checklist | A frontend developer can explain/request trace the flow |

Verification must run against isolated configuration. A missing `TEST_DATABASE_URL`, a non-`_test` database, SQLite, or a test URL equal to the development URL is a hard failure.

## Teaching Deliverable

`docs/learning/01-auth-and-backend-foundation.md` should teach through one concrete request trace:

1. React login submit and browser cookie behavior.
2. FastAPI route/dependency/schema mapping.
3. Service orchestration and why it owns the transaction.
4. Repository/SQLAlchemy query and PostgreSQL constraints.
5. Argon2 versus refresh-token hashing.
6. Access token versus refresh token lifecycle, including a replay timeline.
7. RBAC enforcement and why hiding UI is insufficient.
8. Unit versus repository versus API versus E2E tests.
9. Debug recipes: inspect OpenAPI, migration state, cookies, CORS, and failed DB guards.

Use sequence diagrams and short code excerpts linked to real project files. Do not duplicate the implementation or translate every Python line.

## Planning Implications

Recommended vertical plan split:

1. Engineering skeleton and real PostgreSQL migration path.
2. User/password/RBAC vertical slice.
3. Session family, refresh rotation, replay revocation, and API contracts.
4. React auth experience and protected/admin probes.
5. Learning documentation, end-to-end smoke, and final security evidence.

Plans 2 and 3 should be test-first at the service/protocol level even though global GSD TDD mode is disabled. The database concurrency test must precede declaring refresh rotation complete. Every plan must include its own threat model block because project security enforcement is enabled.

## Primary References

- FastAPI, OAuth2/JWT and password hashing: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
- SQLAlchemy asyncio/session guidance (used mainly to justify not sharing sessions and avoiding needless async complexity): https://docs.sqlalchemy.org/en/20/orm/session_basics.html
- SQLAlchemy 2.x migration style: https://docs.sqlalchemy.org/en/20/changelog/migration_20.html
- Alembic documentation and autogenerate caveats: https://alembic.sqlalchemy.org/en/latest/
- OWASP Authentication Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- OWASP JSON Web Token Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html

---

## RESEARCH COMPLETE
