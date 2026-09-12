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

- hypothesis: confirmed — 解析 Provider 的结构化输出允许将 `item_id`/占位符放入 `food_name` 或 `catalog_query`，图层将其直接传给目录检索。
- next_action: resolved — prompt v2、DTO 合同与图层回归已阻断内部 ID 作为检索词。

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

## Resolution

- root_cause: DeepSeek 解析提示词与 ParsedMealItemDTO 都未区分内部 item_id 和用户食物名，MealAnalysisGraph 又直接优先使用 catalog_query。
- fix: 升级解析提示词为 v2；拒绝 item_id/占位符作为 food_name；丢弃被内部 ID 污染的可选 catalog_query，使检索安全回退到已校验 food_name。
- verification: MockTransport 覆盖真实 DeepSeek Responses 解析边界，图运行时断言目录搜索收到“米饭”而不是 item_1；相关测试、Ruff、diff check 通过。
- files_changed: backend/app/providers/reasoning/dto.py; backend/app/providers/reasoning/deepseek.py; backend/app/agent/service.py; backend/tests/unit/test_runtime_foundation.py
