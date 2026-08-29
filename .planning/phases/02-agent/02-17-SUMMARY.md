---
phase: 02-agent
plan: 17
subsystem: evaluation
tags: [promptfoo, deepseek, expert-signoff, visual-baseline, release-gate]

requires:
  - phase: 02-agent
    provides: 24-case code evaluation, reviewer schema, Promptfoo release runner, and visual candidate
provides:
  - Hash-bound dual-expert signoff for all 24 cases
  - Bounded 36-call Judge evidence with safe cost accounting
  - Exact visual candidate approval evidence independent from the official baseline
affects: [02-18-release-report, phase-3]

tech-stack:
  added: []
  patterns:
    - Stable reviewer pseudonyms are bound to roles and case/hash records.
    - Paid Judge runs are serial, no-cache, zero-retry, first-failure-stop evidence.
    - Release evidence stores scores, usage, costs and contract hashes but no prompts, outputs, reasoning or keys.

key-files:
  created:
    - backend/evals/expert-signoff-phase2.json
    - backend/evals/promptfoo-release-phase2-v4.json
  modified:
    - backend/evals/run_promptfoo_release.py
    - backend/evals/promptfooconfig.yaml
    - backend/evals/README.md

key-decisions:
  - "于女士和陈先生使用稳定匿名代号，允许跨 case 审核但同一 case 同角色严格去重。"
  - "正式 Judge 采用 phase02-judge-json-thinking-disabled.v4：JSON object 模式与 DeepSeek thinking disabled 均在证据中绑定。"
  - "视觉批准只绑定 candidate SHA；official baseline 保持不变。"

patterns-established:
  - "Provider export parsing must validate target case, usage, strict score object and store only a safe structural summary on failure."
  - "每次付费运行保留独立工件，不能覆盖或合并此前轮次。"

requirements-completed: [AGT-06, AGT-07, ARC-06, QLT-02]
duration: multi-session
completed: 2026-08-29
---

# Phase 02 Plan 17: 人工发布门 Summary

**24-case 双专家签署、独立 36-call v4 Judge 和精确视觉 candidate 批准均已形成可审计证据，且官方视觉基线未被改写。**

## Performance

- **Duration:** multi-session
- **Completed:** 2026-08-29
- **Tasks:** 3/3 human gates
- **Files modified:** 8 key artifacts and contracts

## Accomplishments

- 于女士（yu-nutritionist）和陈先生（chen-food-data-admin）对全部 24 case 的五项确认已物化为 48 条 hash-bound review；五个 Medium case 的双方分数均为 5。
- v4 Judge 在 response_format: json_object 与 thinking.disabled 合同下完成 36/36 次串行调用，五个 Medium case 的稳定独立 Judge 分数均为 4，保守实际成本为 0.00451584 CNY。
- SHA-256 为 530b6bde4cb90cf7d8a99919c76317c58a34b598fa5ed764b7d8adc7f1d47562 的 430×932 visual candidate 已获用户批准；official baseline 仍为 fba54a9449177837dc6f2496d29e479ad26b3b7d0b707de52c2ca6018df2ab4a。

## Task Commits

1. **Task 1: 双角色专家签署合同** - b0e51d7, e7ead06
2. **Task 2: Promptfoo 12×3 正式 Judge 门** - a702f11, d8e2994, 8252201, e7ead06
3. **Task 3: 精确视觉 candidate 批准** - 222b104

## Verification

- validate-signoff passed against the frozen dataset and code-eval hashes.
- Promptfoo v4 evidence records 36 authorized/attempted/completed calls, maxConcurrency=1, no cache, zero retries, v4 prompt/config/transport hashes, usage-accounted cost and five stable scores.
- pytest (20), ruff, evaluation-contract validation and release failure fixtures passed.
- Candidate and official visual SHA-256 values were independently rechecked; no promotion occurred.

## Deviations from Plan

### Auto-fixed Issues

1. **[Rule 1 - Bug] Promptfoo export parsing and cost accounting were too coarse**
- **Found during:** Task 2
- **Fix:** Added safe export-shape diagnostics, target-case verification, strict score parsing and usage accounting even when score parsing fails.
- **Verification:** Synthetic nested/flat/object export fixtures and 20 unit tests.

2. **[Rule 2 - Critical contract] Ordinary text output did not guarantee a safe Judge score**
- **Found during:** Task 2
- **Fix:** Versioned JSON-only contracts through v2–v4, then bound OpenAI JSON object mode and DeepSeek thinking disablement via Promptfoo passthrough.
- **Verification:** Local Promptfoo 0.122.0 source-transfer test, no-network transport preflight and completed v4 evidence.

**Impact:** The additions are fail-closed evaluation and cost-accounting safeguards; they do not relax the 12×3 release contract.

## Next Phase Readiness

Plan 02-18 can consume the formal signoff, completed v4 Judge evidence and visual approval to generate the release report and complete the remaining browser/visual-promotion work.

## Self-Check: PASSED

- backend/evals/expert-signoff-phase2.json and backend/evals/promptfoo-release-phase2-v4.json exist and are committed in e7ead06.
- All three evidence gates are independently present: formal signoff, completed Judge evidence and exact visual approval.

---
*Phase: 02-agent*
*Completed: 2026-08-29*
