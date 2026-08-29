---
phase: 02-agent
plan: 18
subsystem: testing
tags: [release-evidence, promptfoo, playwright, visual-baseline, langgraph, postgres]
requires:
  - phase: 02-agent/17
    provides: real dual-role sign-off, v4 Judge evidence, and an approved visual candidate SHA
provides:
  - hash-bound fail-closed release report
  - user-approved official analysis visual baseline
  - real browser-driven Playwright evidence and Chinese architecture guide
affects: [phase-02-release, evaluation, h5-agent-ui]
tech-stack:
  added: []
  patterns: [isolated release evaluator, exact-SHA visual promotion, fail-closed Spearman gate]
key-files:
  created: [backend/evals/release_phase2.py, backend/evals/phase2-release.json, docs/learning/phase-02-agent-core.md]
  modified: [backend/evals/expert-signoff-phase2.json, frontend/tests/e2e/agent.spec.ts, frontend/tests/e2e/h5-visual.spec.ts-snapshots/analyze-430-chromium-darwin.png]
key-decisions:
  - "Release reporting remains outside evaluate_phase2.py so report code cannot silently invalidate hash-bound real expert review."
  - "A constant human/Judge score series is fail-closed because Spearman is mathematically undefined."
  - "The approved visual candidate was promoted only after exact SHA and old-official SHA verification."
patterns-established:
  - "A release PASS requires every recomputed gate, not an evaluator exit code or prior checkpoint."
requirements-completed: []
duration: 31min
completed: 2026-08-29
status: release_blocked
---

# Phase 02 Plan 18：发布报告、视觉晋升与证据文档 Summary

**将真实专家复审、36-call Judge 与机器评测合并为 hash-bound `FAIL` 发布报告，同时将批准 SHA 的完成分析视觉基线晋升并补齐真实 E2E 与中文教学。**

## Performance

- **Duration:** 31min
- **Tasks:** 3/3 自动化交付完成；发布接受门未通过
- **Files modified:** 12（不含用户未提交模板）

## Accomplishments

- 新增独立 `release_phase2.py`，精确绑定 dataset、code-eval、formal signoff 与 v4 Promptfoo 的 SHA，重算 Critical、High、Medium、score-1 和 Spearman 门。
- 基于于女士与陈先生实际保存的全 4 复审重新物化 `expert-signoff-phase2.json`，并通过 `validate-signoff`；没有改动、暂存或提交用户模板。
- `phase2-release.json` 如实为 `FAIL`：Critical 100%、High 100%、两类 Medium 平均 4、无 1 分均通过；十个配对人类/Judge 分数都恒定，Spearman 为 `null`，因此阈值失败。
- 核验用户批准 SHA 后，将 `530b6bde4cb90cf7d8a99919c76317c58a34b598fa5ed764b7d8adc7f1d47562` 机械晋升为 official visual baseline；旧 baseline 为 `fba54a9449177837dc6f2496d29e479ad26b3b7d0b707de52c2ca6018df2ab4a`。
- Playwright 真实本机链路 5/5 通过：克数直算、断线/重载零二次分析 POST、集中 resume、修正、跨用户 404、DELETE 与完成分析视觉。
- 新增证据绑定的中文教学文档及 Phase 2 全部 18 个计划索引。

## Task Commits

1. **Task 1: 执行已授权 Promptfoo 并生成唯一 release report** — `ce36b97` (`fix`)
2. **Task 2: 晋升批准视觉并完成真实 E2E/browser** — `25458b1` (`test`)
3. **Task 3: 写证据绑定的中文教学文档** — `5d95a2a` (`docs`)

## Verification

- `backend/.venv/bin/python -m pytest tests/unit/test_phase2_eval_contract.py -q` — 7 passed
- `validate-signoff` — passed
- `release_phase2.py release ...` — report generated as `FAIL`; `verify-release` correctly exits non-zero
- `frontend npm run test:e2e -- --grep "phase 2 direct grams contract|phase 2 visual candidate"` — 5 passed
- directory-contract pytest, Ruff、frontend build 和 Phase README `02-01`…`02-18` index checks — passed
- 内置浏览器：真实 `http://127.0.0.1:4173/` 公开首页可访问，产品入口与免责声明可见。

## Decisions Made

- 不修改被 `phase2-code-eval.json` hash 绑定的旧评测器；报告器单独实现，避免仅为汇总逻辑而让真实签署过期。
- 不通过更改或推断专家评分来使评测变绿。全 4 仍是常数，无法满足 Spearman 合同。
- 视觉批准与发布接受门独立：视觉已晋升，但不代表 release `PASS`。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Integrity] Isolated the release evaluator from the signed code-eval evaluator**
- **Found during:** Task 1
- **Issue:** 修改 `evaluate_phase2.py` 会改变已审核 code-eval 的实现 hash，使真实签署失效。
- **Fix:** 新建 `release_phase2.py`，只读消费四类不可变证据。
- **Verification:** 原 code-eval/signoff 验证仍通过；新 release 单元测试覆盖可变分数 PASS 与真实常数 FAIL。
- **Committed in:** `ce36b97`

**2. [Rule 1 - Test] Corrected foreign-thread E2E return URL assumption**
- **Found during:** Task 2
- **Issue:** 登录回跳会安全清理未知 thread query，测试错误地期待 query 保留。
- **Fix:** 正常登录后访问 foreign thread URL，再断言 404 驱动的 URL 清理和报告不可见。
- **Verification:** 真实 Playwright 5/5 passed。
- **Committed in:** `25458b1`

## Release Blockers

1. **Release gate failure:** latest real human scores and v4 Judge scores are both constant `[4, 4, 4, 4, 4]`; Spearman is undefined. 不能通过把所有分数改成相同值解决。若要重新评测，必须由两位专家独立、可审计地重新审阅并产生真实非恒定配对分数，再获得新的付费运行授权（不能复用或篡改旧 Judge 证据）。
2. **Browser matrix incomplete:** 自动化 E2E 已覆盖真实认证路径；内置浏览器只验证了公开首页。它在输入测试邮箱和密码前要求即时用户确认，因此认证成功、错误和空态浏览器验收未完成。

## Next Phase Readiness

- 已有可信的机器、专家、Judge、视觉与 E2E 证据，但 **Phase 2 不能标记为 release PASS 或完成**。
- 不更新 `STATE.md`、`ROADMAP.md` 或 requirements 状态，直到 Spearman 发布门和内置浏览器认证矩阵均真实通过。

## Known Stubs

None.

## Self-Check: PASSED

- `ce36b97`、`25458b1`、`5d95a2a` 均存在于 git history。
- 本 Summary、release report、official baseline 和中文教学文档均存在。
