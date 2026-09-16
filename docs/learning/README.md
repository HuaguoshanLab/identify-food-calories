# 功能学习总目录

这里按“用户能做什么”学习项目，重点看 **AI 怎样与后端协作**：接收输入、理解意图、调用工具、追问、保存结果，再利用历史信息提供下一次服务。

本目录负责提供功能入口和阅读顺序。功能文档解释业务背景、执行流程和关键代码；只引用仓库内真实代码，不把规划目标当成已经验证的能力，也不保存凭证或用户隐私。

## 从哪里开始

先读 **01 登录注册**，理解后端如何识别用户；再沿着 **03 文字餐食分析 → 04 图片识别 → 05 菜品检索 → 06 营养计算 → 07 追问恢复** 学习 AI 主线。随后看餐食保存、长期记忆和饮食规划，理解一次对话如何变成可以长期使用的产品。

**22 篇功能文档均按功能组织。** 导航全部进入独立功能文档。原有阶段文档移至 docs/after/ 作为历史参考；学习主线以本目录的新文档为入口。

## 先分清 AI 和后端分别做什么

| 环节 | 当前实现 |
|---|---|
| 理解餐食文字 | 文本 Provider 提取结构化食物项，后端校验格式 |
| 看餐食图片 | 视觉 Provider 识别食物与份量线索 |
| 查相似菜品 | Embedding 提供相似表达线索，后端融合候选，用户确认非精确结果 |
| 算营养与目标 | 后端按目录、公式和规则计算 |
| 生成与调整餐单 | 当前主要由后端规则组合、替换和校验；不能描述成模型自由生成 |
| 恢复对话 | 自定义状态机推进，应用服务手动读写 LangGraph Checkpoint |
| 每周复盘 | 后端先汇总事实，再让模型输出受限建议 |
| 保存偏好 | 有限规则提取明确表达，本地账本控制归属与可见性，Mem0 保存受控副本 |

## 功能导航

| 顺序 | 功能与入口 | 要学懂的问题 | 文档状态 |
|---|---|---|---|
| 01 | [登录注册与登录状态](feature-auth.md) | 后端如何确认你是谁，给 AI 会话建立用户归属？ | 已按场景串联代码重写 |
| 02 | [密码找回与账号管理](feature-account-recovery.md) | 忘记密码、管理登录设备时，后端如何处理？ | 已按场景串联代码重写 |
| 03 | [文字餐食分析](feature-text-analysis.md) | 一句“我吃了什么”，如何进入 Agent 并得到结果？ | 已按场景串联代码重写 |
| 04 | [食物图片上传与识别](feature-image-analysis.md) | 跟着一张照片读懂上传、模型请求、状态转换与追问。 | 已按场景串联代码重写 |
| 05 | [菜品检索与候选确认](feature-food-search.md) | 用户的叫法如何对应到可计算的菜品，何时需要确认？ | 已更新初始目录精确查询与同名来源确认 |
| 06 | [营养计算与结果校验](feature-nutrition.md) | 为什么热量由工具计算，模型不能随意写数值？ | 已按场景串联代码重写 |
| 07 | [信息追问与对话恢复](feature-clarification.md) | 信息不够时如何暂停，回复后如何继续？ | 已按场景串联代码重写 |
| 08 | [重量输入与单位转换](feature-weight.md) | “0.5斤”这样的输入怎样转成可计算的克数？ | 已按场景串联代码重写 |
| 09 | [餐食确认、餐次与历史记录](feature-meal-records.md) | 分析结果如何成为正式记录？ | 已按场景串联代码重写 |
| 10 | [长期饮食偏好记忆](feature-memory.md) | 如何记住“不吃香菜”，又允许用户修改和删除？ | 已补充复合偏好拆分、临时范围隔离、原子保存与分类复核 |
| 11 | [个人资料与饮食目标](feature-profile-targets.md) | 用户资料如何形成可校验的每日目标？ | 已按场景串联代码重写 |
| 12 | [生成一日餐单](feature-daily-planning.md) | 如何按目标比较候选组合，并检查忌口和全天约束？ | 已更新午晚餐组合明细、受限份量、分批预算与历史快照 |
| 13 | [餐单局部调整](feature-plan-adjustment.md) | 怎样落实清淡要求，并保留其他餐次快照？ | 已更新连续同文换餐、网络重试去重、固定餐次与受控标签约束 |
| 14 | [餐单存档与历史版本](feature-plan-archive.md) | 完成的计划如何长期保存、按日期查找？ | 已按场景串联代码重写 |
| 15 | [摄入统计与历史看板](feature-dashboard.md) | 如何把已确认记录变成今日与本周统计？ | 已按场景串联代码重写 |
| 16 | [AI 每周饮食复盘](feature-weekly-review.md) | 怎样先算好事实，再让模型给出受限的文字解释？ | 已按场景串联代码重写 |
| 17 | [后台营养目录维护](feature-catalog-admin.md) | 管理员怎样维护供 AI 工具使用的数据？ | 已按场景串联代码重写 |
| 18 | [菜谱候选池管理](feature-recipe-pool.md) | 如何标注餐内角色，让主食、蛋白质菜和蔬菜组成一餐？ | 已按场景串联代码重写 |
| 19 | [向量索引构建与管理](feature-vector-index.md) | 菜品如何准备好供语义检索使用，失败后怎么办？ | 已按场景串联代码重写 |
| 20 | [管理员权限与审计](feature-admin-permissions.md) | 谁能修改后台数据，操作如何留下记录？ | 已按场景串联代码重写 |
| 21 | [模型配置与运行记录](feature-runtime-operations.md) | 如何查看模型运行和失败信息，管理运行配置？ | 已按场景串联代码重写 |
| 22 | [Agent 可观测性与本地 Langfuse](feature-observability.md) | 如何在不泄露饮食和健康数据的前提下查看 Agent 调用轨迹？ | 已接入开发环境 |

## 后续维护规则

每个阶段或功能变更完成后，更新本目录中受影响的功能文档；新功能才新增独立文档，并同步上方导航。不要按 Phase 新建教程，也不要把已归档的阶段文件搬回本目录。具体合同见[项目规范](../../AGENTS.md)与[GSD 项目说明](../../.planning/PROJECT.md)。

## 每篇功能文档的阅读结构

开头用几句话介绍功能，再按以下顺序讲解：

1. **具体例子**：一个真实使用场景贯穿全文，示意数据与真实运行结果明确区分。
2. **为什么这样实现**：说明业务问题和设计理由。
3. **整体流程图**：先看清输入、处理和输出。
4. **跟着例子读代码**：每一步都写“收到什么、代码在哪里、连续主逻辑、为什么这样写、处理后变成什么、交给谁”；陌生语法在出现处解释。
5. **分支对照**：换一个输入会如何处理，不能只写“有异常处理”。
6. **自己验证一次**：提供现有测试命令，说明应观察的输入、状态或调用次数。
7. **理解检查**：三个问题和最短源码阅读顺序。

篇幅随功能复杂度调整；精简的是重复表达，不省略理解所必需的数据流。

## 场景教程重写验证（本轮）

本轮重写除图片篇以外的 20 篇；图片篇沿用已确认版本。核对 **61 段**连续 Python 节选与对应源码，并检查语法结构和本地链接。已有运行文档中的锁等待补充说明保留；其历史验证描述不等于本轮新增验收。

按各篇测试命令去重执行 26 个文件或测试选择器，共 **296 项通过、3 项失败**。三个失败仍位于目录发布生命周期测试，原因是 FakeLifecycleRepository 缺少 add_catalog_search_version；因此不能宣称目录发布验证通过。

本轮未执行真实模型、真实 PostgreSQL 集成测试或浏览器页面验收。下面保留此前验证记录，时间相同但执行批次和范围不同。

## 本次验证记录（2026-09-12）

本次修改学习文档，没有修改业务实现。已检查 21 篇功能文档与目录的本地链接；新增 20 篇中的 Python 节选逐段与当前源码比对。

选取 24 个相关测试文件运行，共 **293 项通过、3 项失败**。覆盖文字与图片处理、检索、营养计算、追问恢复、记忆、餐食保存、目标与餐单、看板、周复盘、后台配置与权限等离线路径；不代表所有功能已完成实际页面或集成验收。

失败集中在 `backend/tests/admin/test_catalog_lifecycle_service.py`：`FakeLifecycleRepository` 缺少 `add_catalog_search_version`，目录发布进入索引任务准备时抛出 `AttributeError`。因此本次不能确认该文件中的发布生命周期验证通过，本文只解释已核对的源码行为。

本次未运行真实 PostgreSQL 集成测试、真实模型评测、邮件端到端测试或浏览器交互。第一篇此前单独运行的 15 项认证服务测试通过，不计入本次 296 项结果。

<details>
<summary>本次执行的测试文件（相对 backend/）</summary>

```text
tests/unit/test_weight_input.py
tests/unit/test_nutrition.py
tests/unit/test_runtime_foundation.py
tests/unit/test_agent_multimodal.py
tests/unit/test_image_safety.py
tests/unit/test_hybrid_food_search.py
tests/unit/test_agent_memory_context.py
tests/unit/test_diet_planning_graph.py
tests/records/test_record_service.py
tests/memory/test_memory_service.py
tests/planning/test_planning_service.py
tests/planning/test_planning_profile_service.py
tests/planning/test_managed_recipe_candidates.py
tests/planning/test_plan_archive.py
tests/dashboard/test_dashboard_service.py
tests/dashboard/test_weekly_review_graph.py
tests/dashboard/test_weekly_review_cache_service.py
tests/admin/test_catalog_draft_service.py
tests/admin/test_catalog_lifecycle_service.py
tests/admin/test_runtime_config_service.py
tests/unit/test_admin_user_management_api.py
tests/unit/test_admin_rbac_api.py
tests/unit/test_admin_run_api.py
tests/unit/test_embedding_provider.py
```

在已安装测试依赖的 backend 环境中，将上列文件路径作为 `python -m pytest` 的参数可复查同一批测试。单独复查重量解析可运行 `python -m pytest tests/unit/test_weight_input.py -q`。此处仅运行离线测试，不需要加载生产凭证。

</details>

## 旧文档归档

原有阶段及补充专题文档已迁至 [docs/after/](../after/README.md)。本目录只保留按功能组织的新学习文档。
