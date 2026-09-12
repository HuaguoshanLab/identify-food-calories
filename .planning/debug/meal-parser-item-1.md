---
status: resolved
trigger: "分析页输入‘米饭 100g’后显示未匹配菜品：item_1"
created: 2026-09-12
updated: 2026-09-12
---

# Meal Parser `item_1` Debug Session

## Symptoms

- Expected: 用户输入“米饭 100g”后，应将“米饭”作为目录查询词并进入唯一精确匹配或明确的候选确认。
- Actual: 真实分析页显示“未匹配菜品：item_1”。
- Error: 页面没有 JavaScript 错误；后端返回的未匹配项目名为内部占位标识。
- Timeline: 当前本地 DeepSeek 配置下复现；此前 Phase 06.3 冻结检索评测不覆盖真实文本解析 Provider 输出。
- Reproduction: 在 `/app/analyze` 输入“米饭 100g”，点击“开始分析”。

## Current Focus

- hypothesis: confirmed — 存在两个独立问题：解析 Provider 可污染检索字段；即使后端正确保存 `unaccounted_items` 的内部 item_id，前端仍直接渲染该 ID。
- next_action: resolved — prompt v2/DTO 防护已阻断错误检索；前端将未匹配 ID 映射为 understood_items 中的用户可读名称，缺失映射使用安全通用文案。

## Evidence

- timestamp: 2026-09-12
  source: browser
  finding: 页面可见“未匹配菜品：item_1”。
- timestamp: 2026-09-12
  source: configuration
  finding: 当前本地 `REASONING_PROVIDER_MODE=deepseek`。
- timestamp: 2026-09-12
  source: code
  finding: DeepSeek parse 指令仅要求 JSON schema，未约束 `food_name`/`catalog_query` 必须是用户描述的食物名称且不得为内部 item ID。
- timestamp: 2026-09-12
  source: safe-equivalent-provider-and-graph-test
  finding: 模拟 DeepSeek 真实 Responses JSON 返回 item_id=food_name=catalog_query=item_1 时，旧 DTO 会接受；图层会以 catalog_query 优先调用目录搜索。该链路不记录原始餐食文本。
- timestamp: 2026-09-12
  source: regression-test
  finding: v2 合同拒绝 item_1 作为 food_name；若仅可选 catalog_query 被污染，则清空该字段并由图层以已校验的 food_name“米饭”检索。28 passed，1 PostgreSQL 测试因未通过 run_pg.py 而按设计跳过。

- timestamp: 2026-09-12
  source: code-and-browser
  finding: MealAnalysisGraph 设计上在 unaccounted_items 保存 item_id，_build_report 同时返回 understood_items。AnalyzePage 曾直接 join unaccounted_items，导致 UI 泄露 item_1。刷新真实本地线程后，页面显示“未匹配菜品：辣椒炒肉”，未显示内部 ID。
- timestamp: 2026-09-12
  source: frontend-regression-test
  finding: AnalyzePage 测试覆盖 item_1 映射到“米饭”且页面无 item_1，以及缺失映射显示“未能匹配的餐品”。15 个分析页组件测试和 TypeScript 类型检查通过。

## Resolution

- root_cause: DeepSeek 解析提示词与 ParsedMealItemDTO 未区分内部 item_id 和用户食物名，图层又优先使用 catalog_query；此外，后端合法的 unaccounted_items=item_id 被 AnalyzePage 直接拼接展示。
- fix: 升级解析提示词为 v2；拒绝 item_id/占位符作为 food_name；丢弃被内部 ID 污染的可选 catalog_query；前端由 understood_items 映射未匹配 ID 到名称，映射失败只显示安全通用文本。
- verification: MockTransport 覆盖真实 DeepSeek Responses 解析边界；图运行时断言目录搜索收到“米饭”；15 个分析页组件测试、TypeScript 类型检查通过；真实本地分析页刷新后显示用户可读“辣椒炒肉”而非内部 ID。全仓 lint 未通过，4 项为既有无关错误。
- files_changed: backend/app/providers/reasoning/dto.py; backend/app/providers/reasoning/deepseek.py; backend/app/agent/service.py; backend/tests/unit/test_runtime_foundation.py; frontend/src/features/agent/components/AnalyzePage.tsx; frontend/src/features/agent/components/AnalyzePage.test.tsx
