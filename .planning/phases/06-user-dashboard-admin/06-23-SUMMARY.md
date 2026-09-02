---
phase: 06-user-dashboard-admin
plan: 23
subsystem: agent-safety
tags: [python, pydantic, deepseek, fake-provider, offline-evaluation, privacy]
requires:
  - phase: 06-07
    provides: Deterministic weekly facts, coverage gate, version vocabulary, and minimal cache boundary.
  - phase: 06-08
    provides: Strictly validated de-identified 14-case weekly-review fixture catalog.
provides:
  - Facts-only bounded weekly-review graph with deterministic safe abstentions.
  - Runtime-validated symmetric DeepSeek/Fake weekly-review Provider contracts.
  - Loader-driven frozen evaluation for all 14 safety, privacy, budget, and schema cases.
affects: [weekly-review-api, dashboard-cache, provider-evaluation, phase-07]
tech-stack:
  added: []
  patterns: [facts-only provider DTO, independent semantic gate, no-replay unknown outcome, fixture-driven offline eval]
key-files:
  created: [backend/app/dashboard/weekly_review_graph.py, backend/app/dashboard/weekly_review.py, backend/tests/evals/test_weekly_review_eval.py]
  modified: [backend/app/providers/reasoning/dto.py, backend/app/providers/reasoning/ports.py, backend/app/providers/reasoning/fake.py, backend/app/providers/reasoning/deepseek.py]
key-decisions:
  - "WeeklyReviewOutputDTO validates only strict structure; the graph separately applies facts/category and health-language semantics to every adapter result."
  - "Unknown provider outcomes stop immediately without a retry; schema and semantic failures receive at most one explicit correction retry."
  - "Fake Provider discards each facts request body and records only call accounting metadata."
requirements-completed: [UI-02]
duration: 7min
completed: 2026-09-02
---

# Phase 06 Plan 23: Bounded Weekly Review Graph Summary

**基于去标识周聚合事实的受限周复盘 graph：Provider 最多两次调用、八秒和 360 输出 token，并对 schema、事实越界、医疗/强制语言、预算、停用和未知结果确定性弃权。**

## Performance

- **Duration:** 7 min
- **Started:** 2026-09-02T11:37:43Z
- **Completed:** 2026-09-02T11:45:19Z
- **Tasks:** 2/2
- **Files modified:** 13

## Accomplishments

- 用 Pydantic 建立严格的周复盘 facts/request/output/result DTO；Provider 请求无法携带用户原文、图片、邮件、账本 digest 或任意额外字段。
- 扩展 Reasoning Provider 窄 port，并让 DeepSeek 与 Fake 使用同一周复盘 DTO；DeepSeek 固定静态安全指令、`reasoning.effort=none` 和 360 output token，Fake 不保留请求体。
- 交付纯 async facts-only graph：覆盖不足、Provider 停用、预算拒绝、超时、schema/语义无效与未知结果均返回稳定安全码；未知结果绝不重放。
- 将全部 14 个冻结 case 由 loader 驱动，断言稳定码、调用数、最小 ledger 与版本/digest 元数据；无真实模型、SaaS 或敏感样本。

## Task Commits

1. **Task 1: 由冻结 loader 写 graph/provider/eval RED 矩阵** — `29b51e1` (test)
2. **Task 2: 实现 facts-only graph 与对称 Provider adapter** — `5e90f59` (feat)

## Files Created/Modified

- `backend/app/dashboard/weekly_review_graph.py` — 有界 async graph、事实输入白名单、语义安全阀和稳定 abstention 映射。
- `backend/app/dashboard/weekly_review.py` — 不接触持久化的应用层 graph 调用包装。
- `backend/app/providers/reasoning/{dto.py,ports.py,fake.py,deepseek.py}` — 受限周复盘 DTO、port、无请求体 Fake 与 360-token DeepSeek adapter。
- `backend/tests/dashboard/test_weekly_review_graph.py` — 14-case graph、敏感字段零调用和 unknown no-replay 合同。
- `backend/tests/providers/test_weekly_review_provider_dto.py` — DTO 白名单、语义拒绝和 Fake trace 数据最小化合同。
- `backend/tests/evals/test_weekly_review_eval.py` — loader 驱动的冻结评测门禁。
- `backend/app/dashboard/README.md`、`backend/app/providers/reasoning/README.md`、`backend/tests/providers/README.md` — 目录职责、允许依赖与文件索引。

## Decisions Made

- DTO 的职责仅限运行时结构/字段白名单；事实支持性、类别范围、数字、医疗/限制性语言和 reasoning 文本由 graph 的独立语义阀重复验证，避免任一 adapter 绕过安全判定。
- graph 只拿到 `facts_digest` 与版本写最小 ledger metadata；facts JSON、prompt、Provider body、输出原文和 reasoning 不进入账本或 Fake trace。
- fixture 的 `admission` 仅为离线证据，不是可被 runtime 接受的配置字段。

## Verification

- `cd backend && uv run pytest tests/architecture/test_directory_contract.py tests/test_reasoning_provider.py tests/dashboard/test_weekly_review_graph.py tests/providers/test_weekly_review_provider_dto.py tests/evals/test_weekly_review_eval.py -q` — PASS（46 passed）。
- `cd backend && uv run ruff check app/dashboard/weekly_review_graph.py app/dashboard/weekly_review.py app/providers/reasoning/ports.py app/providers/reasoning/dto.py app/providers/reasoning/fake.py app/providers/reasoning/deepseek.py tests/dashboard/test_weekly_review_graph.py tests/providers/test_weekly_review_provider_dto.py tests/evals/test_weekly_review_eval.py` — PASS。
- 敏感字段与 stub 扫描 — PASS：仅测试内存注入的 email 负例和静态安全指令命中；没有持久 Provider/request/output/reasoning 内容，也未引入网络 endpoint、认证路径、文件访问或 schema 变更。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 使冻结 loader 测试适配现有 pytest 运行时**
- **Found during:** Task 2
- **Issue:** 项目未安装 `pytest-asyncio`，且 `tests/` 不是可导入 Python package；初始 RED 测试会在 collection 前失败，不能实际执行 frozen contract。
- **Fix:** 按项目既有 async 测试惯例使用同步测试中的 `asyncio.run`，并通过 `importlib` 直接加载严格 loader；仍由 loader 而非测试内嵌 case 驱动。
- **Files modified:** `backend/tests/dashboard/test_weekly_review_graph.py`, `backend/tests/evals/test_weekly_review_eval.py`, `backend/tests/providers/test_weekly_review_provider_dto.py`。
- **Verification:** 14-case eval 与完整 46 项聚焦测试通过。
- **Committed in:** `5e90f59`。

**2. [Rule 2 - Missing Critical] 同步新增模块文件的目录索引**
- **Found during:** Task 2
- **Issue:** 新增周复盘 graph/应用包装和 Provider 能力后，直接父目录 README 未完整索引其职责与安全边界，违反项目目录文档合同。
- **Fix:** 更新 dashboard 和 reasoning README，并在新建 `tests/providers/` 同次建立职责、允许依赖和文件索引。
- **Files modified:** `backend/app/dashboard/README.md`, `backend/app/providers/reasoning/README.md`, `backend/tests/providers/README.md`, `backend/tests/README.md`。
- **Verification:** `tests/architecture/test_directory_contract.py` 通过。
- **Committed in:** `29b51e1`, `5e90f59`。

---

**Total deviations:** 2 auto-fixed（Rule 1: 1，Rule 2: 1）。
**Impact on plan:** 两项均保证测试真实执行与目录合同可审计；未增加外部依赖、网络能力或业务范围。

## Known Stubs

None - graph 的拒绝路径是可交付的安全行为，不是未接线占位符。

## Issues Encountered

- sandbox 默认禁止访问既有 uv cache 与 Git index；获得受控权限后，未下载新包，全部计划测试与原子提交正常完成。

## User Setup Required

None - 不新增依赖、密钥、SaaS 或外部配置。

## Next Phase Readiness

- 后续 API/cache 编排可通过 `run_weekly_review` 传入已验证 facts，并且只持久化 `WeeklyReviewGraphResult` 的最小安全 metadata。
- 冻结 14-case 门禁已覆盖低覆盖、事实污染、schema/语义拒绝、Provider 停用与 no-replay unknown 路径；无已知阻塞项。

## Self-Check: PASSED

- 已确认 `weekly_review_graph.py`、`weekly_review.py`、三份测试与 Provider 变更文件均存在。
- 已确认 Task commits `29b51e1` 与 `5e90f59` 均在 Git 历史中存在。

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-02*
