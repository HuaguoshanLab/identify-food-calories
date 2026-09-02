---
phase: 05-diet-planning-subgraph
slug: diet-planning-subgraph
status: passed
threats_open: 0
asvs_level: 1
security_block_on: high
register_authored_at_plan_time: true
created: 2026-09-02
---

# Phase 5 — 安全威胁验证

> 审计范围：Phase 5 的十份计划威胁模型、十一份执行摘要、上下文、复验报告，以及 `aa55ccb` / `e95e1af` / `137a2b2` 的修复实现。实现文件全程只读。

## 审计结论

**33/33 已关闭。**

`T-05-30` 的计划缓解要求测试/浏览器产物使用合成数据，且 SUMMARY 不记录敏感值。测试现使用明确命名、与会话无关的合成普通成人 fixture；SUMMARY 和 verification 只描述该 fixture 类型，不再包含精确身体资料。2026-09-02 复审已对 Phase 5 工件和受影响 API 测试执行原会话资料组合扫描，未发现复现。

## 信任边界

| 边界 | 描述 | 跨越数据 |
|---|---|---|
| H5 / 公共 API → planning service | 用户身体资料、目标、偏好与调整文本进入服务端 | 敏感健康相关资料、自由文本 |
| planning graph → tool/service | 图只能请求确定性结果，不能成为营养数值或授权真相 | versioned targets、受控菜谱、校验结果 |
| repository / seed → 用户餐单 | 仅审核、合格、指定版本的菜谱可进入餐单 | recipe audit metadata、受控克数、营养目录引用 |
| checkpoint / event ledger → API / H5 | 内部运行状态必须经过闭合安全投影 | 安全业务阶段与餐卡字段 |
| tests / summaries / verification → 项目工件 | 测试资料和证据不得泄露真实健康资料 | 合成账号、合成身体资料、审计描述 |

## 威胁登记与验证

| Threat ID | 类别 | 组件 | 处置 | 状态 | 实现证据 |
|---|---|---|---|---|---|
| T-05-01 | Tampering | target input | mitigate | CLOSED | `backend/app/planning/schemas.py:68-105` 的 `extra=forbid`、枚举、范围和闭合 speed literal；`test_planning_profile_api.py:154-177` 断言未知/越权字段为 422 且不写入。 |
| T-05-02 | Elevation of privilege | health scope | mitigate | CLOSED | `service.py:65-95,343-358` 在目标/菜谱前 fail-closed；`test_diet_planning_agent_api.py:101-132` 断言拒绝且不保存 profile。 |
| T-05-03 | Information disclosure | target result | mitigate | CLOSED | `TargetCalculationResult` 仅含 action、版本、target 与安全文案；`graph.py:1147-1181` 仅投影目标范围、餐卡与免责声明。 |
| T-05-04 | Spoofing / Information disclosure | profile CRUD | mitigate | CLOSED | `planning/api.py:21-53` 全部从 `AuthenticatedPrincipal` 取 owner；`repository.py:33-40,68-71` SQL 的 `user_id` + `deleted_at` predicate；A/B API 合同在 `test_planning_profile_api.py:112-151`。 |
| T-05-05 | Tampering | profile persistence | mitigate | CLOSED | 闭合 Pydantic 写入 DTO 与 Service commit/rollback 在 `schemas.py:91-133`、`service.py:365-445`；无效写入不落库测试见 `test_planning_profile_api.py:154-177`。 |
| T-05-06 | Information disclosure | deleted data | mitigate | CLOSED | `repository.py:68-71` 隐藏 soft-delete；`planning/api.py:49-53` 归一 404；`test_planning_profile_api.py:145-151` 覆盖删除后读/改为 404。 |
| T-05-07 | Tampering | recipe metadata | mitigate | CLOSED | `repository.py:74-116` 同时要求 active、项目来源、许可、审核角色、catalog 和 recipe version；`importer.py:106-184` 校验后幂等导入并切换 active；`0012_activate_controlled_recipes_v2.py:18-31` 停用 v1 但不删除。 |
| T-05-08 | Information disclosure | third-party recipe content | mitigate | CLOSED | `schemas.py:191-235` 与 `repository.py:105-115` 只接受 project-authored / 固定许可 / approved 的短结构化 recipe；当前 seed 是仓库内 JSON，无抓取、正文、图片或购物单路径。 |
| T-05-09 | Tampering | nutrition totals | mitigate | CLOSED | `service.py:237-298` 用 qualified food ID + grams 逐食材重算；`service.py:108-181` 汇总实际三餐后才 PASS/REPLAN/RELAX；修复测试 `test_planning_service.py:310-363`。 |
| T-05-10 | Spoofing / Information disclosure | thread snapshot / resume | mitigate | CLOSED | `agent/api.py:76-89,145-180` 将 principal 传给每个 service 操作；`AgentService.latest_run_and_events()` 继续 tenant-filter；`test_diet_planning_agent_api.py:181-235` 断言 foreign 404。 |
| T-05-11 | Tampering | command / tool input | mitigate | CLOSED | `DietPlanningStartCommand` 与 `AgentInputRequest` 是 `extra=forbid`（`agent/schemas.py:31-50`）；`DietPlanningGraph` 只调用 typed `PlanningToolAdapter`（`graph.py:873-958`）。 |
| T-05-12 | Denial of service | graph loop | mitigate | CLOSED | 初始循环 `graph.py:906-963` 有 `replan_count < 3`；调整入口 `graph.py:973-1073` 第四次立即 `LIMIT_REACHED`；工具预算同文件 `1075-1118`。 |
| T-05-13 | Information disclosure | checkpoint / SSE | mitigate | CLOSED | `graph.py:1147-1181` 为 allowlist report；`agent/service.py:205-207,525-536` 只持久化安全投影；集成测试禁 provider/prompt/tool/cost/ID 字段，`test_diet_planning_agent_api.py:225-231,327-332`。 |
| T-05-14 | Tampering | form command | mitigate | CLOSED | 前端 Zod 严格解析与后端闭合 DTO 双边验证；`PlanPage.test.tsx:80-107` 只发送已显示且确认的值，服务端 422 contract 见 `test_planning_profile_api.py:154-177`。 |
| T-05-15 | Repudiation / Tampering | persistence intent | mitigate | CLOSED | `DietPlanningStartCommand.save_profile` 是显式布尔值；`graph.py:900-904` 仅 health guard 后才可保存；`test_diet_planning_agent_api.py:242-274` 断言未确认或未选择保存零写入。 |
| T-05-16 | Information disclosure | client state | mitigate | CLOSED | `frontend/src/features/plans/api/profile.ts:1-58` 仅用内存 `AuthenticatedRequest`；plans feature 的 `rg` 未发现 localStorage/sessionStorage，`PlanPage.test.tsx:109-132` 断言不渲染 provider/token/reasoning。 |
| T-05-17 | Tampering | feedback constraints | mitigate | CLOSED | `graph.py:973-1047` 将反馈收敛到有限 intent/slot，保留 preferences，`service.py:141-177` 在排除项、能量地板与比例失败时拒绝 RELAX。 |
| T-05-18 | Tampering / Repudiation | preference replay | mitigate | CLOSED | `graph.py:1049-1069` 使用 SHA-256 marker 防止同一 feedback 重放；typed capture 走既有 owner-scoped memory port；图/API 合同覆盖幂等写入。 |
| T-05-19 | Denial of service | replan loop | mitigate | CLOSED | `graph.py:906-963,973-1073` 的 durable count、第四次 hard guard 与 budget limit；`PlanPage.test.tsx:254-276` 断言客户端不再提交。 |
| T-05-20 | Information disclosure | adjusted report | mitigate | CLOSED | `graph.py:1029-1046` 仅投影 changed slot、range 和允许的 relaxation；API 测试明确禁止 raw feedback、ledger、provider、tool/reasoning，`test_diet_planning_agent_api.py:327-332`。 |
| T-05-21 | Information disclosure | profile client | mitigate | CLOSED | `profile.ts:1-58` 无 user ID / local storage，只用 authenticated request；服务器 SQL owner predicate 见 `repository.py:33-40,68-71`。 |
| T-05-22 | Tampering | profile write | mitigate | CLOSED | 资料页唯一 write transport 是显式 PUT/PATCH/DELETE（`profile.ts:34-58`）；PlanPage 预填不写入，`PlanPage.test.tsx:80-82` 断言零 profile/memory mutation。 |
| T-05-23 | Information disclosure | delete cache | mitigate | CLOSED | `PersonalProfilePage` 删除 mutation 设 cache 为 null 并 invalidate；服务端 soft-delete query filter 如上；组件/API 合同覆盖删除后 404 与不复活。 |
| T-05-24 | Information disclosure | status / UI | mitigate | CLOSED | `frontend/src/features/plans/api/schemas.ts` 以 Zod allowlist 解析 snapshot/event；`PlanPage.tsx:51-91` 仅将固定 event type 映射为固定中文文案。 |
| T-05-25 | Elevation of privilege | refusal UI | mitigate | CLOSED | `PlanPage.tsx:94-112` health refusal 不渲染餐卡、调整框或 bypass CTA；`PlanPage.test.tsx:109-132` 明确断言。 |
| T-05-26 | Tampering | displayed constraints | mitigate | CLOSED | `PlanPage.tsx:51-91` 只消费后端 report；前端不计算 exclusions，`RelaxationAlert` 显示“忌口和明确排除未放宽”。 |
| T-05-27 | Tampering | adjustment UI | mitigate | CLOSED | `PlanPage.tsx:71-91` 只提交 `{kind, text}` 到 owned thread；约束/health/relax 决策仍在 `service.py:108-181`。 |
| T-05-28 | Information disclosure | feedback rendering | mitigate | CLOSED | 前端从相邻安全快照推导旧菜名，不渲染原反馈；`PlanPage.test.tsx:167-222` 断言 provider 文本、checkpoint/thread/memory ID 不可见。 |
| T-05-29 | Denial of service | repeated adjustments | mitigate | CLOSED | `PlanPage.tsx:71-72` limit/refusal 时早退，后端 `graph.py:973-974` 仍是最终 hard cap。 |
| T-05-30 | Information disclosure | test / browser artifacts | mitigate | CLOSED | `test_diet_planning_agent_api.py:32-39` 的 `SYNTHETIC_ORDINARY_ADULT_PROFILE` 明确标记合成 fixture（149cm/71kg/61岁）；`05-11-SUMMARY.md:41` 与 `05-VERIFICATION.md:45,55` 只记录“合成普通成人”。复审对 Phase 5 工件和该 API 测试的原会话资料组合扫描无匹配，且该测试 5 passed。 |
| T-05-31 | Spoofing | E2E identity | mitigate | CLOSED | `frontend/tests/e2e/plans.spec.ts:8-70` 经公开注册、Mailpit 激活、登录进入页面；没有 forged token 或 direct DB。 |
| T-05-32 | Tampering | security regression | mitigate | CLOSED | `test_planning_profile_api.py:112-177` A/B、删除和 422；`test_diet_planning_agent_api.py:101-335` owner/idempotency/refusal；`test_agent_bootstrap.py` 隔离 PG 与 bootstrap。 |
| T-05-33 | Repudiation | documentation | mitigate | CLOSED | `docs/learning/05-diet-planning-subgraph.md:1-113` 明确普通饮食参考、拒绝范围、数据流和证据限制；无医疗疗效承诺。 |

## 已开放威胁

无。

## 未注册威胁标记

无。`05-09-SUMMARY.md` 唯一显式的 `## Threat Flags` 为 None；Plan 11 新增的版本化 seed、迁移和 bootstrap 已分别映射到 T-05-07、T-05-09、T-05-32。T-05-30 是已登记威胁的未落实缓解，不是 unregistered flag。

## 已接受风险

无。

## 验证执行记录

| 检查 | 结果 |
|---|---|
| `APP_ENV=test uv run pytest`（PlanningService、ProfileService、recipe importer、DietPlanningGraph） | **56 passed**，2026-09-02。 |
| 包含 PostgreSQL 的完整 target suite | 本机未提供 `TEST_DATABASE_URL`，4 个集成测试按配置 fail-closed；这证明测试不会回退开发库，但本次不能重新声称该四项通过。已有 `05-VERIFICATION.md` 记录隔离库通过证据。 |
| 静态实现审查 | owner predicates、closed DTO、guard、safe projection、版本选择和 loopback-only bootstrap 均在上述源码位置找到。 |
| T-05-30 复审扫描 | Phase 5 工件和受影响 API 测试均未发现原会话身体资料组合；API 正例 fixture 明确标为 synthetic。 |

## 安全审计轨迹

| 审计日期 | 范围 | 已关闭 | 开放 | 执行者 |
|---|---|---:|---:|---|
| 2026-09-02 | 初始 33 项威胁登记 | 33 | 0 | gsd-security-auditor |
| 2026-09-02 | T-05-30 修复复审：脱敏工件、synthetic fixture、组合扫描、隔离 API | 1 | 0 | gsd-security-auditor |

## Sign-off

- [x] 全部 33 项计划期威胁均有处置并逐项检查。
- [x] SUMMARY threat flags 已纳入映射。
- [x] 实现文件未修改。
- [x] `threats_open: 0` — 已满足。

**Approval:** passed — T-05-30 已基于合成 fixture、文档脱敏和组合值扫描关闭。
