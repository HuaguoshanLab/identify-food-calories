---
phase: 06-user-dashboard-admin
verified: 2026-09-04T02:40:00Z
status: gaps_found
score: 51/54 plan must-have truths verified
overrides_applied: 0
gaps:
  - truth: "每个 /api/v1/admin/* 命令在读取或返回幂等重放前，重新从 PostgreSQL 校验当前 active admin role"
    status: failed
    reason: "目录 create、patch、publish、disqualify 在调用 require_role() 之前查询 command-key replay，并直接返回已有草稿或发布对象。已被降权但仍持有有效 JWT 的前管理员可用自己已知的幂等键绕过本次 DB-RBAC 检查，取得重放结果。"
    artifacts:
      - path: "backend/app/admin/service.py"
        issue: "create_catalog_draft（约 371 行）、patch_catalog_draft、publish_catalog_draft（约 571 行）和 disqualify_catalog_publication（约 616 行）均在 require_role() 前 early-return replay。"
    missing:
      - "将当前 active-admin DB-RBAC 检查移到所有 replay 查询与任何资源投影返回之前。"
      - "补充 normal-user 和已降权管理员使用既有 command key 重放四类目录命令时返回 403 的 service/API 回归测试。"
  - truth: "自动化经真实公开路径覆盖 dashboard、SSE、周复盘和后台拒绝/管理流"
    status: failed
    reason: "06-20 明确要求的两份 Playwright 资产及后台 runner 配置在仓库中不存在；因此不能把组件测试、浏览器观察或已有周复盘 spec 当作这两条 E2E 的通过。"
    artifacts:
      - path: "frontend/tests/e2e/records-dashboard.spec.ts"
        issue: "文件不存在。"
      - path: "admin-frontend/playwright.config.ts"
        issue: "文件不存在，admin-frontend 无法作为 Playwright 项目运行。"
      - path: "admin-frontend/tests/e2e/admin-management.spec.ts"
        issue: "文件不存在。"
    missing:
      - "为 records dashboard 建立真实公开 API、认证和 RuntimeConfig 准备路径的 Playwright spec。"
      - "为独立后台建立 Playwright 配置和 admin-management 真实管理/拒绝流程 spec。"
  - truth: "Phase 6 修改后用户端完整 Vitest 门禁保持通过"
    status: failed
    reason: "Phase 6 提交 f4b1c6e 修改了 PlanPage 的终态呈现，但没有同步旧的 PlanPage 测试期望；全量 frontend Vitest 现有 1 条失败。"
    artifacts:
      - path: "frontend/src/features/plans/components/PlanPage.tsx"
        issue: "06-06 将 PlanningStatus 改为 SafePlanningProgress 后，受控候选耗尽分支不再呈现既有测试要求的“暂时无法生成计划”标题。"
      - path: "frontend/src/features/plans/components/PlanPage.test.tsx"
        issue: "第 151 行仍断言该标题，运行时无法找到。"
    missing:
      - "明确保留该用户可见标题，或按经确认的新文案更新测试与其行为合同，使全量用户端门禁恢复通过。"
---

# Phase 6：用户看板与后台管理验证报告

**阶段目标：** 用户看懂历史摄入趋势，管理员可以安全维护 Agent 所依赖的数据和配置。

**验证结论：** `gaps_found`。核心产品闭环、迁移链、目录治理、运行诊断和文档均有代码证据；但目录命令可在重放幂等请求时绕过本次 DB-RBAC 检查，这是管理员安全边界的阻断缺口。此外，计划承诺的 Playwright 资产缺失，且 Phase 6 对规划页的修改造成全量前端测试回归。不能标记通过。

**验证模式：** 初次验证。没有既有 `06-VERIFICATION.md`，也没有可应用 override。

**MVP 元数据守卫：** ROADMAP 将本阶段标为 `mode: mvp`，但 `gsd-sdk query user-story.validate --story "用户看懂历史摄入趋势，管理员可以安全维护 Agent 所依赖的数据和配置。" --pick valid` 返回 `false`；该目标不是 `As a …, I want to …, so that …` 的用户故事。因此本报告不能伪装成符合 MVP User Flow Coverage 合同的形式验证，只能按 ROADMAP 的五条 success criteria 执行标准目标倒推。应由负责人用 `/gsd mvp-phase 6` 修正元数据或移除错误的 `mvp` 标记。

## 目标倒推与可观察事实

| # | 必须为真的事实 | 状态 | 直接证据 |
|---|---|---|---|
| 1 | 用户可查看今日/本周摄入、历史、趋势与周复盘。 | ✓ VERIFIED | `DashboardService` 按持久化 `consumed_local_date` 聚合并以签名 keyset 读取 history；Records 页严格消费 overview/history/weekly DTO。真实浏览器记录确认“白米饭 100 克”保存后显示 130 kcal、1 餐、趋势、history 与低覆盖周复盘。 |
| 2 | 独立后台只调用 `/api/v1/admin/*`；普通用户不能由前端取得后台数据，用户 H5 不承载后台页面。 | ✗ FAILED | 独立前端/H5 隔离均成立，但 `AdminService` 四类 catalog 命令在 `require_role()` 前直接返回 command-key replay。已降权的原管理员持有既有 key 时可绕过当前 PostgreSQL RBAC 检查，故“每个 admin API 都执行当前角色校验”不成立。 |
| 3 | 管理员可治理菜品、营养、来源、授权、版本并查看可读审计差异。 | ✓ VERIFIED | 草稿/预览/审核/发布/失格端点经 DB-RBAC、If-Match、幂等键和审计服务；发布创建 immutable snapshot，nutrition/planning 查询受 eligibility overlay 约束。真实后台已完成草稿→审核→发布。 |
| 4 | 管理员可查看运行、失败信息、工具/耗时/费用，而不取得原图、密钥、原文或思维链。 | ✓ VERIFIED | `/runs/metrics`、`/runs`、`/runs/{id}` 共用终态 UTC predicate；`AdminRunDetailResponse` 只含 allowlist 字段。真实后台 runs 列表与详情已确认，记录未出现餐食原文、Provider body、图片或密钥。 |
| 5 | README 有架构、状态、时序、启动/调试与可验证面试线索。 | ✓ VERIFIED | 根 README、三个子项目 README 和 `docs/learning/06-dashboard-admin.md` 均存在；文档链接到 API/service/repository/graph 与对应测试，也明确区分浏览器证据和未完成 E2E。 |
| 6 | 06-20 声明的 records dashboard 与独立后台真实 Playwright 管理/拒绝流程可自动运行。 | ✗ FAILED | 三个必需资产不存在：`frontend/tests/e2e/records-dashboard.spec.ts`、`admin-frontend/playwright.config.ts`、`admin-frontend/tests/e2e/admin-management.spec.ts`。 |
| 7 | Codex 内置浏览器已覆盖普通用户后台拒绝与过期会话拒绝。 | ? UNCERTAIN | `docs/verification/phase-06-browser-acceptance.md` 明确登记该拒绝矩阵尚未完成；后端 unit tests 覆盖了拒绝语义，但这不是浏览器验收。 |

**路线图成功条件：** 4/5 已支持；后台安全授权条件被 replay-before-RBAC 缺口阻断。  
**计划级 must-haves：** 51/54 已验证；2 项明确失败（RBAC replay 绕过、缺失 E2E 资产），1 项须人工复验（浏览器拒绝矩阵）。

## 关键工件与连接

| 工件 | L1/L2：存在且非 stub | L3：接线 | L4：数据流 |
|---|---|---|---|
| `backend/app/records/service.py` | ✓ ZoneInfo 校验、持久 local date、一次性回填与事务 rollback。 | ✓ records API 调用 service；保存只读取 `completed_validated` 报告。 | ✓ `MealRecord.consumed_local_date` 进入 dashboard SQL。 |
| `backend/app/dashboard/{api,service,repository}.py` | ✓ overview/history/weekly 实现非静态返回。 | ✓ router 在 `main.py` 注册，service 注入 planning 窄 port。 | ✓ SQL 先按 `user_id`、未删行、本地日过滤，再聚合/分页；目标只由 completion projection 返回。 |
| `backend/app/admin/{api,service,repository}.py` | ⚠️ RBAC、审计、目录、运行配置、runs API 均有实际实现，但 catalog replay 顺序有安全缺口。 | ⚠️ `/api/v1/admin/*` 路由→`AdminService`→repository；命令写审计并单次 commit；四类 catalog replay 却在 DB-RBAC 前返回。 | ✓ 当前角色、实体 revision、immutable publication/eligibility 和 run ledger 投影均来自 PostgreSQL；但 replay return 不应绕过角色投影。 |
| `frontend/src/features/records/*` | ✓ Zod client、今日卡、趋势、history、周复盘存在且 targeted tests 通过。 | ✓ `RecordsPage` 使用 dashboard/weekly client，Load more 使用服务端 opaque cursor。 | ✓ 真实保存记录经公开 API 显示在 Records；未发现客户端 profile 推导目标。 |
| `admin-frontend/src/*` | ✓ 独立入口、内存 token、guard、catalog/config/runs/audit/overview 页面存在。 | ✓ `main.tsx` 组合 BrowserRouter→QueryClientProvider→AdminAuthProvider；feature client 调 admin-only base。 | ✓ Guard probe 和每条后端 API 的 DB-RBAC 双层存在；401/403 清 session/Query cache。 |
| `backend/migrations/versions/0013_*`–`0019_*` | ✓ 七份实体迁移存在。 | ✓ `alembic heads` 输出唯一 `0019 (head)`。 | ✓ 静态元数据依次为 0013←0012、0014←0013、0015←0014、0016←0015、0017←0016、0018←0017、0019←0018。 |

## 数据流核验

1. **记录→看板：** `MealRecordService.confirm_from_completed_run()` 校验 IANA 时区，以 `consumed_at` 写 `consumed_local_date`；`SqlAlchemyDashboardRepository` 用该列、租户和软删过滤聚合；`RecordsPage` 严格解析后渲染。真实浏览器已完成这条链。
2. **目录→未来分析：** catalog draft 的 preview/diff 由服务端根据当前草稿计算；publish 生成 immutable publication，eligibility overlay 进入 nutrition/planning future-query；真实后台发布“白米饭”后，该 canonical name 能被公开分析命中并保存。
3. **后台授权→审计：** 请求的 JWT 只认证；多数 service 操作会由 `require_role` 重新读取数据库当前角色。每项变更在 service 事务中写 scalar before/after diff 与 reason；audit/runs 读取使用签名 cursor 和白名单 DTO。**反证：** catalog create/patch/publish/disqualify 的 replay 查询与早返回发生在该检查前，不能视作完整 RBAC 闭环。
4. **Agent 生命周期→H5：** 公共 SSE 仅输出 `safe-stream-stage.v1`、allowlist `stage` 与安全文案；前端本地 strict parser 映射阶段，未知事件变成通用可重试状态，不直接渲染 provider/state/reasoning。

## 自动化与行为检查

| 检查 | 实际结果 | 结论 |
|---|---|---|
| `backend: uv run pytest` Phase 6 targeted suite | 103 passed，3 skipped/9 errors；错误全部来自本会话未配置 `DATABASE_URL`/`TEST_DATABASE_URL` 的 PostgreSQL fixture，不是断言失败。 | 单元/API/fake/eval 有效；PostgreSQL 集成在当前环境 **未复验**。 |
| `backend: ruff` Phase 6 source/tests | PASS。 | 无 lint blocker。 |
| `backend: mypy app/dashboard app/admin` | FAIL，34 errors；其中 dashboard weekly-review typing、admin metrics `object`→`datetime`、以及既有 `app/memory/providers.py` 问题。 | ⚠️ 类型质量债务；不改变已观察到的运行闭环，但不能宣传完整 mypy 门禁通过。 |
| `frontend: phase-6 targeted Vitest` | 8 files / 21 tests PASS；typecheck、build PASS。 | UI-02/UI-03 目标组件证据有效。 |
| `frontend: npm test -- --run` | 25 files/138 tests PASS，`PlanPage.test.tsx` 1 FAIL。 | ✗ Phase 6 SSE 变更引入/暴露未闭合回归，见 gaps。 |
| `admin-frontend: npm test -- --run` | 8 files / 22 tests PASS。 | 后台组件与 DTO 边界有自动化证据。 |
| `admin-frontend: VITE_ADMIN_API_BASE_URL=/api/v1/admin npm run build` | PASS；静态扫描未找到 `frontend/src`、`localStorage`、`sessionStorage` 或 `indexedDB`。 | 独立构建与内存会话边界有效。 |
| `backend: APP_ENV=test uv run alembic heads/history` | PASS，唯一 `0019 (head)`。 | 0013–0019 迁移链有效。 |

## 真实浏览器证据与边界

已验证的真实公开路径（2026-09-04）包括：

- 普通用户：`/app/analyze` 完成受控目录分析→确认保存→记录详情→`/app/records`（今日、趋势、history、低覆盖周复盘）。
- 管理员：`/admin/catalog` 完成草稿→审核→发布；同一 SPA 会话验证 `/admin/runs` 最小详情和 `/admin/audit`。

这不是完整浏览器验收。尚未实测普通用户后台拒绝、过期会话、`/admin/overview` 与 UTC 深链接、runtime disable、catalog 失格后的历史 snapshot 稳定、跨日补记/cursor，以及周复盘 success/safety-abstain/retry 状态。详见 `docs/verification/phase-06-browser-acceptance.md`；该文件没有把它们伪装成通过。

## 需求可追溯性

| 需求 | 状态 | 证据 |
|---|---|---|
| UI-02 | ✓ SATISFIED（仍有 E2E gap） | dashboard 读模型、Records UI、facts-first weekly review、冻结 14-case eval、真实保存→Records 路径。 |
| UI-03 | ✓ SATISFIED | 安全 SSE DTO、后端 stage mapping、两个 H5 safe-progress 组件与 targeted tests。 |
| ADM-01 | ✗ BLOCKED | 独立后台和 memory-only UX guard 成立，但 catalog command replay 在 `require_role` 前返回，违反每次操作执行当前 PostgreSQL RBAC 的后端安全合同。 |
| ADM-02 | ✓ SATISFIED | draft/review/publish/disqualify、immutable publication 与 future eligibility SQL guard；真实 catalog 发布。 |
| ADM-03 | ✓ SATISFIED | metrics/list/detail 最小 DTO、相同 terminal predicate、runs 真实浏览器详情。 |
| ADM-04 | ✓ SATISFIED（浏览器禁用路径待验） | immutable non-secret runtime config、admission snapshot、环境-only resolver 与 service tests。 |
| ADM-05 | ✓ SATISFIED | append-only audit migration/trigger、reason、server scalar diff、cursor query 与真实 audit 页面。 |
| ARC-08 | ✓ SATISFIED | 同级独立 `admin-frontend/`、独立 lockfile/build、admin-only API base 与无用户 H5 import 扫描。 |
| EDU-02 | ✓ SATISFIED | README 架构/状态/时序、启动与调试命令，且对缺失 E2E 如实说明。 |
| EDU-03 | ✓ SATISFIED | 根 README 与 Phase 6 learning 文档给出可链接到源码/测试的面试深挖题。 |

## 反模式与反证检查

- 未发现 Phase 6 核心生产代码中的 `TODO`、`FIXME` 或 `XXX` 债务标记。
- **反证 1（部分满足）：** E2E 计划写了三类自动化真实路径，但 records-dashboard 与 admin-management 文件/runner 实际缺失。这不是“文档待补”，而是可观察的交付缺口。
- **反证 2（误导性成功测试）：** targeted SafePlanningProgress tests 通过，不能证明修改后的完整 Planning 页面仍满足既有终态文案合同；全量 Vitest 的失败已经证明这个覆盖缺口。
- **反证 3（未覆盖错误路径）：** 当前浏览器证据不覆盖普通用户/过期管理员拒绝、runtime disable 和 catalog 失格；必须按下方人工项复验。
- **反证 4（RBAC 顺序漏洞）：** `create_catalog_draft`、`patch_catalog_draft`、`publish_catalog_draft`、`disqualify_catalog_publication` 都在 `require_role()` 前接受 command-key replay 并返回对象；降权后的调用者可重放自己已知键。这是阻断项，不可降格为浏览器待验收。
- `mypy` 当前不通过属于 warning；它不是用“存在文件”代替功能验证的理由，也不能被 SUMMARY 的旧 PASS 声明覆盖。
- Phase 7 的“CI 运行 … Playwright E2E”只是一条通用质量目标，并未明确承接 `records-dashboard.spec.ts` 或 `admin-management.spec.ts` 的具体公开用户流；按保守 deferred 规则，这些仍是 Phase 6 明确计划的未交付项，未被转移。

## 人工/环境复验项

### 1. 后台拒绝与会话失效

**测试：** 以普通用户访问 admin，再让已登录管理员会话失效并访问 guarded 页面。  
**预期：** 普通用户固定拒绝；401/403 清内存 session 与 Query cache，不渲染旧后台数据。  
**原因：** 当前浏览器记录明确未覆盖此矩阵。

### 2. 后台运营命令

**测试：** 从 overview 点击带 UTC 参数的 runs 深链接；执行 runtime disable；对隔离测试 publication 执行失格，再检查未来使用被阻断而历史 MealRecord snapshot 不变。  
**预期：** 指标/list 时间窗一致；新调用被拒绝、旧快照保留；失格不篡改历史。  
**原因：** 需要真实管理员会话和受隔离数据，当前记录未覆盖。

### 3. 记录时间边界与周复盘分支

**测试：** 通过页面创建跨日补记并翻 history cursor；验证周复盘 success、safety-abstain 与 retryable 三种公开状态。  
**预期：** 本地日稳定、分页无漏重；建议只出现在安全 success 状态。  
**原因：** 当前真实路径仅有单条记录和低覆盖结果。

### 4. PostgreSQL 复验环境

**测试：** 使用受保护 `tests/run_pg.py --env-file .env.test.example` wrapper 重跑 dashboard/admin/records integration tests。  
**预期：** 测试数据库隔离且 integration 全部通过。  
**原因：** 本验证会话未提供 `DATABASE_URL` 与 `TEST_DATABASE_URL`，故拒绝猜测或连接开发库。

## Gaps Summary

Phase 6 的产品骨架不是 stub：代码、路由、DTO、迁移与部分真实浏览器成功链都存在。但是“核心功能存在”不等于“阶段完整”。首先，catalog command 的幂等重放发生在 DB-RBAC 前，破坏了“管理员可以安全维护数据和配置”的核心安全前提，必须先修复并加降权重放回归测试。其次，06-20 计划承诺的两组 Playwright 资产根本不存在；再次，06-06 改动后全量前端测试有实际失败。三项都必须闭合后，才可以重新进行无保留的阶段验证；其余浏览器/测试库复验项是明确登记的证据缺口，不能被现有成功路径抵消。

---

_验证人：gsd-verifier_  
_本报告未修改生产代码，也未采信 SUMMARY 作为完成证据。_
