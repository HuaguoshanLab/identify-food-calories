# Phase 6: 用户看板与后台管理 - Research

**Researched:** 2026-09-02
**Domain:** 用户摄入聚合、受限周复盘、营养目录治理、运行审计与独立管理员 SPA
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### 用户看板与时间口径

- **D-01:** `/app/records` 的首屏固定为“今日摄入摘要 → 本周趋势 → 按日期分组的历史餐食”；不新增底部 Tab 或独立用户端看板项目。
- **D-02:** 今日摘要展示总热量、蛋白质/脂肪/碳水相对个人目标区间的状态，以及当天已保存餐食数量；不得伪装为医学精度。
- **D-03:** 若用户没有完整个人资料或未生成饮食计划，只展示已确认的实际摄入，不显示或猜测目标对比。
- **D-04:** 所有趋势与周统计按用户实际用餐时间、用户本地自然日和自然周归档；补记的餐食必须回填到原用餐日期。

#### 周复盘与受限模型建议

- **D-05:** 周复盘默认展示本周（周一至今天），允许查看已结束的过去完整周。
- **D-06:** 复盘先给基于已保存餐食的客观汇总与可见模式，再给 1–3 条普通饮食参考建议；必须明确它仅根据已记录数据生成，且不构成医疗建议。
- **D-07:** 复盘永远展示数据覆盖范围（已记录天数和餐数）。记录不足时只能给已有汇总，禁止输出趋势判断或建议。
- **D-08:** 建议可由模型生成个性化自然语言，但模型只能接收后端已经计算、可追溯的聚合事实及安全约束；输出必须运行时校验，不得自行生成权威营养数字、医疗结论或思维链。

#### 营养目录版本治理

- **D-09:** 管理员对菜品、别名、每 100g 标准营养、来源和授权状态的改动必须经历“草稿 → 审核 → 发布新不可变版本”；新分析和新餐单只使用已发布的合格版本，历史餐食继续使用确认时快照。
- **D-10:** v1 的任意管理员均可创建、审核和发布目录版本；每一步必须记录操作者、时间、必填原因和字段级前后差异，不新增目录审核员角色或双人审批门槛。
- **D-11:** 已发布条目的授权撤销或关键营养数据失格后，必须立即禁止它进入后续分析和新餐单；不允许重算、覆盖或删除既有已确认的餐食快照。
- **D-12:** 发布前必须展示菜名/别名、每 100g 营养、来源链接、授权状态的字段级差异和受影响菜品数量；发布原因必填。后台主界面不以原始 JSON diff 代替人类可读预览。

#### 运行审计与模型配置

- **D-13:** Agent 运行审计默认展示近 24 小时总运行数、失败率、P50/P95 延迟和总估算费用，并提供可筛选的单次运行列表。
- **D-14:** 运行列表可按时间范围、运行状态、图版本、Provider/模型版本、失败节点和失败码筛选。运行详情只显示工具名称、耗时、费用、调用计数和安全摘要；禁止显示用户邮箱、原文、原图、完整 State 或模型思维链。
- **D-15:** 停用 Provider 时立即阻止新的模型调用和新运行；已经发出的调用依既有超时完成并完整记账，随后向用户返回安全、可重试的失败结果。不得硬中断为无法解释的半截状态。
- **D-16:** 模型版本、单次费用上限和周期费用上限由管理员填写原因并确认后，立即形成可追溯的配置版本，只影响其后启动的新运行；正在执行的运行按启动时配置快照完成。密钥永不读出、存入后台可见状态或回显。

#### 已继承且不可突破的边界

- **D-17:** 用户 H5 保持“分析、记录、计划、我的”四 Tab；后台必须是独立 `admin-frontend/`，后端 `/api/v1/admin/*` 的数据库权威 RBAC 是最终授权真相，前端隐藏菜单不能代替它。
- **D-18:** 所有用户可见流式进度和后台运行摘要只使用安全的业务阶段/摘要，不暴露 Provider 原文、内部节点细节以外的敏感状态、原图、密钥或完整模型推理。

### the agent's Discretion

- 确定本地时区来源、周起始日计算、趋势图具体类型、聚合 API 的分页和缓存策略，以及数据不足阈值；必须保持 D-01..D-07 的事实边界。
- 依据当前 Provider 与 Pydantic 官方资料，确定周复盘模型的结构化 DTO、提示词版本、允许建议类别、拒绝/降级策略、成本预算和输出校验；模型只能表达经批准的聚合事实。
- 确定目录草稿、版本、发布和失格的精确数据库 Schema、Alembic 拆分、幂等键、事务边界与并发控制；必须保留过去记录的快照稳定性和完整审计差异。
- 确定 `admin-frontend/` 的目录组织、独立 Vite 配置、路由守卫、TanStack Query 契约生成/验证和视觉组件细节，但不得复制用户 H5 或绕过公开 API。
- 确定运行指标的精确聚合窗口、P50/P95 算法、成本保留精度、运行详情分页和配置热加载策略；必须符合 D-13..D-16 及现有运行账本的安全数据最小化。

### Deferred Ideas (OUT OF SCOPE)

范围不包含医疗诊断或治疗、通用目标的伪造、展示原图/用户原文/密钥/完整 Graph State/模型思维链，亦不包含新的用户角色、复杂多级审批流、完整食谱或购物清单。
</user_constraints>

## Project Constraints (from AGENTS.md)

- 保持 `frontend/`、`backend/` 与新增同级 `admin-frontend/` 独立；禁止 Next.js、微服务、Kafka、Kubernetes，且后台不得塞入用户 H5。 [VERIFIED: codebase grep]
- 后端必须遵守 API → Service → Repository → Model；Graph 只能经 `agent/tools.py` 调用领域服务；ORM、HTTP Schema、Graph State、Provider DTO 必须分离。 [VERIFIED: codebase grep]
- PostgreSQL 是业务真相；所有持久化结构经 Alembic；确定性服务是营养、目标、聚合和校验的数值真相。 [VERIFIED: codebase grep]
- `/api/v1/admin/*` 每个端点都必须经数据库实时 RBAC；管理员变更在同一事务写审计；密钥、原图/base64、原文、完整 State、思维链不可记录或回显。 [VERIFIED: codebase grep]
- 新目录必须有职责、允许依赖和文件索引的 README；后端还要有中文教学文档；测试分别使用 fake repository、真实 PostgreSQL、HTTPX，以及 Fake Provider 的图行为测试。 [VERIFIED: codebase grep]
- 用户可见页面、图表、表单和跨栈路径除组件/API/Playwright 门禁外，必须通过产品真实页面和公开 API 的内置浏览器验收。 [VERIFIED: codebase grep]

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|---|---|---|
| UI-02 | 用户可查看今日/本周摄入、历史餐食、营养趋势和周复盘。 | 看板投影、IANA 时区、覆盖门槛、受限周复盘和 H5 验收路径。 [VERIFIED: codebase grep] |
| UI-03 | 流式状态清楚展示感知、等待补充、工具计算、校验和完成，但不暴露模型思维链。 | 复用安全业务阶段；周复盘只展示 facts/generating/validated/abstained。 [VERIFIED: codebase grep] |
| ADM-01 | `/admin` 仅管理员可访问，前后端同时执行 RBAC。 | 独立 SPA guard + 每个后端端点调用当前 DB role。 [VERIFIED: codebase grep] |
| ADM-02 | 管理员可管理菜品、别名、标准营养、来源、授权状态和数据版本。 | draft/review/publish 与 eligibility overlay 架构。 [VERIFIED: codebase grep] |
| ADM-03 | 管理员可查看 Agent 运行、失败节点、工具调用、费用与延迟，但看不到不必要的敏感原文或原图。 | 最小化审计 DTO、P50/P95 SQL、cursor 分页。 [VERIFIED: codebase grep] |
| ADM-04 | 管理员可启停模型 Provider、配置模型版本和费用上限，密钥不可在页面回显。 | 版本化非密钥配置与 run-start snapshot/admission gate。 [VERIFIED: codebase grep] |
| ADM-05 | 所有后台变更保存操作者、时间、前后值和原因。 | 服务器生成字段级 diff 的 append-only audit。 [VERIFIED: codebase grep] |
| ARC-08 | 管理后台使用独立 `admin-frontend/` React 项目，与 `frontend/`、`backend/` 同级并独立构建部署；后台与用户端共用 FastAPI，但后台权限始终由 `/api/v1/admin/*` 的后端 RBAC 强制执行。 | 独立 Vite SPA、独立 QueryClient/AuthProvider、共享公开 FastAPI 契约。 [VERIFIED: codebase grep] |
| EDU-02 | README 包含架构图、LangGraph 状态图、关键时序图、启动与调试命令。 | 最后一波补齐根/三端 README 的图和可运行命令。 [VERIFIED: codebase grep] |
| EDU-03 | 关键模块配套面试深挖题和可验证答案线索。 | 教学文档与 README 的问题/证据小节。 [VERIFIED: codebase grep] |
</phase_requirements>

## Summary

Phase 6 不应把“看板”实现为前端对全量记录的二次计算。现有 `GET /meal-records` 无分页且只返回逐条快照；`MealRecord` 已有 `consumed_at`、软删除与 `(user_id, consumed_at)` partial index，但尚无用户时区、聚合投影、周复盘或已成功生成餐单的持久事实。应新增受 records 所有的 dashboard 查询服务，数据库做时区归档和 `Decimal` 聚合，浏览器只绘制已验证投影。 [VERIFIED: codebase grep]

后台的关键不是页面，而是不可绕过的写入协议。现有 `NutritionCatalogVersion` 只有不可变内容 hash/released 时间，repository 直接挑每个 catalog 的最新版本；没有草稿、审核、发布指针、失格 overlay 或通用管理员审计。`AgentRun`/`AgentInvocation` 已保存版本、状态、调用数、延迟、费用和失败码，但没有管理员查询投影、配置版本快照或全局时间窗索引。直接在现有表上就地修改“已发布”行会破坏历史可追溯性。 [VERIFIED: codebase grep]

**主要建议：** 先交付数据库强制的 dashboard/目录/配置/审计协议，再接 H5 与独立 `admin-frontend`；周复盘是严格的、缓存的、最多两次调用的受限子图，低覆盖永不调用 Provider。 [VERIFIED: codebase grep]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| 本地日/自然周归档与营养求和 | Database / Storage | API / Backend | `timestamptz` 必须按明确 IANA zone 投影，`sum`、过滤和软删除必须在 tenant-filtered SQL 完成。 [CITED: https://www.postgresql.org/docs/current/functions-datetime.html] |
| 今日摘要、趋势与历史分页 API | API / Backend | Database / Storage | API 只投影确定性事实，避免 H5 拉全量记录并产生时区/精度漂移。 [VERIFIED: codebase grep] |
| 周复盘事实判断与安全弃权 | API / Backend | Database / Storage | 覆盖、模式、缓存键和健康边界必须在模型之前确定性执行。 [VERIFIED: codebase grep] |
| 周复盘自然语言 | API / Backend | Browser / Client | 本项目无 SSR；实际责任是后端有界 Graph/Provider 路径，客户端只显示安全结果。 [VERIFIED: codebase grep] |
| H5 可视化与日期选择 | Browser / Client | API / Backend | 图表只能呈现 Zod 已验证的聚合点，不可计算营养真相。 [CITED: https://zod.dev/basics] |
| 目录发布、失格和审计 | API / Backend | Database / Storage | 事务、锁、不可变版本和 DB-authoritative RBAC 不可放入 SPA。 [VERIFIED: codebase grep] |
| 管理路由守卫与部署入口 | Browser / Client | API / Backend | 独立 SPA 改善导航与部署隔离，但其 guard 只改善 UX，不能授予权限。 [VERIFIED: codebase grep] |
| Provider 准入、预算和运行配置快照 | API / Backend | Database / Storage | 已启动 run 必须保留启动快照；新 run 在调用前读取当前 enabled 配置。 [VERIFIED: codebase grep] |

## Standard Stack

### Core

| 库 / 技术 | 版本 | 用途 | 采用理由 |
|---|---:|---|---|
| React + TypeScript + Vite | Reuse `frontend` pins: React 19.2.8, Vite 8.2.2 | H5 和独立 admin SPA | 已被项目锁定；Vite `base` 可为独立部署路径重写构建资产 URL。 [VERIFIED: codebase grep] [CITED: https://vite.dev/guide/build] |
| React Router + TanStack Query + Zod | Reuse 7.18.2 / 5.102.6 / 4.4.3 | route/guard、查询缓存、响应校验 | Query key 应包含影响数据的所有变量；mutation 后按层级 key 精确失效；Zod `.parse()` 在边界拒绝错误响应。 [VERIFIED: codebase grep] [CITED: https://tanstack.com/query/latest/docs/framework/react/guides/query-keys] [CITED: https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation] [CITED: https://zod.dev/basics] |
| FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + PostgreSQL | Reuse backend lock | 公开 API、运行时 DTO、事务、迁移与聚合 | FastAPI dependency 适合在每个端点注入认证/授权 Service；Pydantic `extra='forbid'` 可拒绝未声明字段。 [VERIFIED: codebase grep] [CITED: https://fastapi.tiangolo.com/tutorial/security/get-current-user/] [CITED: https://pydantic.dev/docs/validation/latest/concepts/models/] |
| 原生 SVG + HTML 数据表 | Browser built-ins | 7 天营养趋势 | 本阶段只需小型、固定点数的趋势图；以可访问数据表为语义真相、SVG 为视觉增强，避免新增图表包与复杂 tooltip/zoom 状态。 [ASSUMED] |

### Supporting

| 库 / 技术 | 版本 | 用途 | 使用时机 |
|---|---:|---|---|
| `zoneinfo`（Python 标准库） | Python 3.12+ | 验证 IANA timezone 并计算本地日/周边界 | 所有 dashboard endpoint 与记录保存/编辑的时区输入。 [ASSUMED] |
| PostgreSQL `AT TIME ZONE`, `date_trunc`, `percentile_cont` | PostgreSQL 16 runtime | 本地日期/周边界、P50/P95 | `AT TIME ZONE` 可在带/不带时区表示间转换；`percentile_cont` 是连续分位聚合。 [CITED: https://www.postgresql.org/docs/current/functions-datetime.html] [CITED: https://www.postgresql.org/docs/current/functions-aggregate.html] |
| LangGraph + existing reasoning Provider/Fake | Locked backend packages | 有界周复盘 | 仅复用现有 Provider Port、ledger、checkpointer 和 Fake；不增编排框架或 SaaS tracing。 [VERIFIED: codebase grep] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|---|---|---|
| 原生 SVG + 可访问表 | Recharts | Recharts 有 responsive container，但本阶段的七点趋势不需要通用图表功能；当前 package legitimacy 工具无法对 npm registry 完成规定审计，故不引入新依赖。 [CITED: https://recharts.github.io/en-US/api/ResponsiveContainer/] [ASSUMED] |
| 数据库 dashboard 聚合 | 浏览器 `listMealRecords` 聚合 | 后者会读取无界历史、依赖浏览器时区且让 `Decimal`/软删除/覆盖计算分叉；禁止。 [VERIFIED: codebase grep] |
| 独立 `admin-frontend/` | 在用户 H5 增 `/admin` | 违反 D-17/ARC-08，并把桌面管理密度硬塞进 H5。 |

**安装：** 不新增直接依赖；`admin-frontend` 只复用已锁定的 React/Vite/Router/Query/Zod/Tailwind/shadcn Base UI/Lucide 依赖版本，并生成自己的 lockfile。 [VERIFIED: codebase grep]

## Package Legitimacy Audit

本阶段不推荐新增 npm/PyPI/crates 直接依赖，因此不执行新的包安装。`slopcheck` 已存在但其当前 `install` 子命令把 `recharts` 按 PyPI 包查询，且受限网络下无法访问 registry；它不能作为 npm 包的成功审计证据。若计划后来新增任何包，必须先用该生态的官方文档确认包名、对正确 registry 运行审计，并在实现前人工复核。 [VERIFIED: codebase grep]

## Architecture Patterns

### System Architecture Diagram

```text
H5 /app/records ──Bearer──> GET /api/v1/dashboard/overview
  │                                  │
  │ Zod-validated projection          ├─ validate IANA timezone / local week bounds
  ▼                                  ├─ records repository: active snapshots only
今日摘要 → 周趋势 SVG+表 → 历史 cursor └─ planning narrow port: target only if eligible
  │
  └─ GET /weekly-reviews/{week} ─> facts DTO ──low coverage──> summary + abstention
                                     │ sufficient
                                     ▼
                              bounded WeeklyReviewGraph
                                     │ (max 2 / 8 s / caps)
                                     ▼
                         Provider DTO validation + semantic gate
                                     │
                                     └─ safe response + minimal Agent ledger

admin-frontend ──Bearer──> /api/v1/admin/* ──> AdminService DB-role check
  │                                            ├─ catalog draft/review/publish transaction
  ├─ catalog diff / publish                        ├─ immutable published snapshot + eligibility overlay
  ├─ runs/metrics                                   ├─ AgentRun/Invocation minimal projection
  └─ provider config                                └─ configuration version + append-only audit
```

### Recommended Project Structure

```text
backend/app/
├── dashboard/                 # user-scoped aggregate/read + weekly-review service, schemas, ports, repository
├── admin/                     # admin HTTP/RBAC/audit; catalog/config/run query use cases
├── nutrition/                 # immutable published catalog and qualification read boundary
├── planning/                  # narrow target/recipe eligibility service boundary
└── providers/reasoning/       # weekly-review DTO/Port/DeepSeek/Fake extension only

frontend/src/features/records/
├── api/                       # dashboard + review schemas/client
└── components/                # summary, accessible trend, history, review

admin-frontend/
├── src/auth/                  # separate in-memory access-token bootstrap and admin route guard
├── src/features/catalog/      # draft/editor/review/publish
├── src/features/runs/         # metrics/list/detail filters
├── src/features/config/       # non-secret configuration versions
└── src/components/ui/         # only official Base UI primitives
```

Every newly created directory above must receive its own README and update its parent index in the same commit. [VERIFIED: codebase grep]

### Pattern 1: Freeze local-time attribution at record write

**What:** extend create/update record requests with a validated IANA `time_zone`; service derives and persists `consumed_local_date` and `consumed_time_zone` from `consumed_at`. Backfill existing rows using the one explicit dashboard timezone selected by the user, record a migration reason, then never recompute that record’s local-date attribution on a browser zone change. [ASSUMED]

**使用时机：** 每次保存/编辑餐食、看板分组和周复盘；使用 `consumed_at`，绝不使用 `created_at`。PostgreSQL 不会在 `timestamptz` 中保留输入的 timezone identifier，依赖之后的 session/browser zone 会让历史餐食跨日期移动。 [CITED: https://www.postgresql.org/docs/current/functions-datetime.html]

```sql
-- Query only user-owned, non-deleted immutable snapshots.
SELECT consumed_local_date,
       count(*) AS meal_count,
       coalesce(sum(energy_kcal), 0) AS energy_kcal,
       coalesce(sum(protein_g), 0) AS protein_g,
       coalesce(sum(fat_g), 0) AS fat_g,
       coalesce(sum(carbohydrate_g), 0) AS carbohydrate_g
FROM meal_records
WHERE user_id = :user_id
  AND deleted_at IS NULL
  AND consumed_local_date >= :week_start
  AND consumed_local_date < :week_end
GROUP BY consumed_local_date
ORDER BY consumed_local_date;
-- `sum` returns NULL on zero selected rows; coalesce deliberately defines API zeroes.
-- 来源: https://www.postgresql.org/docs/current/functions-aggregate.html
```

### Pattern 2: Facts-first weekly review

**What:** `DashboardService` deterministically emits `WeeklyAggregateFactsDTO`; only sufficient coverage may enter a one-step graph. Provider request/output, Graph State and HTTP DTO remain different models. [VERIFIED: codebase grep]

**Recommended threshold:** sufficient means at least **4 distinct local days and 8 saved meals** in the selected Monday–Sunday range; current week remains labelled “截至今天” rather than “完整周”. This is deliberately conservative product policy, not a clinical threshold. [ASSUMED]

```python
class WeeklyAggregateFactsDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    week_start: date
    week_end_exclusive: date
    coverage_days: int = Field(ge=0, le=7)
    meal_count: int = Field(ge=0)
    coverage_sufficient: bool
    totals: NutritionTotalsDTO
    allowed_patterns: tuple[WeeklyPattern, ...]
    facts_version: Literal["weekly-facts.v1"]

class WeeklyReviewOutputDTO(ProviderDTO):
    suggestions: list[SuggestionDTO] = Field(min_length=1, max_length=3)
    disclaimer: Literal["仅基于已记录数据，供一般饮食参考，不构成医疗建议。"]

    @model_validator(mode="after")
    def accepts_only_supported_safe_language(self) -> "WeeklyReviewOutputDTO":
        # Check categories are in facts.allowed_patterns; reject numbers, medical,
        # restrictive/self-harm language, duplicate categories, and extra/reasoning fields.
        return self
```

`extra='forbid'` rejects unrecognised fields, but schema shape is not semantic safety: plan a separate validator for allowed category/facts linkage, disclaimer, prohibited claims and retries. [CITED: https://pydantic.dev/docs/validation/latest/concepts/models/]

### Pattern 3: Immutable catalog snapshot plus mutable eligibility overlay

**What:** keep published catalog/version/food/source/alias/nutrient rows immutable. Draft data lives in a separate mutable change-set/draft graph; review freezes a candidate hash; publish copies it once into a new published version and atomically advances the active-publication pointer. `CatalogItemEligibility` is an append-only status history with a single active projection for post-publication authorization withdrawal/critical nutrient disqualification. [ASSUMED]

**Why:** D-11 requires immediate exclusion for new work without rewriting the version that explains old records. Existing repository currently chooses each catalog’s newest version and filters `is_qualified`; changing that field in place would mutate the historical source. [VERIFIED: codebase grep]

**Transaction:** `SELECT ... FOR UPDATE` the catalog publication row (or an advisory lock per catalog), recompute server-side field diff/count/content hash, assert `draft_revision`/idempotency key, insert version/items/aliases/sources, write audit, advance pointer, commit once. A second publish of the same key returns the existing immutable result. [ASSUMED]

### Pattern 4: Configuration version is a non-secret admission policy

**What:** keep keys/endpoints only in environment-backed provider factories. Store an immutable `AgentRuntimeConfigVersion` with enabled boolean, provider key, allowlisted model alias, price snapshot reference, per-run/period caps, effective time, actor/reason and version; store its ID and copied numeric limits on every run at admission. [ASSUMED]

**Critical gap:** `Settings` and `DeepSeekReasoningModelProvider` currently read model/price from environment and hard-require `deepseek-v4-flash`; an admin form cannot satisfy D-16 until a server-side allowlist/resolver is added. Never accept arbitrary provider endpoint or key from the form. [VERIFIED: codebase grep]

**Stop semantics:** provider disable/config change blocks admission of *new* model invocation/run after commit; already dispatched calls are not cancelled, wait to their existing timeout, write usage/failure, then return the safe retryable result. [VERIFIED: codebase grep]

### Pattern 5: Admin read API uses keyset paging and minimal projections

**What:** run list filters use validated query DTOs and `(created_at DESC, id DESC)` opaque cursor; details join only `AgentRun` and `AgentInvocation` safe fields. Metrics use the same terminal-run filter and time window as the list. [ASSUMED]

```sql
SELECT count(*) AS run_count,
       avg(CASE WHEN status IN ('failed', 'limit_reached') THEN 1 ELSE 0 END) AS failure_ratio,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY elapsed_ms) AS p50_ms,
       percentile_cont(0.95) WITHIN GROUP (ORDER BY elapsed_ms) AS p95_ms,
       coalesce(sum(estimated_cost_usd), 0) AS total_cost_usd
FROM agent_runs
WHERE created_at >= :start AND created_at < :end
  AND status IN ('completed', 'failed', 'limit_reached');
-- 来源: https://www.postgresql.org/docs/current/functions-aggregate.html
```

Add a migration-owned admin index beginning with `created_at` plus `id`; add only measured filter composites after `EXPLAIN (ANALYZE, BUFFERS)`, not speculative indexes. [ASSUMED]

### 数据/API 契约建议

| Endpoint | Request | Safe response / rule |
|---|---|---|
| `GET /api/v1/dashboard/overview` | `week_start`, validated IANA zone or persisted setting | `today`, seven ordered `daily_points`, target status only when a completed planning eligibility fact exists, coverage, cursor-free first history page. [ASSUMED] |
| `GET /api/v1/dashboard/history` | `before` opaque cursor, bounded `limit` | date-grouped `MealRecordSummary`; preserve record detail endpoint for item list. [ASSUMED] |
| `GET /api/v1/dashboard/weeks/{monday}` | IANA zone is server-validated | deterministic facts/summary plus cached safe review or abstention; no raw model output. [ASSUMED] |
| `POST /api/v1/admin/catalog-drafts` / `PATCH` | typed draft patch, `If-Match` revision, reason | mutable draft only; API calculates diff, never trusts client diff. [ASSUMED] |
| `POST /api/v1/admin/catalog-drafts/{id}/review` / `publish` / `disqualifications` | reason + command/idempotency key | state transition/audit and immutable publication or immediate future-use block. [ASSUMED] |
| `GET /api/v1/admin/runs`, `/metrics`, `/{id}` | strict filters and opaque cursor | only IDs, versions, state, node/tool name, duration, calls, cost, failure code, safe summary. [ASSUMED] |
| `GET/POST /api/v1/admin/runtime-configs` | no secret fields; non-empty reason, confirmation/idempotency key | active config summary/version and immutable audit; key/endpoint/provider body never serializes. [ASSUMED] |

### Anti-Patterns to Avoid

- **在 H5 以 `new Date()` 聚合所有历史：** 会产生时区、精度、软删除和无界传输错误；服务端聚合才是唯一投影。 [VERIFIED: codebase grep]
- **以 `created_at` 归档补记：** 直接违反实际用餐时间回填。
- **更新已发布 catalog item 的营养/授权列：** 会改写过去版本；改为新发布版本或 eligibility overlay。 [VERIFIED: codebase grep]
- **只在 `admin-frontend` 隐藏菜单：** 当前 JWT role claim 本身不是最终授权；每个端点必须重读数据库角色。 [VERIFIED: codebase grep]
- **审计存完整 JSON payload/Provider body：** 会把敏感健康数据和密钥带入后台；只白名单安全字段并存 hash/digest。 [VERIFIED: codebase grep]
- **按 offset 翻 Agent run：** 时间范围变化会造成重复/漏项；使用稳定 keyset cursor。 [ASSUMED]

## Don't Hand-Roll

| 问题 | 不要自建 | 改用 | 原因 |
|---|---|---|---|
| 数值营养、目标区间和覆盖事实 | 前端公式或模型数值结论 | `records` 聚合 + existing deterministic nutrition/planning services | 已有 `Decimal` 快照、确定性营养/目标工具和版本字段。 [VERIFIED: codebase grep] |
| 认证/权限 | 新 token/localStorage 或仅前端 guard | existing AuthProvider + FastAPI auth + `AdminService.require_role` | access token 已被约束为内存、refresh 为 HttpOnly Cookie，admin role 当前 DB 读取。 [VERIFIED: codebase grep] |
| 分位数 | Python 拉全量排序 | PostgreSQL `percentile_cont` | 数据库提供 ordered-set percentile；避免转移全表数据。 [CITED: https://www.postgresql.org/docs/current/functions-aggregate.html] |
| diff | 浏览器提交 raw JSON patch/diff | server-side typed before/after projection + field diff | 防止伪造审计、漏字段和 secret 回显。 [ASSUMED] |
| 周复盘 | 自由聊天、RAG 或第二条 Provider 通路 | existing LangGraph/Provider/Fake/ledger + constrained DTO | AI-SPEC 已冻结两次/8 秒/最小化/安全弃权合同。 [VERIFIED: codebase grep] |

**关键洞见：** 此阶段真正复杂的是历史和授权协议；看起来简单的图表或 CRUD 如果绕过这些协议，就是不可审计的数据污染。 [ASSUMED]

## Common Pitfalls

### Pitfall 1: 历史时区漂移
**问题：** 用户旅行或浏览器时区变化后，同一 `timestamptz` 被归入不同“今天/本周”。
**根因：** 当前 `MealRecord` 只有 `consumed_at`，没有原始 IANA zone/local date。 [VERIFIED: codebase grep]
**规避：** 写入/编辑时冻结 `consumed_local_date` 与 zone；dashboard 按冻结日期查询；migration 明确记录既有行 backfill 规则。 [ASSUMED]
**预警信号：** 测试把一条靠近 UTC 午夜的记录从 `Asia/Shanghai`/`America/Los_Angeles` 切换后落到不同日期。 [ASSUMED]

### Pitfall 2: 目录“发布”只是改了 live row
**问题：** 新营养值反向改变历史复盘或餐单来源。
**根因：** 当前 `is_qualified` 和“latest version”查询不足以表达发布/撤销。 [VERIFIED: codebase grep]
**规避：** immutable published rows + active publication pointer + future-use eligibility overlay；recipe 查询同时检查 ingredient eligibility。 [ASSUMED]
**预警信号：** 发布/失格后既有 `MealRecord.energy_kcal` 或 catalog version 发生变化。 [VERIFIED: codebase grep]

### Pitfall 3: Provider 配置看起来已切换，实际仍读环境
**问题：** 管理 UI 显示新模型/上限，运行仍用 startup Settings。
**根因：** 当前 provider factory 把 model/prices 固定从 `Settings` 注入。 [VERIFIED: codebase grep]
**规避：** admission 时读 DB active config、校验 allowlist、把版本和上限 snapshot 到 run/invocation；密钥留在环境。 [ASSUMED]
**预警信号：** 管理配置版本与 `AgentRun.model_version`/费用快照不一致。 [ASSUMED]

### Pitfall 4: P95 与失败率口径不一致
**问题：** 指标卡、列表和告警得到不同数字。
**根因：** 一个查询包含 `accepted/running`，另一个只含终态，或 UTC/本地边界不一致。 [ASSUMED]
**规避：** 固定“start inclusive/end exclusive、terminal status、UTC created_at”指标合同；在一个 repository 方法中复用 SQL fragments。 [ASSUMED]
**预警信号：** 24 小时指标与无筛选列表条目数无法对上。 [ASSUMED]

### Pitfall 5: 把 schema 校验误认为 AI 安全
**问题：** JSON 是合法的，文本仍可编造数字或给医疗/限制性建议。
**根因：** Pydantic 只保证结构/约束，不能自动证明事实忠实或健康安全。 [CITED: https://pydantic.dev/docs/validation/latest/concepts/models/]
**规避：** coverage gate 在调用前；输出类别必须是 facts approved pattern；文本走禁止数字/医疗/限制性词与重复检查；一次校正后弃权。 [VERIFIED: codebase grep]
**预警信号：** low coverage 有 Provider 调用，或 ledger/response 出现 `reasoning`/自由文本字段。 [VERIFIED: codebase grep]

## 代码示例

### 端点级数据库权威 RBAC

```python
# Every /api/v1/admin/* route receives an authenticated session, then checks
# the active role from PostgreSQL before loading any domain data.
def require_admin(principal: AuthenticatedPrincipal,
                  admin_service: AdminService = Depends(get_admin_service)) -> uuid.UUID:
    admin_service.require_role(user_id=principal, required_role=UserRole.ADMIN)
    return principal

@router.get("/runs", response_model=AdminRunPage)
def list_runs(admin_id: Annotated[uuid.UUID, Depends(require_admin)], ...):
    return service.list_runs(...)
```

The local `/admin/probe` already establishes this DB-role pattern; reuse it rather than inventing a second authorization scheme. [VERIFIED: codebase grep] FastAPI supports route dependencies to inject a current-user dependency. [CITED: https://fastapi.tiangolo.com/tutorial/security/get-current-user/]

### Frontend query keys and mutation invalidation

```tsx
const overviewKey = (weekStart: string) => ['records-dashboard', { weekStart }] as const

const overview = useQuery({
  queryKey: overviewKey(weekStart),
  queryFn: () => getDashboardOverview(request, { weekStart }),
  staleTime: 30_000,
})

const publish = useMutation({
  mutationFn: publishCatalogDraft,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin', 'catalog'] }),
})
```

Variables that change a fetch belong in the query key; invalidation marks matching queries stale and refetches active ones. [CITED: https://tanstack.com/query/latest/docs/framework/react/guides/query-keys] [CITED: https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation]

## 当前演进

| 旧做法 | 当前做法 | 变更阶段 | 影响 |
|---|---|---|---|
| `listMealRecords` loads every active record and H5 groups dates | Dedicated cursor-paged deterministic dashboard projection | Phase 6 | Prevents unbounded history transfer and makes local-week facts authoritative. [VERIFIED: codebase grep] |
| `NutritionCatalogVersion.released_at` implies current data | Explicit immutable published version plus active eligibility | Phase 6 | Separates publication from withdrawal without changing historical snapshots. [ASSUMED] |
| Startup environment Settings are the only provider configuration | DB config version admitted per new run; secret remains environment-only | Phase 6 | Enables D-15/D-16 without secret leakage or retroactive run changes. [ASSUMED] |

## 假设日志

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | Freeze `consumed_local_date`/IANA zone at record save and backfill legacy rows once. | Pattern 1 | Historical date assignment may need a user-confirmation UX/migration policy. |
| A2 | Coverage threshold is ≥4 distinct days and ≥8 meals. | Pattern 2 | Product may consider it too strict/lenient; it must be frozen in fixtures. |
| A3 | A seven-point native SVG with semantic table is sufficient, so no chart dependency is needed. | Standard Stack | Visual/product requirements may later need a full chart library. |
| A4 | Use catalog draft tables, immutable published snapshots and eligibility overlay rather than mutable published rows. | Pattern 3 | Existing importer/recipe relationships may make migration larger than estimated. |
| A5 | Add a completed-planning eligibility fact; profile alone cannot prove D-03. | Summary/API contract | Requires a small Phase-5-domain extension or authoritative derived projection. |
| A6 | Cursor pagination and proposed admin index shape meet expected audit scale. | Pattern 5 | Need production query plans/data volume before optimizing further. |

## 未决问题

1. **既有记录如何确定其首次本地时区？**
   - 已知：现有 `MealRecord` 保存 aware `consumed_at`，未保存 IANA timezone/local date。 [VERIFIED: codebase grep]
   - 未知：历史行没有可恢复的“当时所在地”。
   - **RESOLVED：** 添加用户级 IANA dashboard timezone 偏好。首次已有记录的用户必须确认浏览器提议的 IANA zone 后才回填；以确认 zone 对 consumed_at 计算 consumed_local_date，记录 local_date_source='confirmed_timezone_backfill'、规则与审计。不得声称恢复历史所在地。
2. **“已生成饮食计划”应由何处作为 D-03 的权威事实？**
   - 已知：`PlanningProfile` 有资料/目标，但当前没有持久的完成计划实体。 [VERIFIED: codebase grep]
   - 未知：仅 profile 是否足够表示用户实际完成过计划。
   - **RESOLVED：** 饮食规划图成功产生并校验完成报告时，在同一业务事务写入用户绑定、可撤销的 PlanningCompletionProjection，含完成 run/thread、目标/profile revision、completed_at。profile/目标删除或版本失效撤销资格；dashboard 只经窄 port 读取，绝不从 profile 猜测。
3. **周复盘配置是否共享既有 AgentRun，还是增加类型/关联？**
   - 已知：ledger 可存 graph/prompt/tool/model/version/成本，但缺少 `config_version` 和 review facts digest 专用列。 [VERIFIED: codebase grep]
   - **RESOLVED：** 新增最小 WeeklyReviewResult/等价领域表，唯一键为 (user_id, week_start, facts_digest, graph_version, prompt_version, schema_version, runtime_config_version)。只存语义校验后的安全用户可见建议/弃权码、版本、result digest 和关联 AgentRun；不存 prompt、原文 facts、provider body 或 reasoning。相同键并发复用/等待同一结果，cache hit 零 Provider 调用；任一版本/facts 变化自然失效；OUTCOME_UNKNOWN 绝不重放。

## 环境可用性

| Dependency | Required By | Available | Version | Fallback |
|---|---|---:|---|---|
| Node.js | 两个 Vite SPA | ✓ | v22.23.2 | — [VERIFIED: codebase grep] |
| npm | 前端依赖/构建 | ✓ | 10.9.8 | — [VERIFIED: codebase grep] |
| `uv` | backend test/build | ✓ | 0.12.7 | — [VERIFIED: codebase grep] |
| Docker | 真实 PostgreSQL integration/E2E environment | ✓ | 29.4.0 | — [VERIFIED: codebase grep] |
| Python runtime on PATH | Backend contract specifies 3.12+ | ✗ | 3.9.6 | `uv` must select project Python 3.12+; do not run backend directly with this interpreter. [VERIFIED: codebase grep] |
| `pg_isready` / confirmed running PostgreSQL | 聚合、迁移、integration tests | ✗ | — | start project Docker Compose; no SQLite fallback. [VERIFIED: codebase grep] |

**缺少且无替代的依赖：** 已确认运行的 PostgreSQL（真实 repository integration 不得降级 SQLite）。 [VERIFIED: codebase grep]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | yes | existing Bearer session validation; access token only in memory and refresh token HttpOnly. [VERIFIED: codebase grep] |
| V3 Session Management | yes | admin SPA must use same refresh/bootstrap flow and clear in-memory token on 401. [VERIFIED: codebase grep] |
| V4 Access Control | yes | every `/api/v1/admin/*` endpoint calls DB-current `AdminService.require_role`; SQL filters user dashboard by owner. [VERIFIED: codebase grep] |
| V5 Input Validation | yes | Pydantic/Zod `extra='forbid'`, bounded filters/cursors/IANA timezone/If-Match revision. [CITED: https://pydantic.dev/docs/validation/latest/concepts/models/] |
| V6 Cryptography | yes | reuse existing token/key handling and one-way hash/digest; never implement custom encryption/secret display. [VERIFIED: codebase grep] |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---|---|---|
| Forged/stale admin role claim | Elevation of privilege | Revalidate active role from PostgreSQL per admin request; test forged admin JWT and demotion after token issuance. [VERIFIED: codebase grep] |
| Catalog publish race / replay | Tampering | row/advisory lock, If-Match revision + idempotency key, one transaction including audit/pointer. [ASSUMED] |
| Sensitive runtime detail exposure | Information disclosure | response DTO whitelist; no email, raw text/image, provider body, full state, reasoning, key or endpoint. [VERIFIED: codebase grep] |
| Provider stop or budget race | Denial of service / repudiation | admission lock/config snapshot; no unknown-outcome replay; complete ledger accounting. [VERIFIED: codebase grep] |
| Cross-user dashboard read | Information disclosure | `user_id` predicate inside SQL repository, not post-load UUID comparison. [VERIFIED: codebase grep] |

## 计划波次与验证策略

| Wave | Deliverable | Dependencies / exit evidence |
|---|---|---|
| 0 | Documentation skeleton and DB foundations: timezone attribution/backfill, dashboard aggregate read port, planning-completion fact, catalog draft/publication/eligibility/audit/config/run metadata migrations. | Alembic upgrade from empty DB; real PostgreSQL constraints, backfill and lock/concurrency tests. [ASSUMED] |
| 1 | Deterministic dashboard APIs plus admin domain APIs/RBAC/audit/run metrics; repository indexes and cursor DTOs. | fake-repository service tests, HTTPX 401/403/tenant/filter/cursor tests, PostgreSQL aggregate/P50/P95/soft-delete tests. [VERIFIED: codebase grep] |
| 2 | Weekly-review graph/Provider/Fake extension and frozen 14-case synthetic eval set required by AI-SPEC. | low coverage = 0 calls; facts/output minimization; ≤2 calls, 8 s/cost/disable/unknown outcome safe abstention. [VERIFIED: codebase grep] |
| 3 | H5 records dashboard and independent `admin-frontend`, each with README, Zod clients, Query keys, local states and route guards. | Vitest/Testing Library/MSW; admin ordinary-user forbidden UI; no user-H5 admin route. [VERIFIED: codebase grep] |
| 4 | Cross-stack regression, docs/teaching, README diagrams/debug/interview evidence and real browser acceptance. | Playwright plus Codex browser through public APIs; no DB/token seeding. [VERIFIED: codebase grep] |

### 浏览器验收路径

1. 注册、邮件验证、登录真实用户；保存含接近午夜和补记日期的餐食，进入 `/app/records`，验证“今日→本周→历史→周复盘”的顺序、四 Tab 未变、320/430/desktop container 无横向滚动。 [VERIFIED: codebase grep]
2. 无记录、低覆盖、加载失败、完整历史长列表、已完成周和本周各走一次；低覆盖必须只显示覆盖/汇总和“无建议”，不能显示模型内容。 [ASSUMED]
3. 用真实管理员登录独立 admin SPA，确认普通用户/过期会话被拒绝；创建草稿、检查人类可读 diff、审核、发布，再失格一项，确认新分析/新餐单不可用而历史餐食值不变。 [ASSUMED]
4. 过滤后台 runs，核对 24h metrics 与列表口径；查看详情确认仅有最小字段；更改非密钥配置并验证新 run snapshot、已启动 run 不被改写。 [ASSUMED]

## Sources

### Primary (HIGH confidence)
- [PostgreSQL date/time functions](https://www.postgresql.org/docs/current/functions-datetime.html) — `AT TIME ZONE`、明确 `date_trunc` timezone 参数。
- [PostgreSQL aggregate functions](https://www.postgresql.org/docs/current/functions-aggregate.html) — `sum` 空集行为、`percentile_cont`。
- [FastAPI current-user dependencies](https://fastapi.tiangolo.com/tutorial/security/get-current-user/) — dependency-injected authentication pattern。
- [Pydantic models](https://pydantic.dev/docs/validation/latest/concepts/models/) — `extra='forbid'` 与运行时模型验证边界。
- [TanStack Query keys](https://tanstack.com/query/latest/docs/framework/react/guides/query-keys) and [invalidation](https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation) — cache key 与 mutation invalidation。
- [Vite build guide](https://vite.dev/guide/build) — independent deployment public base path。
- Codebase: `backend/app/records`, `nutrition`, `planning`, `agent`, `admin`; `frontend/src/features/records`; package manifests and integration/E2E tests. [VERIFIED: codebase grep]

### Secondary (MEDIUM confidence)
- [Recharts ResponsiveContainer docs](https://recharts.github.io/en-US/api/ResponsiveContainer/) — alternative responsive chart capability; not adopted.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all recommended runtime libraries already pinned; no new package is proposed. [VERIFIED: codebase grep]
- Architecture: HIGH — codebase gaps and PostgreSQL/HTTP contracts directly support the recommended boundaries. [VERIFIED: codebase grep]
- Pitfalls: HIGH — timezone, mutable catalog, configuration and ledger gaps are directly observable; exact thresholds/DB shape remain documented assumptions. [VERIFIED: codebase grep]

**Research date:** 2026-09-02
**Valid until:** 2026-10-02 for stable PostgreSQL/FastAPI patterns; recheck packages before any new dependency install.
