# Phase 1 Source Coverage Audit

**Phase:** 1 — 受控数据与可运行薄切片  
**Audit status:** complete; no source item is silently omitted.

## Authoritative Requirement Coverage

| Source item | Planned in | Delivery evidence |
|---|---|---|
| ARCH-01, ARCH-03, ARCH-06 | 01-01, 01-02, 01-09 | independent projects, Python 3.11, DB-only Compose, explicit `_test` DB and runnable separate terminals |
| ARCH-04, DATA-01 | 01-03, 01-04, 01-06 | SQLAlchemy/Alembic schema, governed manifest/seed, repository/service/search evidence |
| DATA-04 | 01-05, 01-09 | fake-repo and PostgreSQL production `release_preflight` gate plus CI/runbook invocation |
| CAL-01 | 01-06, 01-07 | single `CalculationService` formula and versioned API contract |
| ARCH-05 | 01-07 | `/api/v1`, OpenAPI D-06 fields, safe errors and narrow CORS contract |
| ARCH-02 | 01-02, 01-08 | React/TypeScript/Vite plus TanStack Query REST consumer |

## Goal Coverage

| Roadmap success truth | Planned in |
|---|---|
| Developer can run Compose PostgreSQL plus independently started frontend/backend and make a real REST request | 01-01, 01-02, 01-07, 01-08, 01-09 |
| Empty PostgreSQL can recreate catalog schema and query approximately 100 stable dish IDs | 01-03, 01-04, 01-06 |
| Provenance, commercial-use reference, derivation chain, and release eligibility are enforced | 01-04, 01-05, 01-07 |
| A supported dish plus grams receives deterministic database-derived kcal; model kcal is never accepted | 01-06, 01-07, 01-08 |

## Locked-Decision Coverage

| Decisions | Planned in |
|---|---|
| D-01–D-06 single-dish path, searchable aliases, default grams, explicit calculation, result scope, API returns governance but UI does not render it | 01-07, 01-08 |
| D-07–D-12 15-first then approximately-100 catalog, standard recipe relation, version/provenance/release gate | 01-03, 01-04, 01-05 |
| D-13–D-18 `/api/v1`, strict API→Service→Repository→Model boundary and layered tests | 01-06, 01-07 |
| D-19–D-20 concise runnable documentation, curl samples and flow diagram | 01-09 |
| D-21–D-27 Compose scope, explicit migration/seed, env hygiene, ports, narrow CORS, separate terminals | 01-01, 01-07, 01-09 |

## Requested Execution-Control Index

The requester supplied DATA/CALC/API/ARCH/UX/TEST/OPS labels that are not requirement IDs in `REQUIREMENTS.md`. They are treated here as traceability controls, not invented product requirements.

| Control labels | Concrete plan coverage |
|---|---|
| DATA-01..06 | 01-03..01-05: stable relation graph; aliases/version; provenance/license/derivation; status; 15 then approximately-100 demo-only seed; production gate |
| CALC-01..05 | 01-06..01-07: bounded `dishId`/Decimal grams; sole formula; half-up rounding; eligibility filtering; safe errors/forbidden client nutrition fields |
| API-01..05 | 01-07: `/api/v1`; search; calculate; Pydantic/error envelope; D-06 sourceReference/licenseStatus/dataVersion plus OpenAPI/CORS tests |
| ARCH-01..08 | 01-01..01-09: separate projects; approved stack; Compose; Alembic; strict layers; versioned REST; env/test DB boundaries; independently replayable workflow |
| UX-01..04 | 01-08: searchable Base UI aliases; defaults/local grams/explicit submit; stated loading/error/stale/accessibility and no governance UI |
| TEST-01..05 | 01-01, 01-03..01-09: fail-closed test setup; real PostgreSQL schema/repository/seed/preflight; fake service tests; API/OpenAPI/CORS; Vitest; Playwright/manual |
| OPS-01..05 | 01-01, 01-04, 01-05, 01-09: DB health/test creation, env rules, explicit migration/seed, runbook/curl/dataflow, local/CI preflight gate |

## Research and Scope Fence Coverage

- The official shadcn Vite + Base UI CLI and registry are used in 01-02/01-08. `@headlessui/react` is explicitly excluded despite the stale research example.
- Package legitimacy has a blocking checkpoint before the flagged/missing-audit npm packages are installed in 01-02.
- Images, upload routes, model calls, multi-dish inputs, calorie intervals, saved analysis/history, corrections, account/auth, third-party storage, queues, and production deployment are absent by phase boundary; no plan task implements them. Their later security controls remain assigned to Phases 2–5.
- The old `.planning/research/STACK.md` recommendation for Next.js is superseded by `AGENTS.md`, `01-CONTEXT.md`, and the Phase 1 research/UI contract; it is not used.

## Pre-Mortem Checks

| Likely failure | Early plan guard |
|---|---|
| The 15-dish schema proof is mistaken for the finished catalog | 01-04 seed integration test asserts all D-08 dishes and an approximately-100 final count. |
| License columns exist but demo data can still ship | 01-05 fake-repo and PostgreSQL preflight tests inspect both manifest and database and require non-zero exit. |
| UI duplicates calculation or bypasses API layers | 01-06/01-07 service/API tests and 01-08/01-09 component/E2E tests assert backend-only kcal and explicit POST behavior. |
