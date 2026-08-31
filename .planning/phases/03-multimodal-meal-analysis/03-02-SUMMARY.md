---
phase: 03-multimodal-meal-analysis
plan: 02
subsystem: qwen-vision-provider
tags: [qwen-vl, httpx, pydantic, image-safety, cost-accounting]
requires:
  - phase: 03-01
    provides: validated temporary image references and a test-forced Vision Provider boundary
provides:
  - Qwen-VL OpenAI-compatible adapter with strict observation validation
  - non-retrying outcome-unknown handling and bounded transient retry
  - versioned CNY token-tier accounting and user-verified local Qwen configuration
affects: [03-03, meal-analysis, image-upload, agent-observation]
tech-stack:
  added: []
  patterns: [in-memory data URL boundary, strict provider JSON validation, CNY tier cost accounting]
key-files:
  created:
    - backend/app/providers/vision/qwen.py
    - backend/tests/test_qwen_vision_provider.py
  modified:
    - backend/app/core/config.py
    - backend/app/providers/vision/factory.py
    - backend/.env.example
key-decisions:
  - "Qwen 价格按用户核实的人民币每百万 Tokens 阶梯保存，不把 CNY 写入美元字段。"
  - "timeout、连接或协议中断一律标为 OUTCOME_UNKNOWN，绝不自动重调。"
  - "真实 API Key 只在未提交的 backend/.env 中验证存在；本计划不发送付费真实图片请求。"
patterns-established:
  - "视觉调用仅从已验证临时引用读取 bytes，并仅在单次 outbound body 内生成 data URL。"
  - "模型响应先提取 JSON 再经过 VisionMealResult 校验；不合格响应 fail closed。"
requirements-completed: [VIS-03, VIS-05, VIS-06]
duration: 41min
completed: 2026-08-31
---

# Phase 3 Plan 02 Summary

**Qwen3-VL-Flash 现在通过受控 HTTP adapter 接收短期已验证图片，返回严格观察 DTO，并以已核实的人民币阶梯记录成本。**

## Accomplishments

- 实现 Qwen OpenAI compatible adapter：固定非 thinking、JSON object、版本化图文约束和 completion 上限。
- 结构无效、4xx、429/5xx 与未知网络结果被稳定分类；仅 429/5xx 在同一 request key 下最多重试一次。
- `backend/.env` 的 Key、北京/默认业务空间、Base URL、`qwen3-vl-flash` 与价格快照均由用户核实，秘密未写入 Git。
- 补充本地配置验证命令与 Qwen 的数据最小化、计量边界文档；真实调用仍需在正式业务路径中触发。

## Task Commits

1. **Task 1: 实现 Qwen-VL 结构化观察 adapter 和安全计量** — `4f8017b`、`d29efbf`、`03c0538`
2. **Task 1 文档收尾：记录 Qwen Provider 配置与安全边界** — `6307fc9`
3. **Checkpoint 2: 核实 Qwen 生产区域和未提交配置** — 用户于 2026-08-31 确认；无代码提交。

## Verification

- 本地 Qwen provider 配置装配 — PASS；未读取 Key、未执行真实网络调用。
- pytest：29 passed。
- mypy：PASS。
- 供应链与依赖锁门禁：PASS。

## Deviations from Plan

**[Rule 1 - Correctness] 人民币价格字段建模** — 计划实现初稿沿用美元命名，用户提供的 Model Studio 价格明确为 CNY；已改为三个输入 token 档位的 CNY 字段、类型归一化及对应测试。验证：29 项相关测试、mypy 和依赖门禁通过。提交：`03c0538`。

**Total deviations:** 1 auto-fixed（正确性）。**Impact:** 防止成本记录币种错误，无范围扩张。

## Issues Encountered

无。为避免无业务价值的付费调用，本计划未执行可选真实图片 smoke；配置装配和 mock transport 已验证。

## User Setup Required

外部服务配置已由用户完成。详见 [03-USER-SETUP.md](./03-USER-SETUP.md)。

## Next Phase Readiness

Plan 03-03 可以把安全图片和 Qwen 观察接入餐食分析 API/应用服务。真实 Qwen 调用仍只能从该受控业务路径发起，不能在测试中直接调用。

---
*Phase: 03-multimodal-meal-analysis*
*Completed: 2026-08-31*
