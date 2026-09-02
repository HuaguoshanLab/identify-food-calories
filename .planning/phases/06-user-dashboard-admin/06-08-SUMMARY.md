---
phase: 06-user-dashboard-admin
plan: 08
subsystem: testing
tags: [python, offline-evaluation, fixture-loader, privacy]
requires:
  - phase: 06-07
    provides: Weekly-review facts and cache version vocabulary used by the frozen synthetic cases.
provides:
  - A strictly validated, de-identified 14-case weekly-review fixture catalog.
  - A zero-dependency loader that rejects malformed or sensitive fixture data before tests reach graph or provider code.
affects: [06-23, weekly-review-graph, provider-evaluation]
tech-stack:
  added: []
  patterns: [versioned offline fixture catalog, recursive sensitive-field denylist, exact-shape loader]
key-files:
  created:
    - backend/tests/evals/fixtures/weekly_review/weekly_review_cases.v1.json
    - backend/tests/evals/fixtures/weekly_review/loader.py
    - backend/tests/evals/fixtures/weekly_review/README.md
  modified:
    - backend/tests/README.md
key-decisions:
  - "Catalog v1 keeps only aggregate synthetic facts and scripted safe outcomes; it never stores raw Provider payloads or real sensitive probes."
  - "The loader validates the exact frozen ID set, field whitelist, version and call-count invariants before returning fixtures."
patterns-established:
  - "Offline eval fixtures are versioned JSON plus a standard-library loader, not test data copied from runtime ledgers."
  - "Privacy-contamination scenarios declare a stable rejection expectation without embedding prohibited personal data in the catalog."
requirements-completed: [UI-02]
duration: 8min
completed: 2026-09-02
---

# Phase 06 Plan 08: Weekly Review Fixture Catalog Summary

**冻结了可重放的 14 例周复盘合成数据集，并在 graph/provider 前以严格 loader 阻断敏感字段、未知形状和不合法调用预期。**

## Performance

- **Duration:** 8 min
- **Started:** 2026-09-02T11:10:54Z
- **Completed:** 2026-09-02T11:18:58Z
- **Tasks:** 1
- **Files modified:** 6

## Accomplishments

- 新增 `weekly-review-fixtures.v1` catalog，显式冻结 AI-SPEC 要求的 case-01 至 case-14。
- 新增纯标准库 loader，强制格式/版本、完整 14-case 集、递归敏感字段拒绝、字段白名单、facts/config/脚本/ledger 调用数一致性。
- 新建并索引 `tests/evals/fixtures/weekly_review/` 文档层级，写明允许依赖、14-case 索引与禁存边界。

## Task Commits

1. **Task 1: 创建 14-case 冻结合成 fixture、loader 与目录索引** - `65ad3b3` (feat)

## Files Created/Modified

- `backend/tests/evals/fixtures/weekly_review/weekly_review_cases.v1.json` - 14 个去标识化 facts/config/Fake 脚本/稳定预期/最小 ledger 案例。
- `backend/tests/evals/fixtures/weekly_review/loader.py` - 严格、无网络的 catalog loader 与 `--validate` CLI。
- `backend/tests/evals/README.md` - 离线评测目录职责和敏感数据边界。
- `backend/tests/evals/fixtures/README.md` - fixture catalog 边界与消费规则。
- `backend/tests/evals/fixtures/weekly_review/README.md` - catalog v1、14-case 索引与格式合同。
- `backend/tests/README.md` - 索引新的 `evals/`，并补齐既有 `agent/` 直接子目录索引。

## Decisions Made

- 隐私污染案例只保存 `SENSITIVE_FIELD` 的稳定拒绝预期；真实敏感值由后续测试在内存中注入，避免 fixture 本身变成泄露载体。
- loader 使用精确白名单而非宽松反序列化，保证版本漂移、额外字段、重复 ID 和超限调用数均在进入 graph/provider 前失败。

## Verification

- `cd backend && uv run python tests/evals/fixtures/weekly_review/loader.py --validate tests/evals/fixtures/weekly_review/weekly_review_cases.v1.json` — PASS（14 frozen cases）。
- loader 负向验证 — PASS（重复 ID、敏感 `email` 字段、未知 facts 字段均被拒绝）。
- `cd backend && uv run ruff check tests/evals/fixtures/weekly_review/loader.py` — PASS。
- `cd backend && uv run pytest tests/architecture/test_directory_contract.py -q` — PASS（2 passed）。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] 补齐既有 `tests/agent/` 父索引**
- **Found during:** Task 1（目录合同验证）。
- **Issue:** `tests/agent/` 已存在，但 `backend/tests/README.md` 未列出它，导致新增 eval 目录无法通过项目的直接父索引强制合同。
- **Fix:** 在同一父 README 增加 `agent/` 索引行。
- **Files modified:** `backend/tests/README.md`。
- **Verification:** `tests/architecture/test_directory_contract.py` 通过。
- **Committed in:** `65ad3b3`。

---

**Total deviations:** 1 auto-fixed（Rule 2: 1）。
**Impact on plan:** 仅修复同一父索引的既有合同缺口；不扩大功能范围。

## Issues Encountered

- sandbox 初次阻止 `uv` 访问全局缓存和 Git 创建 index lock；在获得受控权限后，原计划验证与逐文件原子提交均完成。

## User Setup Required

None - 不新增依赖、环境变量或外部服务。

## Next Phase Readiness

- 06-23 可直接通过 `load_catalog()` 消费同一 14-case 冻结资料，并将 Fake Provider 行为与 `expected`/`ledger` metadata 比对。
- 不存在已知 stub 或新增网络/认证/文件访问威胁面。

## Self-Check: PASSED

- 所有声明的新 catalog、loader 和三级 README 均存在。
- Task commit `65ad3b3` 可在 Git 历史中找到。

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-02*
