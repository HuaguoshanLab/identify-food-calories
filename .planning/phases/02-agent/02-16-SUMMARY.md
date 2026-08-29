---
phase: 02-agent
plan: 16
subsystem: evaluation-release-contract
tags: [fake-provider, langgraph, postgresql-checkpointer, promptfoo, expert-review, release-gate]
requires:
  - phase: 02-agent
    provides: "冻结 24-case 数据集、持久化 MealAnalysisGraph、确定性营养工具与 PostgreSQL Checkpointer"
provides:
  - "dataset/源码哈希绑定的 24-case 实际机器评测证据"
  - "每 case 营养师与食物成分数据管理员双角色签署合同"
  - "固定 12×3 Promptfoo 配置、阈值失败夹具和已批准本地 CLI"
affects: [phase-02-human-signoff, phase-02-paid-promptfoo, phase-02-release]
tech-stack:
  added: [promptfoo@0.122.0]
  patterns: ["observed-not-expected evidence", "hash-bound review inputs", "fail-closed release fixtures"]
key-files:
  created:
    - backend/evals/evaluate_phase2.py
    - backend/evals/phase2-code-eval.json
    - backend/evals/expert-signoff-v1.schema.json
    - backend/evals/promptfooconfig.yaml
    - backend/evals/release-failures.json
  modified:
    - backend/evals/README.md
    - frontend/package.json
    - frontend/package-lock.json
    - README.md
key-decisions:
  - "机器评测只保存实际 Fake Provider→Graph→工具→PostgreSQL Checkpointer 观测，拒绝复制 expected 的静态文件。"
  - "每个 case 必须由不同 pseudonym 的营养师和食物成分数据管理员共同签署；附加产品/隐私角色不能替代。"
  - "Promptfoo 固定为 frontend lockfile 的 promptfoo@0.122.0，仅能用 npx --no-install，并必须等待独立付费授权。"
metrics:
  duration: "约 55 分钟"
  completed: "2026-08-29"
  cases: 24
  critical_pass_percent: 100.0
  high_pass_percent: 100.0
---

# Phase 02 Plan 16: 机器评测与发布合同 Summary

**24 条冻结案例现已由实际 Fake Provider、Meal Graph、确定性工具和 PostgreSQL Checkpointer 运行并产出 hash-bound 观测证据；人工签署和付费 Judge 仍被独立门禁阻塞。**

## Accomplishments

- `phase2-code-eval.json` 绑定 dataset、评测器、Graph、Fake Provider、工具、营养 Service、目录和 State schema 的 SHA-256；包含精确 24 条 observed state、trace、report、events、禁止结果、provider calls 与 Checkpointer reopen 证据。
- `verify-code-eval` 拒绝静态 expected 冒充、案例重排、缺执行证据以及任何实现或 dataset hash 漂移。当前观测计算为 Critical 100%、High 100%。
- 双角色 JSON schema 强制每 case 一位营养师和一位食物成分数据管理员，强制不同 pseudonym、五项专业确认及 dataset/code-eval/rubric hash；所有 Medium 样本还必须有逐 case 人工/Judge 1–5 分，Spearman 只能从原始分数重算。
- 15 类独立 failure fixtures 覆盖缺角色、重复 reviewer/pseudonym、缺评分、hash/rubric 漂移、Spearman 和全部发布阈值失败。
- 已按用户批准将 `promptfoo@0.122.0` 精确锁定在现有 `frontend/` Node 项目，并验证 `npx --no-install promptfoo --version` 为 `0.122.0`。没有运行付费评测。

## Verification

- `pytest tests/unit/test_eval_dataset.py tests/unit/test_phase2_eval_contract.py -q` — 5 passed。
- `ruff check`、`mypy evals/evaluate_phase2.py` — passed。
- 通过 `tests/run_pg.py` 在隔离 `food_agent_test` 实际执行并复核 24-case code eval — passed。
- `self-test --fixtures release-failures.json` 与 `validate-contracts` — passed。
- `frontend`：`npm run lint`、`npm run typecheck`、`npx --no-install promptfoo --version | grep -Fx 0.122.0` — passed。

## Evidence

- Dataset SHA-256：`0c837864750b30d97f545010c763f2540086d545922b515923c684cae57b66ac`
- Code-eval evidence SHA-256：`4f7dd409a41320242bcf73a9d977ba38c22c9ceb2a69374c8dc0df27ac8373d0`

## Task Commits

1. `fc4acba` — `test(02-16): add failing eval evidence contracts`
2. `c991d39` — `feat(02-16): record observed 24-case code eval`
3. `118e938` — `feat(02-16): lock expert and release evidence contracts`
4. `e99a37b` — `chore(02-16): pin approved local promptfoo cli`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] 仓库根目录没有 Node package，不能把 CLI 安装到计划所列的根 `package.json`。**

- **Found during:** Task 3
- **Fix:** 将已批准的 `promptfoo@0.122.0` 精确加入已有的 `frontend/package.json` / `package-lock.json`，并在根 README 与 frontend README 固定唯一调用方式。
- **Why:** `frontend/` 是仓库唯一 Node 项目；新建根 Node workspace 会引入无职责架构层且破坏现有前端依赖边界。
- **Commit:** `e99a37b`

**2. [Rule 3 - Blocking] Promptfoo 的 Apple Silicon SQLite 绑定未随 omit-optional 安装。**

- **Found during:** Task 3 本地 CLI 版本验证
- **Fix:** 只从已批准的 lockfile 补齐 Promptfoo 自身的官方可选 `@libsql/darwin-arm64` 传递绑定，跳过安装脚本；随后本地 CLI 版本校验通过。
- **Commit:** `e99a37b`

## Known Stubs

None。`expert-signoff-phase2.json` 和 `promptfoo-phase2.json` 尚未创建不是 stub：它们必须分别由 Plan 02-17 的真人双角色签署与明确付费授权产生。

## Next Phase Readiness

Plan 02-17 必须停止在三个独立人工门：24 case 双角色签署、12×3 Promptfoo 付费授权、以及 candidate 视觉批准。任何一个批准都不能替代另两个。

## Self-Check: PASSED

- 已确认机器证据、schema、Promptfoo 配置、失败夹具和本 Summary 存在。
- 已确认四个任务提交均存在于 Git 历史。
