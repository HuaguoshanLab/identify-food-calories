# Phase 1 Source Coverage Audit

**Phase:** 1 — 受控数据与可运行薄切片  
**Audit status:** complete; no source item is silently omitted.

## Authoritative Requirement Coverage

| Source item | Planned in | Delivery evidence |
|---|---|---|
| ARCH-01, ARCH-06 | 01-01 | independent `frontend/` and `backend/`, Compose PostgreSQL healthcheck, documented separate terminals |
| ARCH-03, ARCH-04, DATA-01 | 01-02 | SQLAlchemy 2 models, Alembic-only DDL, versioned catalog manifest, real PostgreSQL tests |
| DATA-04 | 01-02 | transaction-validating seed and production `release_preflight` gate |
| CAL-01 | 01-03 | one backend `CalculationService` formula and fake-repository unit tests |
| ARCH-05 | 01-03 | `/api/v1` schemas, OpenAPI contract test, safe error envelope |
| ARCH-02 | 01-04 | React/TypeScript/Vite client calling the published REST API through TanStack Query |

## Goal Coverage

| Roadmap success truth | Planned in |
|---|---|
| Developer can run Compose PostgreSQL plus independently started frontend/backend and make a real REST request | 01-01, 01-03, 01-04 |
| Empty PostgreSQL can recreate catalog schema and query approximately 100 stable dish IDs | 01-02 |
| Provenance, commercial-use reference, derivation chain, and release eligibility are enforced | 01-02 |
| A supported dish plus grams receives deterministic database-derived kcal; model kcal is never accepted | 01-03, 01-04 |

## Locked-Decision Coverage

| Decisions | Planned in |
|---|---|
| D-01–D-06 single-dish path, searchable aliases, default grams, explicit calculation, result scope, API-only provenance | 01-04 |
| D-07–D-12 15-first then approximately-100 catalog, standard recipe relation, version/provenance/release gate | 01-02 |
| D-13–D-18 `/api/v1`, strict API→Service→Repository→Model boundary and layered tests | 01-03 |
| D-19–D-20 concise runnable documentation, curl samples and flow diagram | 01-04 |
| D-21–D-27 Compose scope, explicit migration/seed, env hygiene, ports, narrow CORS, separate terminals | 01-01, 01-03, 01-04 |

## Requested Execution-Control Index

The requester supplied DATA/CALC/API/ARCH/UX/TEST/OPS labels that are not requirement IDs in `REQUIREMENTS.md`. They are treated here as traceability controls, not invented product requirements.

| Control labels | Concrete plan coverage |
|---|---|
| DATA-01..06 | 01-02: stable ID/entity graph; aliases; data version; provenance/license/derivation; release status; 15-dish validation followed by approximately 100 manifest records and count test |
| CALC-01..05 | 01-03: `dishId` + bounded Decimal grams input; sole formula; fixed half-up rounding; DB eligibility check; safe domain errors and rejection of client nutrition/model fields |
| API-01..05 | 01-03: `/api/v1` + FastAPI docs; search; calculate; separate Pydantic DTO/error envelope; OpenAPI snapshot and restrictive CORS tests |
| ARCH-01..08 | 01-01..01-04: independent projects; approved React/Vite and FastAPI/SQLAlchemy stack; Compose PostgreSQL; Alembic; strict layers; versioned REST; env boundaries; independently runnable developer workflow |
| UX-01..04 | 01-04: one single-dish path; Base UI searchable alias combobox; default/editable grams with explicit submit; specified loading/error/stale/accessibility states |
| TEST-01..05 | 01-02..01-04: fake-repository service unit tests; isolated PostgreSQL migration/repository/seed integration tests; API/schema/OpenAPI/CORS tests; Vitest/Testing Library component tests; Playwright plus end-of-phase manual check |
| OPS-01..05 | 01-01, 01-02, 01-04: DB-only Compose healthcheck; `.env.example`/ignored real env; explicit migration/seed; concise runbook/curl/flow; executable production preflight and all-suite verification |

## Research and Scope Fence Coverage

- The official shadcn Vite + Base UI CLI and registry are used in 01-01/01-04. `@headlessui/react` is explicitly excluded despite the stale research example.
- Package legitimacy has a blocking checkpoint before the flagged/missing-audit npm packages are installed in 01-01.
- Images, upload routes, model calls, multi-dish inputs, calorie intervals, saved analysis/history, corrections, account/auth, third-party storage, queues, and production deployment are absent by phase boundary; no plan task implements them. Their later security controls remain assigned to Phases 2–5.
- The old `.planning/research/STACK.md` recommendation for Next.js is superseded by `AGENTS.md`, `01-CONTEXT.md`, and the Phase 1 research/UI contract; it is not used.

## Pre-Mortem Checks

| Likely failure | Early plan guard |
|---|---|
| The 15-dish schema proof is mistaken for the finished catalog | 01-02 seed integration test asserts all D-08 dishes and an approximately-100 final count. |
| License columns exist but demo data can still ship | 01-02 production preflight tests inspect both manifest and database and require non-zero exit. |
| UI duplicates calculation or bypasses API layers | 01-03 API/service tests and 01-04 component/E2E tests assert backend-only kcal and explicit POST behavior. |
