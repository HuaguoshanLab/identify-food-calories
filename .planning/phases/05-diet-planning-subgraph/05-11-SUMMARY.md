---
phase: 05-diet-planning-subgraph
plan: "11"
subsystem: planning-safety
tags: [deterministic-validation, controlled-recipes, alembic, postgresql]
requires: [05-08]
provides:
  - complete three-meal totals, macro-ratio, exclusion, and duplicate validation
  - version-selected v2 controlled recipe seed with immutable v1 history
  - recovery of the public adult planning API success path
affects: [diet-planning-graph, local-bootstrap, planning-api]
key-files:
  created:
    - backend/app/planning/data/controlled-recipes.v2.json
    - backend/migrations/versions/0012_activate_controlled_recipes_v2.py
  modified:
    - backend/app/planning/service.py
    - backend/app/agent/tools.py
    - backend/app/agent/graph.py
    - backend/app/planning/importer.py
decisions:
  - "v1 保留不可变审计记录；运行时明确选择 v2，旧版本不再是候选。"
  - "低于 1200 kcal、宏量比例失败、重复 recipe 或排除项命中永不进入 RELAX。"
completed: 2026-09-02
---

# Phase 5 Plan 11: 规划校验与受控菜谱修复 Summary

补齐了原本断开的三餐校验链，并用可审计的 v2 seed 取代总量不足的 v1 运行时候选。

## Accomplishments

- Service 从实际三餐重算每日能量与三大宏量，校验三槽完整性、recipe 去重、忌口、1200 kcal 地板、目标区间和 AMDR 比例。
- 图和 adapter 强类型透传 `PlannedMeal`；初始 `RELAX` 现在安全完成并公开偏离，不会错误重试或伪装为硬通过。
- `controlled-recipes.v2` 是唯一 active/query-selected 版本；v1 仅留作审计历史。0012 和 importer 在升级/导入时停用 v1。
- 本地开发库已升级 0012 并成功导入 v2；未触碰 `planning_profiles` 或用户偏好。

## Verification

- PASS — service/importer/graph 定向测试：54 passed。
- PASS — 真实 PostgreSQL 公开 diet-planning API：5 passed；包含健康拒绝和明确命名的合成普通成人 v2 成功路径。
- PASS — 0012 在隔离测试库上 `downgrade 0011` 后 `upgrade head`。
- PASS — Ruff。
- KNOWN EXTERNAL — Mypy 被既有 `app/memory/providers.py` 的 Mem0 类型问题阻断；本次修改文件无类型错误。

## Deviations from Plan

**[Rule 1 - Bug]** 原始 v1 seed 三餐约 1011 kcal，且校验调用链没有消费 `meals`。修复为确定性 totals/ratio/repetition 校验和版本化 v2 seed，而非放宽最低能量或健康边界。

## Self-Check: PASSED

- v2 manifest、0012 migration、定向测试和教学文档均存在。
- 真实 PostgreSQL API 正反例与迁移 round trip 已执行。
