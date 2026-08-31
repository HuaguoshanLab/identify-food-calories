# Phase 3: 多模态餐食分析闭环 - Pattern Map

**Purpose:** planner/executor map from Phase 3 responsibilities to closest existing code. This document is read-only guidance, not a second architecture contract.

## Backend

| Planned role | Closest analog | Required pattern |
| --- | --- | --- |
| Vision port, DTO, fake and factory | `backend/app/providers/reasoning/{ports,dto,fake,factory,deepseek}.py` | One Protocol; `extra="forbid"` Pydantic provider DTOs; fake records metadata without body; production factory fails closed; safe `ProviderCallError` kinds only. |
| Provider accounting and outcome unknown | `backend/app/providers/reasoning/deepseek.py` and `backend/app/agent/models.py:AgentInvocation` | Preserve request ID, usage and cost as safe metadata; never persist image/model body; record `outcome_unknown` and do not blind retry. |
| Image-related state | `backend/app/agent/state.py:MealAgentState` and `StateMealItem` | State stays JSON-safe and bounded; Provider DTO/ORM/http schema remain distinct; replace the Phase 2 empty `image_refs` sentinel with minimal safe references only. |
| Graph routing | `backend/app/agent/graph.py:MealAnalysisGraph` | Graph depends on provider and nutrition tool ports only; vision node returns observations, then catalog/calculation/validation remains deterministic. |
| Thread/run idempotency and cleanup | `backend/app/agent/service.py`, `models.py`, `repository.py`, `retention.py` | Service owns transaction and user scope; repository owns query/add/flush; durable request digest/command key precedes provider call; retention must cover every exit path. |
| API, multipart and SSE | `backend/app/agent/api.py`, `schemas.py` | Route validates HTTP and calls Service; ownership is always user-scoped; snapshots/events expose only safe summaries; use versioned OpenAPI schema. |
| Database migration | `backend/migrations/versions/0004_agent_core.py` and `0005_nutrition_catalog_content_hash.py` | Schema changes land in a new Alembic revision and are proven on isolated PostgreSQL; never create tables ad hoc in lifespan. |

## Frontend

| Planned role | Closest analog | Required pattern |
| --- | --- | --- |
| Analysis page state | `frontend/src/features/agent/components/AnalyzePage.tsx` | Extend the existing protected page rather than add a parallel page; one request owner from `useAuth`, thread in URL, safe status text, field-local errors. |
| SSE/reconnect | `frontend/src/features/agent/stream/useAgentEventStream.ts` | Fetch authoritative snapshot before events; use sequence IDs and stop client retry loops; never trust event payload as report truth. |
| Public contract | `frontend/src/features/agent/api/generate-contracts.mjs` and generated client/schema files | Change FastAPI first, regenerate generated artifacts, and test contract drift; do not hand-edit generated files. |
| H5 controls | `frontend/src/components/ui/` and `docs/ui/h5-foundation.md` | Existing shadcn Base UI and Lucide only; semantic tokens; one scroll root; visible labels, `aria-live`, 44px targets, no layout shifts. |

## Test Patterns

| Layer | Closest analog | Phase 3 application |
| --- | --- | --- |
| Provider/unit | `backend/tests/test_reasoning_provider.py` | Script vision success, schema invalid, transient, permanent and outcome-unknown outcomes; assert no image body enters trace. |
| Graph/API unit | `backend/tests/unit/test_agent_api_contract.py` | Assert multipart/error schemas, safe SSE payload and thread ownership without paid calls. |
| PostgreSQL integration | `backend/tests/integration/test_agent_vertical.py`, `test_agent_retention.py`, `test_agent_checkpoint.py` | Prove migration, deletion, resume, idempotency and no cross-user/duplicate invocation using isolated real PostgreSQL. |
| Browser | `frontend/tests/e2e/agent.spec.ts`, `h5-visual.spec.ts` | Use actual login + file chooser + public API; cover success, clarification, error/recovery and text fallback; never seed DB or browser token. |

## File-creation rule

Every new directory under `backend/app/providers/vision/`, image-processing modules, eval assets or frontend feature subdirectory must include its own `README.md` and update its direct parent index in the same commit.
