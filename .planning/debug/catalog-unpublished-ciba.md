---
status: diagnosed
mode: diagnose-only
created: 2026-09-05
updated: 2026-09-05
trigger: "用户报告四川糍粑发布后，客户端提示无法生成营养报告、未匹配菜品：1"
---

# 未发布目录与误导提示

## Symptoms

- expected: 后台发布菜品后，客户端能匹配并计算。
- actual: 输入四川糍粑、补充100克后，报告提示未匹配菜品1。
- timeline: 本次报告时发生；此前是否成功未知。

## Current Focus

- hypothesis: 审核发布未完成，而非名称匹配失败。
- next_action: 用户先审核再发布；若要求代码修复，应区分生命周期冲突原因、明确发布前置状态、将未计入编号映射菜名。
- scope: 只读核对，不执行审核/发布，不改业务代码。

## Evidence

- 内置浏览器后台发布页显示“此草稿已被其他管理员更新”，当前值全为破折号，提示首次发布，立即失格按钮禁用。
- 受保护本地 food_agent_dev 只读事务对指定草稿查询：名称四川糍粑、revision1、authorized；review_revisions=[]、publication_revisions=[]、active_publication_count=0。
- 只读核对用户当前分析：waiting_input 中 understood_items 名称四川糍粑、item_id=1；补充后 grams=100，unaccounted_items=[1]、is_partial=true。模型没有将名称误识别成其他菜品。
- `admin/service.py::publish_catalog_draft` 要求当前 revision 的审核记录；不存在时 CatalogDraftConflict。API 将其映射为通用409。
- `CatalogLifecyclePage.tsx` 将所有409统一提示其他管理员更新；本场景并无证据支持多人冲突。
- `graph.py::_build_report` 的 unaccounted_items 是内部 item_id；AnalyzePage 直接 join 显示，导致用户看到编号而不是 understood_items 中的菜名。

## Eliminated

- 已发布却查不到：此条目根本没有发布记录。
- 模型把菜名改写导致未匹配：实际报告中的识别名称与草稿一致。
- 重量未提交：实际报告克重为100。

## Resolution

- root_cause: 当前菜品未审核、未发布，不在可计算的发布目录中；管理端错误原因和客户端未匹配菜名的显示均不准确。
- fix: 未执行。未替用户发布菜品，也未修改其营养数据。
- verification: 内置浏览器当前页面、指定菜品/会话的只读数据库结果、源码条件一致。

## 2026-09-05 担担饭后续核对

- 用户要求浏览器操作担担饭后，按审核、发布步骤提交，页面曾显示通用冲突；当时未观测到成功反馈，不能据此证明审核没有保存，也不能证明有其他管理员修改。
- 用户要求继续排查时，只读事务确认担担饭 revision 1 已有审核及发布记录，审核快照与当前草稿、内容哈希完全一致，active pointer 指向该发布，eligibility 为 eligible。
- 审核时间为 08:04:12 UTC，发布时间为 08:04:16 UTC。审核理由是上一轮填写的发布理由，实际发布理由为“1”，与助手提交内容不同。因此期间还有页面操作，不能将当前成功归因于助手上一轮提交，也不能由最终状态还原当时失败的具体分支。
- 内置浏览器客户端现有分析已显示担担饭 100g、180 kcal、蛋白质4g、脂肪4g、碳水32g，证明当前发布版本已在客户端生效。本轮未新建分析、未点击确认保存、未改业务数据或代码。
- 修正前述诊断边界：四川糍粑在最初查询时未审核/发布是已确认事实，但其为何未完成不能只归因于用户漏点审核。生命周期所有409共用“其他管理员更新”文案仍是已确认的界面缺陷；担担饭先前失败的具体409分支未被捕获。
