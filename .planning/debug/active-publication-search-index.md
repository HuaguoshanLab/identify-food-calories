---
status: resolved
trigger: "用户在后台看到已发布且 eligible 的白米饭，用户分析页输入白米饭 100g 却先后出现未匹配与 RUNTIME_FAILURE"
created: 2026-09-12
updated: 2026-09-12
---

# 已发布目录的检索索引与运行失败

## Symptoms

- expected: 已授权、已发布、激活且 eligible 的“白米饭”应在用户侧被精确匹配并计算。
- actual: 早先显示“未匹配菜品：白米饭”；最新一次显示泛化的“本次餐食分析未完成”。
- reproduction: 在 `/app/analyze` 输入“白米饭 100g”，点击开始分析。
- timeline: 该菜品发布于混合检索索引功能之前；后续本地启动并迁移后复现。

## Current Focus

- hypothesis: 旧的激活发布版本没有 `catalog_search_names` 回填，导致混合检索无法精确匹配；`RUNTIME_FAILURE` 与该索引缺失独立，发生在图转换开始前。
- next_action: resolved — 回填已执行；运行失败现有安全诊断已落地，并完成真实页面回归。
- scope: 不修改现有营养权威数据或公开密钥；不记录原始餐食或模型内容。

## Evidence

- 白米饭草稿 `authorized`，有发布版本、是激活版本，最新资格为 `eligible`。
- 对该激活发布版本只读查询的 `catalog_search_names` 数量为 0。
- `SqlAlchemyHybridFoodSearchRepository.find_current_qualified_exact()` 只从当前合格发布连接 `catalog_search_names` 进行精确匹配。
- 最新失败运行的账本为 `failed / RUNTIME_FAILURE`，图步骤、模型调用、工具调用均为 0，且无 invocation；安全事件没有异常详情。
- `AgentService.execute_run()` 仅会在进入 `graph.ainvoke()` 前的 checkpoint 加载，或 `MealAnalysisGraph.ainvoke()` 的上下文检索/偏好捕获阶段抛出未处理异常时，留下 `RUNTIME_FAILURE` 且三个计数均为 0；目录查询本身不在此路径。
- 用随机线程的只读 PostgreSQL checkpoint 探针及截图线程的只读 checkpoint 探针均可读取并返回空值；用随机身份、无敏感文本探测上下文检索和偏好捕获均成功。因此未发现全局 checkpoint、上下文 SQL 或偏好捕获故障；仍需对真实请求记录安全的失败阶段和异常类别。
- `DeepSeekReasoningModelProvider` 会把 DTO 验证错误包装为 `ProviderCallError`；该路径会先增加图/模型计数并落为 `ANALYSIS_NOT_COMPLETED`，不能解释这次零计数的 `RUNTIME_FAILURE`。
- 管理员受审计回填实际处理 644 个活跃合格发布，新增 1289 个名称索引；“白米饭”精确检索已命中。
- 用户授权后，真实浏览器提交“白米饭 100g”完成分析：130.0 kcal、蛋白质 2.4g、脂肪 0.3g、碳水 28.2g；未保存餐食记录。

## Resolution

- root_cause: 已确认的用户侧未匹配根因是旧活跃发布缺少 `catalog_search_names` 派生索引。原始一次 `RUNTIME_FAILURE` 因当时的全局异常吞没机制未保留安全阶段，无法事后精确归因；后续同一真实路径已成功，未发现持续性 checkpoint 或上下文服务故障。
- fix: 新增管理员 RBAC、确认、幂等键和审计保护的检索索引回填命令；为运行失败记录仅含阶段和异常类的安全诊断，并将前端提示改为服务暂时不可用，而非指责餐食描述。
- verification: 回填后的仓储精确匹配与真实浏览器端到端分析均通过；未直接篡改营养、发布或资格权威数据。
