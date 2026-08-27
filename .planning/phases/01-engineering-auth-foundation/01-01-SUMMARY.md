---
phase: 01-engineering-auth-foundation
plan: 01
subsystem: infra
tags: [fastapi, pydantic-settings, postgresql, pgvector, mailpit, docker-compose]

requires: []
provides:
  - 独立的 pgvector 开发库与测试库以及固定版本 Mailpit
  - fail-closed 数据库、生产密钥、Cookie、CORS 与 SMTP 配置
  - FastAPI /api/v1/health 运行基座
  - 根与 backend 自文档化目录契约
affects: [01-02, 01-03, 01-04, backend, auth, local-infrastructure]

tech-stack:
  added: [FastAPI 0.128.8, Pydantic Settings 2.11.0, SQLAlchemy 2.0.52, pgvector 0.8.6, Mailpit 1.30.6]
  patterns: [fail-closed runtime settings, isolated real-PostgreSQL tests, process-wide engine factory, self-documented directories]

key-files:
  created: [docker-compose.yml, backend/app/main.py, backend/app/core/config.py, backend/tests/unit/test_runtime_foundation.py]
  modified: [README.md, backend/README.md, backend/pyproject.toml]

key-decisions:
  - "本地基础设施固定 pgvector 0.8.6/PostgreSQL 16 与 Mailpit 1.30.6，并只绑定回环地址。"
  - "非生产环境允许无云凭据连接 Mailpit；production 必须同时满足强密钥、Secure Cookie、显式 CORS 和完整 SMTP 凭据。"

patterns-established:
  - "配置先验证后注入：FastAPI 只接收通过 Pydantic Settings 安全边界的配置。"
  - "测试库硬隔离：真实 PostgreSQL、独立端口/卷、_test 命名且禁止 SQLite 和开发库回退。"

requirements-completed: [ARC-01, ARC-04, ARC-07]

duration: 13 min
completed: 2026-08-27
---

# Phase 1 Plan 1: 工程运行基座 Summary

**固定版本 pgvector 双库与 Mailpit 编排，配套拒绝不安全生产组合的 FastAPI 配置和版本化健康端点。**

## Performance

- **Duration:** 13 min
- **Started:** 2026-08-27T05:44:35Z
- **Completed:** 2026-08-27T05:57:26Z
- **Tasks:** 2
- **Files modified:** 20

## Accomplishments

- 建立根、backend、app、core、migrations、tests 与 tests/unit 的职责、允许依赖和文件索引契约。
- 通过 Docker Compose 运行相互隔离的开发/测试 pgvector 数据库，并以固定版本 Mailpit 提供本地 SMTP 捕获。
- 用 18 个单元测试证明数据库隔离、生产配置 fail closed、本地无云凭据 SMTP 和 `/api/v1/health` 合约。

## Task Commits

每个任务均原子提交；TDD 任务按 RED → GREEN 拆分：

1. **Task 1: 审计并建立根与后端目录契约** - `48bfddb` (chore)
2. **Task 2 RED: 建立失败的运行基座合约** - `3214c80` (test)
3. **Task 2 GREEN: 建立隔离基础设施与 fail-closed 配置** - `3182fd8` (feat)

## Files Created/Modified

- `docker-compose.yml` - 固定镜像的 pgvector dev/test 与 Mailpit 编排及健康检查。
- `backend/app/core/config.py` - 数据库、生产密钥、Cookie、CORS 与 SMTP 安全边界。
- `backend/app/core/database.py` - 进程级连接池与请求级 Session factory。
- `backend/app/main.py` - FastAPI 工厂、显式 CORS 与版本化健康端点。
- `backend/tests/unit/test_test_database_guards.py` - 数据库与生产配置拒绝矩阵。
- `backend/tests/unit/test_runtime_foundation.py` - 健康端点公开合约。
- `README.md`、`backend/README.md` 与各目录 README - 工程边界、运行命令和目录索引。

## Decisions Made

- 使用官方可核对的 `pgvector/pgvector:0.8.6-pg16-bookworm` 与 `axllent/mailpit:v1.30.6`，避免浮动镜像导致不可复现或遗漏安全修复。
- 本地端口只绑定 `127.0.0.1`；开发便利不等于把数据库和 SMTP 暴露到局域网。
- 健康端点只返回状态和 API 版本，不泄露数据库、SMTP 或密钥配置。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical documentation] 补齐 `tests/unit/README.md`**
- **Found during:** Task 1
- **Issue:** 计划文件列表遗漏了已有 `tests/unit/` 目录的 README，违反根 `AGENTS.md` 的目录契约。
- **Fix:** 增加职责、允许依赖和文件索引，并同步父级测试索引。
- **Files modified:** `backend/tests/unit/README.md`, `backend/tests/README.md`
- **Verification:** 三段式 README 扫描通过。
- **Committed in:** `48bfddb`

**2. [Rule 1 - Bug] 修复继承测试中的正则转义**
- **Found during:** Task 2 RED
- **Issue:** 旧 scaffold 用未转义的 `+` 匹配 `postgresql+psycopg`，导致正确异常消息仍被 pytest 判为不匹配。
- **Fix:** 将期望表达式改为转义后的字面量匹配。
- **Files modified:** `backend/tests/unit/test_test_database_guards.py`
- **Verification:** 旧数据库保护 7 项与新增合约共 18 项全部通过。
- **Committed in:** `3214c80`

**3. [Rule 3 - Blocking tooling] 隔离本地 Python 构建产物**
- **Found during:** Task 2 RED
- **Issue:** editable install 生成 `.venv` 与 `*.egg-info`，若未忽略会污染工作树并破坏原子提交。
- **Fix:** 增加 backend 局部 `.gitignore`，忽略虚拟环境、缓存、覆盖率与 editable metadata。
- **Files modified:** `backend/.gitignore`, `backend/README.md`
- **Verification:** `git status --short` 无生成产物。
- **Committed in:** `3214c80`, `3182fd8`

---

**Total deviations:** 3 auto-fixed (1 Rule 1, 1 Rule 2, 1 Rule 3)。
**Impact on plan:** 均为测试正确性、强制目录契约和可重复工具链所必需，无功能扩张。

## Issues Encountered

- 沙箱最初禁止 PyPI 网络、Docker daemon、Git index 与本机监听端口；使用受控提权后完成相同固定范围操作，未跳过测试或 Git hooks。

## Known Stubs

None. 可选 SMTP 凭据的 `None` 仅适用于 local/test，production validator 强制提供；migration 目录本计划按边界要求只验证 extension，不创建业务表。

## User Setup Required

None - 本地只需 Docker 与 Python 3.11，不需要云邮件账号或外部密钥。

## Verification Evidence

- `.venv/bin/python -m pytest tests/unit -q` → `18 passed`。
- `docker compose up -d --wait postgres postgres-test mailpit` → 三个服务均 `healthy`。
- 测试库 `CREATE EXTENSION vector` 与查询 → `0.8.6`。
- Mailpit `/api/v1/info` → `v1.30.6`。
- FastAPI `GET /api/v1/health` → `200 {"status":"ok","version":"v1"}`。
- 弱 production 配置构造 Settings → 启动前 `ValidationError`。

## Next Phase Readiness

- 01-02 可直接在真实 PostgreSQL 与现有 Session factory 上建立 Alembic 迁移基座。
- 无阻塞项；认证 schema、业务表和真实 MailProvider 按后续计划实现。

## Self-Check: PASSED

- 关键文件全部存在。
- `48bfddb`、`3214c80`、`3182fd8` 均可从 Git 历史解析。
- Task 1 目录契约、Task 2 单测与计划级 Docker/pgvector/Mailpit/FastAPI 验收全部通过。

---
*Phase: 01-engineering-auth-foundation*
*Completed: 2026-08-27*
