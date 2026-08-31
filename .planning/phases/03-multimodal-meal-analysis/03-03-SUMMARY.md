---
phase: 03-multimodal-meal-analysis
plan: 03
subsystem: multimodal-meal-analysis
tags: [fastapi, langgraph, qwen-vision, postgresql, alembic, multipart]
requires:
  - phase: 03-01
    provides: validated temporary image references and the Vision provider boundary
  - phase: 03-02
    provides: Qwen-VL adapter, configuration contract, and cost accounting
provides:
  - tenant-safe image and vision invocation lifecycle records
  - image observation routed through deterministic nutrition tools
  - multipart image endpoint and frozen browser API client contract
affects: [meal-analysis, image-upload, retention, agent-api]
tech-stack:
  added: [python-multipart]
  patterns: [opaque private image handles, outcome-unknown no-retry, deterministic nutrition provenance]
key-files:
  created:
    - backend/migrations/versions/0006_multimodal_images.py
    - backend/tests/integration/test_agent_multimodal.py
    - backend/tests/unit/test_agent_multimodal.py
  modified:
    - backend/app/agent/api.py
    - backend/app/agent/graph.py
    - backend/app/agent/service.py
    - backend/app/agent/retention.py
    - frontend/src/features/agent/api/generate-contracts.mjs
key-decisions:
  - "图片原文件只存在于私有短期目录；数据库仅保存摘要、受控 locator 与最小调用账本。"
  - "视觉产生候选和估重，所有营养数值仍只能来自确定性 NutritionToolAdapter。"
  - "视觉瞬时失败只重试一次；OUTCOME_UNKNOWN 不自动再调，避免重复付费。"
patterns-established:
  - "图片 API 先做 thread owner 校验，再读取有界 multipart 内容并执行安全解码。"
  - "私有文件删除失败保留 delete_failed 元数据并由保留期任务重试，不提前级联删除线程。"
requirements-completed: [VIS-03, VIS-04, VIS-05, VIS-06, NUT-06, NUT-07]
duration: 48min
completed: 2026-08-31
---

# Phase 3 Plan 03 Summary

**登录用户现在可在同一餐食线程上传一张经安全处理的图片，获得带估算标识、由确定性营养工具计算的报告。**

## Accomplishments

- 新增图片和视觉调用最小化账本迁移，带用户、线程和运行绑定、状态约束、过期索引与幂等键；没有原图、base64、EXIF、原文件名或提示词字段。
- 接通 multipart 上传、图状态、Vision Provider、受控目录检索和营养计算。低可信或缺少重量时统一追问，目录外项明确标为未计入。
- 重试相同命令键只复用同一图片调用；瞬时视觉故障最多再试一次，而 outcome unknown 不盲目重调。
- 临时文件在成功、异常、过期和用户删除路径清理；删除 I/O 失败会保留可审计、可重试的状态。
- 冻结 OpenAPI、Zod schema 和 TypeScript client 已随 multipart 接口更新。

## Task Commits

1. **Task 1: 图片与调用账本、租户隔离和删除链** — `f439297`
2. **Task 2: Vision 到确定性营养报告** — `7c7b712`
3. **收尾: 重试上限、删除失败补偿与真实集成验证** — `291922d`

## Verification

- mypy：通过，覆盖 Agent 与应用装配模块。
- 单元测试：23 passed，覆盖低可信集中追问、估算营养、瞬时重试和 outcome unknown 零盲重调。
- 真实 PostgreSQL：5 passed，覆盖迁移、保留期、图片上传、租户隔离、幂等与临时文件删除。
- 供应链门禁、依赖锁门禁、OpenAPI contract drift、前端 TypeScript 类型检查和 diff whitespace 检查：全部通过。

## Deviations from Plan

**[Rule 1 - Correctness] 迁移基线采用当前实际 head。** 计划上下文仍列出较早的 0004，而仓库已有 0005；新 migration 因此从 0005 衔接，避免分叉迁移历史。影响：无范围扩大。

## Issues Encountered

无阻塞问题。没有发送真实 Qwen 图片请求，因此没有产生额外模型费用。

## User Setup Required

无需新增配置。既有未提交的 Qwen 环境配置继续生效。

## Next Phase Readiness

Plan 03-04 可在这个安全的多模态分析垂直切片之上继续完成本阶段剩余工作。

---
*Phase: 03-multimodal-meal-analysis*
*Completed: 2026-08-31*
