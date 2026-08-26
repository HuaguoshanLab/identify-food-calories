# Walking Skeleton — 中式外卖热量识别

**Phase:** 1  
**Generated:** 2026-08-26

## Capability Proven End-to-End

匿名用户可以搜索一项受支持菜品、确认或修改预填克数并点击计算，由 PostgreSQL 中的受控营养记录经 FastAPI 返回确定性单项热量。

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Frontend | React 19 + TypeScript + Vite, React Router, TanStack Query, Tailwind, shadcn Base UI | Locked by `AGENTS.md` and UI contract; independent client is intentional. |
| Backend | FastAPI + Pydantic + synchronous SQLAlchemy 2 + Alembic | Locked stack and explicit API→Service→Repository→Model learning boundary. |
| Database | One PostgreSQL instance via Docker Compose | Controlled catalog is the authoritative data source; real PostgreSQL is required in integration tests. |
| Auth | None | The product is anonymous; no account/session behavior exists in this phase. |
| Local run target | Docker PostgreSQL plus separately started backend on 8000 and frontend on 5173 | D-21–D-27 require observable, separate startup and logs. |
| Directory layout | `frontend/` and `backend/` independent projects; backend packages follow `api → services → repositories → models`, schemas separate | Prevents ORM/API leakage and formula drift. |

## Stack Touched in Phase 1

- [ ] Project scaffold, lint, formatting, test runners, and lockfiles
- [ ] One calculator route with an interactive Base UI combobox and submit button
- [ ] PostgreSQL migration, explicit controlled-data seed, real database search/read
- [ ] Browser-to-REST-to-database calculation path
- [ ] Documented local full-stack run and verification commands

## Out of Scope

- Image capture/upload, image validation/storage/deletion, and visual-model integration
- Multiple dishes, candidate recognition, grams estimation, calorie intervals, and model metadata
- User edits after analysis, anonymous analysis persistence, user history, accounts, and feedback
- Rate limiting/cost controls, external provider credentials, queues/workers, and production deployment

## Subsequent Slice Plan

- Phase 2: safe image upload and multi-dish recognition against this controlled catalog.
- Phase 3: corrections and reproducible anonymous analysis records.
- Phase 4: frozen-set recognition/weight/interval calibration.
- Phase 5: production protection and release gates.
