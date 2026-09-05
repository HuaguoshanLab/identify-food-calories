---
phase: 06-user-dashboard-admin
plan: 33
subsystem: api
tags: [fastapi, sqlalchemy, zoneinfo, pytest, ruff, idempotency, timezone]
requires:
  - phase: 06-32
    provides: "Records 的 confirmation-first 读取门控与时区验收证据"
provides:
  - "同一已确认 IANA 统计时区可零额外写入地安全重放 confirmation DTO"
  - "异时区和并发唯一约束竞争的泛化 409，且不泄露已存 preference"
  - "Records 三条公开写命令对 ZoneInfo ValueError 的安全 400 映射"
affects: [06-34, 06-35, 06-36, dashboard, frontend-records]
tech-stack:
  added: []
  patterns:
    - "Records Service 在 mutation 前验证 IANA，并将 ZoneInfo 异常族统一映射为领域错误"
    - "唯一约束失败后先 rollback 再 reread，以同/异 IANA 分流幂等 DTO 或泛化冲突"
key-files:
  created: []
  modified:
    - backend/app/records/service.py
    - backend/tests/records/test_record_service.py
    - backend/tests/unit/test_meal_record_api.py
    - backend/app/records/README.md
key-decisions:
  - "仅存储 preference 的相同 ZoneInfo.key 可以重放；不同 key 永远不暴露已确认的值或时间。"
  - "唯一约束竞争必须 rollback 后重读，不将同值竞争者误报为冲突。"
patterns-established:
  - "公开 IANA 写命令以 InvalidTimeZone 作为所有解析失败的安全 HTTP 400 边界。"
requirements-completed: [UI-02]
duration: 1min
completed: 2026-09-05
---

# Phase 6 Plan 33: Records 统计时区确认安全契约 Summary

**Records confirmation 现在可安全重试同一 IANA 时区、对异时区和竞争保持无泄露冲突，并在所有公开写入口拒绝危险 ZoneInfo key。**

## Performance

- **Duration:** 1 min
- **Started:** 2026-09-05T09:52:43+08:00
- **Completed:** 2026-09-05T09:53:13+08:00
- **Tasks:** 1/1
- **Files modified:** 8

## Accomplishments

- 已确认 preference 的同一 `ZoneInfo.key` 返回原 `DashboardTimezoneConfirmationResponse`，不再回填、审计或 commit。
- 异 key 维持泛化 `DashboardTimeZoneAlreadyConfirmed`；唯一约束失败会 rollback、重新读取并按同/异值准确分流。
- `ValueError`、`TypeError` 和 `ZoneInfoNotFoundError` 全部映射为 `InvalidTimeZone`，三条 Records 写路由稳定返回安全 400。
- fake repository 与 HTTP 合约测试锁定无额外写入、无异常详情和无 preference 泄露，并同步 Records/Test 目录索引。

## Task Commits

1. **Task 1: 让 Records confirmation 同 zone 幂等、异 zone 冲突，并在写入前拒绝所有 ZoneInfo 非法 key** - `a19c04a` (test), `95294b5` (fix)

## Files Created/Modified

- `backend/app/records/service.py` - 实现同值 replay、竞争 rollback/reread 与完整 ZoneInfo 异常映射。
- `backend/tests/records/test_record_service.py` - 覆盖首次/同值/异值/竞争和写入前拒绝。
- `backend/tests/unit/test_meal_record_api.py` - 覆盖安全 400 与泛化 409 公开 HTTP 契约。
- `backend/app/README.md`、`backend/app/records/README.md` - 标注 records-owned confirmation 事务边界。
- `backend/tests/README.md`、`backend/tests/records/README.md`、`backend/tests/unit/README.md` - 同步测试职责和文件索引。

## Decisions Made

- 复用已有 confirmation DTO、领域异常和表约束；没有新增表、字段、迁移或可编辑 preference 端点。
- API 路由保留既有 400/409 映射；业务判断和并发恢复完全位于 Records Service。

## Verification

- `cd backend && uv run pytest tests/records/test_record_service.py tests/unit/test_meal_record_api.py -q` — **20 passed**。
- `cd backend && uv run ruff check app/records tests/records/test_record_service.py tests/unit/test_meal_record_api.py` — **All checks passed**。
- `git diff --check` — **passed**。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test correctness] 补全 HTTP 参数化测试的 pytest 导入**
- **Found during:** Task 1
- **Issue:** 新增参数化 API 合约测试遗漏 `pytest` 导入，收集阶段会直接失败。
- **Fix:** 添加显式导入后重新执行红绿循环。
- **Files modified:** `backend/tests/unit/test_meal_record_api.py`
- **Verification:** 目标 pytest 20 项通过，Ruff 通过。
- **Committed in:** `a19c04a`

---

**Total deviations:** 1 auto-fixed（Rule 1 - test correctness）。
**Impact on plan:** 仅修复测试收集错误；没有扩展产品范围、依赖或 schema。

## Issues Encountered

- 初次在受限沙箱执行 `uv` 无法读取现有本地缓存；经授权后在相同项目环境运行测试，未安装或下载任何依赖。

## Known Stubs

None - 本计划的 confirmation 返回值、冲突分流和公开 HTTP 映射均连接现有 Service/API，不依赖空数据或 placeholder。

## User Setup Required

None - 不需要新增环境变量、密钥、迁移或外部服务配置。

## Next Phase Readiness

- 06-34 可以在 records-owned 且可幂等确认的安全前提上收回服务端当前周窗口权威。
- 06-35/36 可以依赖同值 confirmation 的 200 和异值的明确冲突，移除浏览器对读取范围的影响并验证跨时区路径。

## Self-Check: PASSED

- 已确认 `backend/app/records/service.py`、两份测试及五份受影响 README 均存在；`a19c04a` 与 `95294b5` 均可从 Git 历史读取。
- 修改文件扫描未发现会阻塞本计划目标的 TODO、placeholder 或空数据 stub。

---
*Phase: 06-user-dashboard-admin*
*Completed: 2026-09-05*
