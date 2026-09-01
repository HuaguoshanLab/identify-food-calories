---
phase: 04-meal-records-and-memory
plan: "02"
status: retrospective
reconstructed: 2026-09-01
evidence_commits: [2b01c09, f4c742b, 3788e4b, 4f47956, 56a3264]
provides: [memory-ledger, memory-api, mem0-adapter, deletion-outbox]
affects: [04-03, 04-04, 04-05, 04-06, 04-07]
---

# Phase 4 Plan 02: 长期记忆基础追溯 Summary

> 这是追溯性 Summary。`2b01c09` 是原计划的唯一实现提交；04-05/04-06 随后纠正并补强了 direct-memory provision 的持久化语义。

## 可追溯实现

- `2b01c09 feat(04): add auditable long-term memories` 创建 `app.memory`：Provider Port、离线 Fake、Mem0 adapter、tenant-bound ledger repository、Service 和认证 API。
- 配置支持 `MEMORY_PROVIDER_MODE=fake|mem0`；生产模式要求 `MEM0_API_KEY` 和 `MEM0_ENDPOINT`，本地默认 Fake 不需密钥。
- 本地 `PreferenceMemoryLedger` 是授权真相；响应不暴露外部 memory ID、向量、分数、原始对话或 Provider payload。
- 编辑记录为用户手动维护；删除先使本地记忆不可检索，再由 deletion outbox 异步清理外部副本。
- 同一提交增加 memory Service/API/deletion-chain 测试与目录索引。

## 后续补强与验收

- `04-05` 增加 direct preference 的 provisioning outbox、请求键幂等和 `infer=False` Mem0 合同。
- `04-06` 将 Provider I/O 移到 lifespan lease worker，补齐重启、未知结果和删除竞态的真实 PostgreSQL 验证。
- 真实浏览器 UAT 测试 4、5 已通过：分析文本可写入记忆、编辑会变为“用户手动维护”、确认删除后立即为空状态。

## 追溯限制

- 原执行没有任务级 Summary 或命令输出，不能把 `2b01c09` 当作原计划所有验证均已完成的证明。
- 原始 direct-write 路径后来被 04-05/04-06 的 durable outbox 协议取代；当前状态以这些后续计划为准。

## Self-Check

- Git 提交和现存 `app.memory` 模块、测试、配置文件均存在。
- 最终用户路径的浏览器证据见 `04-UAT.md`。
