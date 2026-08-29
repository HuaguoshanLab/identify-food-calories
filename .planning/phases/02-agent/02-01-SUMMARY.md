---
phase: 02-agent
plan: 01
subsystem: supply-chain
tags: [python-3.11, pip, sha256, langgraph, dependency-lock, fail-closed]
requires:
  - phase: 01-engineering-auth-foundation
    provides: "Python 3.11 后端运行环境、pytest 基础设施与目录 README 合同"
provides:
  - "固定七个 Phase 2 新依赖的人工审核 evidence 与不可自动批准门"
  - "Python 3.11 的 hash-complete requirements.lock 与直接依赖漂移检查"
  - "经同一锁同步并冒烟验证的 backend/.venv"
affects: [agent-graph, postgres-checkpointer, provider-adapter, evaluation]
tech-stack:
  added: [langgraph 1.2.11, langgraph-checkpoint-postgres 3.1.2]
  patterns: ["版本化人工供应链 manifest", "pip report + download hash lock", "临时环境与实际环境双重重建"]
key-files:
  created:
    - backend/supply-chain-evidence-v1.schema.json
    - backend/supply-chain-evidence.json
    - backend/validate_supply_chain.py
    - backend/lock_dependencies.py
    - backend/requirements.lock
  modified:
    - backend/pyproject.toml
    - backend/tests/unit/test_supply_chain.py
    - backend/tests/unit/README.md
    - backend/README.md
key-decisions:
  - "未固定身份的 PATH scanner 不执行；使用字段完整、带响应哈希的人工 manifest。"
  - "requirements.lock 以 pip resolver report 的实际归档哈希为准，再以 pip download 复核。"
  - "后续计划只能使用由同一锁同步过的 Python 3.11 backend/.venv。"
patterns-established:
  - "新增 Python 依赖须先通过 supply-chain evidence，再生成或更新 lock。"
  - "lock 检查必须同时验证 pyproject 直接依赖头、精确版本和每行 SHA-256。"
requirements-completed: [AGT-01, ARC-05, ARC-06, QLT-02]
duration: 2h
completed: 2026-08-29
---

# Phase 02 Plan 01: 供应链证据与首绿依赖锁 Summary

**七个新增 Agent 依赖已由人工批准并固化官方 registry 哈希证据，LangGraph runtime 可仅从 Python 3.11 的 hash-complete lock 重建。**

## Performance

- **Duration:** 2h
- **Completed:** 2026-08-29T03:49:34Z
- **Tasks:** 3/3
- **Files modified:** 9

## Accomplishments

- 建立版本化、fail-closed 的供应链 evidence schema 与校验器；`pending` 或未固定的 PATH scanner 均不能授权安装。
- 将用户批准的 7 个精确版本固化为人工 manifest，包含官方 registry 响应 SHA-256、发布者、来源仓库、许可证和发布时间。
- 生成 83 行 Python 3.11 hash-complete lock，并验证临时干净 venv 与实际 `backend/.venv` 都能从该锁安装和 import `AsyncPostgresSaver`。
- 完成后端全量测试：119 passed；真实 PostgreSQL 集成测试使用隔离 `_test` 数据库通过。

## Task Commits

1. **Task 1: 建立版本化供应链 evidence validator（RED/GREEN）** — `aae0fcc`、`d00df15`
2. **Task 2: 核验全部新增依赖（人工批准后固化 evidence）** — `a536907`
3. **Task 3: 首绿前生成并洁净验证 hash-complete Python lock（RED/GREEN）** — `5db2ba4`、`2ca3ee1`
4. **验收修复：供应链证据完整性与时间顺序** — `a7ab149`

## Files Created/Modified

- `backend/supply-chain-evidence-v1.schema.json` — 供应链 evidence v1 的可审计数据合同。
- `backend/supply-chain-evidence.json` — 七个已批准精确版本的人工 manifest 与 registry 响应哈希。
- `backend/validate_supply_chain.py` — 不执行 PATH scanner 的 fail-closed validator。
- `backend/lock_dependencies.py`、`backend/requirements.lock` — pip report/download 驱动的锁生成与漂移检测。
- `backend/pyproject.toml` — 加入已批准的 LangGraph 与 PostgreSQL Checkpointer 直接依赖。
- `backend/tests/unit/test_supply_chain.py` — evidence 篡改、时间顺序、锁 hash 和 pyproject 漂移合同。
- `backend/README.md`、`backend/tests/unit/README.md` — 安装方式与文件索引。

## Decisions Made

- 未运行 PATH 中的 `slopcheck`；scanner 身份未被完整固定时只接受人工 manifest。
- 人工 evidence 必须包含官方 registry response SHA-256；manifest 自身使用 canonical JSON SHA-256 防篡改。
- 使用临时 clean Python 3.11 venv 证明可重建，再同步实际 `backend/.venv`，禁止后续混用系统 Python。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 接受 npm 的官方可哈希 registry 端点**
- **Found during:** Task 2
- **Issue:** validator 错将 npm 展示页域名作为唯一 registry 域名，拒绝 `registry.npmjs.org` 的官方版本响应。
- **Fix:** 改为只接受 npm 官方 registry API 域名，并以真实响应 SHA-256 填充 manifest。
- **Files modified:** `backend/validate_supply_chain.py`, `backend/tests/unit/test_supply_chain.py`, `backend/supply-chain-evidence.json`
- **Verification:** evidence validator、17 项专项测试与 ruff/mypy 通过。
- **Committed in:** `a536907`, `a7ab149`

**2. [Rule 1 - Bug] 排除 pip report 中无归档哈希的本地项目记录**
- **Found during:** Task 3
- **Issue:** pip report 为本地 `food-agent-backend` 记录 `file://` 来源但没有 archive hash；初版生成器误把它当作外部锁定包。
- **Fix:** 明确跳过本地项目，仅对 registry 分发包要求归档 SHA-256，并增加回归测试。
- **Files modified:** `backend/lock_dependencies.py`, `backend/tests/unit/test_supply_chain.py`
- **Verification:** lock 生成、drift check、干净 venv 安装和实际 `.venv` 同步通过。
- **Committed in:** `2ca3ee1`

**3. [Rule 2 - Missing Critical] 证明 evidence 时间关系与全部身份字段不可篡改**
- **Found during:** Task 1 验收
- **Issue:** 初版只校验时间格式，未拒绝核验早于发布或晚于 evidence 生成；registry、repository、license 与重复项缺少定向测试。
- **Fix:** 加入发布/核验/生成时间顺序校验，补齐 registry、repository、license、重复记录和 manifest hash 覆盖。
- **Files modified:** `backend/validate_supply_chain.py`, `backend/supply-chain-evidence.json`, `backend/tests/unit/test_supply_chain.py`
- **Verification:** 17 项专项测试、evidence validator、ruff 与 mypy 通过。
- **Committed in:** `a7ab149`

**Total deviations:** 3 auto-fixed（2 个 Rule 1，1 个 Rule 2）。
**Impact on plan:** 修复均为供应链门正确性所必需；没有扩大功能范围。

## Issues Encountered

- 常规沙箱拒绝访问本机 PostgreSQL 端口，导致集成测试不能启动；以受控权限重跑同一条隔离测试命令后，`119 passed`。

## Known Stubs

None. 当前 evidence 已获人工批准；锁文件和实际运行环境均已验证，未留下阻断计划目标的占位实现。

## User Setup Required

None - 用户已完成本计划唯一的人工供应链批准；无需配置外部服务或密钥。

## Next Phase Readiness

- 后续 Agent、Checkpointer 和 Provider 计划可以使用 `backend/.venv/bin/python` 与 `requirements.lock`，不得绕过 hash lock。
- 任何新增 Python 依赖都必须先更新并通过 supply-chain evidence，再重新生成、验证并同步 lock。

## Self-Check: PASSED

- Summary、五个主要交付物和全部六个任务提交均已确认存在。
- supply-chain validator 与 lock drift check 在 metadata 提交前再次通过。

*Phase: 02-agent*
*Completed: 2026-08-29*
