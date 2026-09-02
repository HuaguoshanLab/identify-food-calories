# Deferred Items

## Pre-existing Type Annotation Gap

- **Observed during:** 06-01 Task 2 validation
- **Location:** `backend/app/records/service.py:236-242`
- **Issue:** `uv run mypy app/records` reports four errors in the pre-existing `_validated_snapshot` dynamic dictionary flow.
- **Scope:** Unrelated to local-time attribution; the changed timezone code is not implicated in the reported lines.
- **Suggested follow-up:** Type the validated report-item structure in a dedicated maintenance task, then re-run `uv run mypy app/records`.
