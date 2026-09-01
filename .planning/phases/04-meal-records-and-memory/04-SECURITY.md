---
phase: 4
slug: meal-records-and-memory
status: verified
threats_open: 0
asvs_level: 1
created: 2026-09-01
---

# Phase 4 — Security

> 审计范围仅限 04-01～04-07 的计划威胁模型；审计核验当前实现、自动化测试和 04-UAT 的真实浏览器路径。

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| 浏览器 → Public API | 已认证 H5 只经公开 HTTP DTO 管理记录与偏好 | 用户身份、餐食时间、白名单偏好 |
| Graph → typed tool | 图不直接访问 ORM 或 Provider | fresh 文本摘要、受限 capture 指令 |
| Service → PostgreSQL | 本地账本是 tenant 授权与删除真相 | 用户 scope、快照、outbox 状态 |
| Worker → Mem0 | 外部 memory 仅在 durable intent 后调用 | canonical text、opaque request key、用户 scope |
| Checkpointer / retrieval | 短期图状态与个人检索必须隔离 | thread ID、安全上下文摘要 |

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-04-01-01 | Spoofing | meal records | mitigate | 完成 run 同时按 thread、owner、completed 校验；服务端构造快照；双用户 PG 测试 | closed |
| T-04-01-02 | Tampering | meal records | mitigate | `(user_id, source_run_id)` / command key 幂等约束与重放复用 | closed |
| T-04-01-03 | Tampering | nutrition history | mitigate | 保存 item/totals/version 快照，编辑不重算历史 | closed |
| T-04-01-04 | Tampering | record deletion | mitigate | soft delete 只影响 record/items，不删除 Agent thread | closed |
| T-04-02-01 | Elevation | memory ledger | mitigate | 所有 memory 操作先以 id、user、active、deleted 本地授权 | closed |
| T-04-02-02 | Tampering | memory creation | mitigate | 类别白名单；推测必须确认才可外呼 Provider | closed |
| T-04-02-03 | Tampering | memory deletion | mitigate | 同事务先停用本地检索，再创建/取消 durable outbox | closed |
| T-04-02-04 | Information disclosure | memory config/API | mitigate | 生产 Mem0 配置 fail-closed；安全 DTO 排除外部 ID 与原文 | closed |
| T-04-03-01 | Information disclosure | personal retrieval | mitigate | SQL 强制 owner 与 active/deleted 条件；真实 PG 零跨用户召回测试 | closed |
| T-04-03-02 | Tampering | retrieval query | mitigate | 第一版关系 SQL tenant 查询，不做 ANN 后 Python 过滤 | closed |
| T-04-03-03 | Tampering | nutrition calculation | mitigate | 上下文仅为 hint；营养仍只由 calculate/validate 工具决定 | closed |
| T-04-03-04 | Tampering | checkpointer | mitigate | 两次打开真实 AsyncPostgresSaver，以同一 thread 恢复 | closed |
| T-04-04-01 | Tampering | H5 record save | mitigate | client 只提交 thread/command/time；后端 schema 禁止伪造 totals | closed |
| T-04-04-02 | Tampering | H5 deletion | mitigate | records/memories 都需 AlertDialog 确认；UAT 验证删除路径 | closed |
| T-04-04-03 | Tampering | H5 data state | mitigate | 仅调用认证公开 API；固定空态，无示例或伪造数据 | closed |
| T-04-04-04 | Information disclosure | H5 DTO | mitigate | strict Zod 白名单与公开 A/B 用户隔离验证 | closed |
| T-04-05-01 | Tampering | direct preference capture | mitigate | 仅确定性一人称 allowlist，经 typed Graph tool | closed |
| T-04-05-02 | Repudiation | provision ledger | mitigate | source run、request-key digest 与 pending intent 持久化 | closed |
| T-04-05-03 | Tampering | Mem0 direct write | mitigate | user-scoped exact resolve、`infer=False`、单 ID fail-closed | closed |
| T-04-05-04 | Information disclosure | Graph/API state | mitigate | state 只留 marker/digest；DTO/E2E 禁止敏感字段 | closed |
| T-04-06-01 | Tampering | unknown provider outcome | mitigate | 仅 exact request-key resolve，禁止盲目二次 create | closed |
| T-04-06-02 | Repudiation | provision/delete race | mitigate | claim/recheck/bind 与 delete-wins 状态机，覆盖三个删除窗口 | closed |
| T-04-06-03 | Information disclosure | retention worker | mitigate | worker 仅记录安全整数计数，不记录 statement/key/外部 ID | closed |
| T-04-06-04 | DoS | outbox worker | mitigate | `SKIP LOCKED`、有界重试/backoff、单 lifespan lease worker | closed |
| T-04-07-01 | Tampering | Graph capture | mitigate | 仅 accepted fresh text 触发，ORM/Provider 留在 Session adapter | closed |
| T-04-07-02 | DoS | Graph replay | mitigate | capture 消耗既有 tool budget，checkpoint marker 阻止 replay | closed |
| T-04-07-03 | Elevation | public memory API | mitigate | register → Mailpit verify → login；A/B GET/PATCH/DELETE 隔离 | closed |
| T-04-07-04 | Information disclosure | product response | mitigate | digest state、安全 DTO、H5 E2E 均禁止 external ID/request key 展示 | closed |

关键文件证据：`backend/app/records/service.py`、`backend/app/memory/service.py`、`backend/app/memory/repository.py`、`backend/app/memory/providers.py`、`backend/app/retrieval/repository.py`、`backend/app/agent/graph.py`、`backend/app/agent/state.py`、`backend/app/agent/retention.py`；测试证据见 `backend/tests/integration/test_meal_records.py`、`test_memory_deletion_chain.py`、`test_retrieval_isolation.py`、`test_agent_checkpoint.py`、`test_memory_direct_write_idempotency.py`、`test_direct_memory_public_api.py` 及 `frontend/tests/e2e/agent.spec.ts`。

## Accepted Risks Log

No accepted risks.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-01 | 28 | 28 | 0 | gsd-security-auditor |

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-01
