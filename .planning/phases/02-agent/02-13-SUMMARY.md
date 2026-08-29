---
phase: 02-agent
plan: 13
subsystem: agent-runtime
tags: [deepseek, httpx, fastapi, phoenix, opentelemetry, tracing, supply-chain]
requires:
  - phase: 02-agent
    provides: ReasoningModelProvider port, bounded meal graph, deterministic nutrition tool port, and supervisor lifecycle
provides:
  - DeepSeek Responses adapter with bounded retry and unknown-outcome protection
  - Hash-locked FastAPI/Phoenix runtime with verified supply-chain evidence
  - Allowlist-only OpenTelemetry spans for actual agent, provider, and nutrition tool calls
affects: [agent-runtime-factory, production-configuration, evals, observability]
tech-stack:
  added: [arize-phoenix 18.1.0, arize-phoenix-otel 0.17.1, openinference-instrumentation-langchain 0.1.72]
  patterns: [runtime-only hash lock export, fail-closed provider configuration, allowlist telemetry wrapper]
key-files:
  created: [backend/app/providers/reasoning/deepseek.py, backend/app/core/tracing.py]
  modified: [backend/pyproject.toml, backend/requirements.lock, backend/app/agent/supervisor.py, backend/tests/unit/test_runtime_foundation.py]
key-decisions:
  - "FastAPI is pinned to 0.137.0 with versioned official registry evidence."
  - "Phoenix is pinned to 18.1.0 because 20.3.0 and 20.4.0 both fail actual Python 3.11 import."
  - "Telemetry accepts only stable metadata and HMAC-scoped thread fingerprints."
patterns-established:
  - "Provider transport uncertainty is terminal and requires an explicit user retry."
  - "Instrumentation wraps narrow ports and records no request or response payload."
requirements-completed: [AGT-05, AGT-06, AGT-07, ARC-06, QLT-02]
duration: 55min
completed: 2026-08-29
---

# Phase 02 Plan 13: 真实 Provider 与安全追踪 Summary

**以 HTTPX MockTransport 验证的 DeepSeek Responses adapter、可审计的 runtime 依赖锁，以及从真实 Agent 调用链产生的隐私安全 OTel spans。**

## Performance

- **Duration:** 55 min
- **Completed:** 2026-08-29T07:06:35Z
- **Tasks:** 3/3
- **Files modified:** 13（含用户授权的供应链证据门禁更新）

## Accomplishments

- 将 `httpx==0.28.1` 固定为唯一 runtime 直接依赖；DeepSeek adapter 只调用 `/responses`、关闭 thinking、强制 JSON Schema/20 秒/800 token，并对未知传输结果绝不重试。
- 用官方 PyPI registry 响应、发布者、仓库、许可证、发布时间与 SHA-256 更新 FastAPI 0.137.0 和 Phoenix 18.1.0 的可版本化证据；validator 与 hash lock 已复验。
- 建立不启动本地 UI 的 allowlist-only OTel runtime：真实 supervisor run、Mock DeepSeek provider 和三个确定性营养工具分别产生受控 span，并保留正确 parent links。

## Task Commits

1. **Task 1: 锁定 runtime 并实现 DeepSeek adapter**
   - `4a646fc` `test(02-13): add failing DeepSeek runtime contracts`
   - `ba11935` `feat(02-13): add bounded DeepSeek runtime adapter`
2. **Task 2: 建立 Phoenix allowlist processor 与 runtime**
   - `df272f6` `test(02-13): add failing tracing privacy contract`
   - `392b241` `feat(02-13): add allowlisted Phoenix tracing runtime`
3. **Task 3: 接线 lifecycle 并证明真实三类 spans**
   - `e3381f5` `test(02-13): add failing real tracing path contract`
   - `b96ec47` `feat(02-13): wire allowlisted spans into agent runtime`

## Verification

- `lock_dependencies.py check` passed; runtime-only hash closure installed in a clean Python 3.11 environment and imported HTTPX, Phoenix, OpenInference, and the adapter. `pytest` was absent as required.
- Actual `backend/.venv` was synced from the full hash lock and completed the same import/adapter smoke test.
- `tests/unit/test_runtime_foundation.py` passed; actual span test proves `agent.run`, `agent.provider`, and all three `nutrition.*` spans, parented beneath the run span, with forbidden meal text, identity, prompts, model output, and CoT absent.
- Isolated PostgreSQL regression: 172 passed, 7 pre-existing Starlette cookie deprecation warnings; Ruff and mypy passed.
- Frontend regression: ESLint, TypeScript, Vitest (93 tests), and production build passed. Vite reports its existing >500 kB chunk warning.

## Decisions Made

- Production must provide `DEEPSEEK_API_KEY`, model and price snapshot; incomplete production configuration fails closed. No real DeepSeek request was made.
- `arize-phoenix==20.3.0` and official candidate `20.4.0` both resolve but fail Python 3.11 `import phoenix` with Phoenix's mutable-default dataclass error. The project owner authorized `18.1.0` only after clean-environment install/import succeeded with FastAPI 0.137.0. The exact evidence and failure rationale live in `backend/supply-chain-evidence.json` and `backend/app/providers/reasoning/README.md`.
- The tracing runtime owns a private provider and exports only to an explicit collector. It neither launches a Phoenix UI nor mutates the global OTel provider.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Compatibility/security] FastAPI 0.128.8 could not satisfy Phoenix 20.3.0 metadata.**

- **Found during:** Task 1
- **Fix:** After explicit user approval, pinned FastAPI 0.137.0; regenerated the hash lock and added official registry evidence to the fail-closed validator.
- **Files modified:** `backend/pyproject.toml`, `backend/requirements.lock`, `backend/supply-chain-evidence.json`, `backend/validate_supply_chain.py`
- **Verification:** validator, lock gate, clean runtime installation, actual venv smoke, and regressions passed.
- **Committed in:** `ba11935`

**2. [Rule 3 - Blocking] Phoenix 20.3.0 cannot import on the supported Python 3.11 runtime.**

- **Found during:** Task 1
- **Fix:** Tested official 20.3.0 and 20.4.0 candidates in clean Python 3.11 environments; both fail at `import phoenix`. After explicit user authorization, selected and evidence-locked `arize-phoenix==18.1.0`, which installed and imported successfully with FastAPI 0.137.0.
- **Files modified:** `backend/pyproject.toml`, `backend/requirements.lock`, `backend/supply-chain-evidence.json`, `backend/app/providers/reasoning/README.md`
- **Verification:** clean candidate install/import, runtime-only lock install, actual venv smoke, and span tests passed.
- **Committed in:** `ba11935`

**Total deviations:** 2; both were necessary compatibility gates, explicitly user-authorized, and confined to the supply-chain/runtime boundary.

## Issues Encountered

- The all-backend command still has one pre-existing failing test: `tests/unit/test_agent_api_contract.py::test_all_agent_operations_require_authentication_and_return_one_sentinel`. It asserts an obsolete 501 placeholder contract while the current route creates a real Agent thread and fails its foreign key because the test injects a nonexistent user. It is outside this plan's strictly allowed files and was not changed. After preparing the isolated `food_agent_test` database with the repository guard, every other backend test passed (172 passed).

## User Setup Required

- Keep `DEEPSEEK_API_KEY` only in the uncommitted server environment. For production, also set `REASONING_PROVIDER_MODE=deepseek`, `DEEPSEEK_MODEL=deepseek-v4-flash`, the versioned price snapshot values, and—only if tracing is enabled—the collector endpoint, HMAC key, service name and service version.

## Next Phase Readiness

- The provider and tracer can be injected into a production runtime factory without exposing payloads. The outstanding obsolete API contract test should be updated in the plan that owns the public Agent API contract; it should not be treated as a provider or dependency regression.

## Known Stubs

None. Optional transport/exporter constructor arguments are explicit testing seams, not runtime placeholders.

## Self-Check: PASSED

- Confirmed the adapter, tracing runtime, supervisor integration, lock file, and this summary exist.
- Confirmed all six RED/GREEN task commits are reachable in Git history.

*Phase: 02-agent*
*Completed: 2026-08-29*
