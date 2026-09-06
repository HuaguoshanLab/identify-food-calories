---
quick_id: 260906-jmo
status: complete
completed_at: 2026-09-06T06:42:17Z
commits:
  backend: da56004
  frontend: 23ef609
---
# 今日计划自动存档与历史版本

## 交付

- PostgreSQL `diet_plans` / `diet_plan_versions`：正式餐单、营养合计、菜谱/计算入口版本证据，独立于短期 Agent 清理。
- 首次生成、调整和重新生成成功后，存档与 Agent completed 状态在一个事务提交。相同运行幂等，同用户并发以稳定父行锁串行化；失败或保存异常保留旧版。
- 计划日期按线程开始时间及已确认统计时区固定；无时区时须通过 records 公开确认入口补齐。
- 今日自动恢复、历史日期分页、前后版本、整日删除确认。删除清除所有版本快照并保留防复活墓碑；未确认身体资料不会因此保存，计划不计入实际摄入。
- 支持原有首次生成的顶层 relaxation 与单餐调整的嵌套 relaxation；两者在严格报告校验和界面中都显式呈现。
- 本机 `food_agent_dev` 已执行 Alembic 0020 → 0021，仅新增存档表；原有开发服务未停止。

## 自动化证据

1. 后端：通过隔离 runner 执行 `tests/integration/test_diet_planning_agent_api.py tests/planning tests/unit/test_diet_planning_graph.py`，**80 passed**。其中覆盖未保存 profile 的餐单存档、用户隔离、版本重放、失败生成、事务中写入后故障回滚、事件清理后读取、真实双连接并发。
2. 前端：`npm run typecheck` 成功；`npm run test -- src/features/plans`，**22 passed / 6 files**。
3. 改动范围 ESLint 与 Ruff 均通过；5 个新增 archive Python 模块定向 mypy（follow-imports=silent）通过。
4. Playwright `plans.spec.ts`：**2 passed**，独立端口 5278/8100/5285、隔离测试库；真实注册、后台公开页面启用 Fake Provider 配置、确认时区、生成、刷新、历史、调整、版本、取消/确认删除和返回空态。320/375/430/768px 无横向溢出。
5. E2E 运行包含生产构建成功；仍有现有单 bundle 超过 500 kB 的构建提示。
6. `git diff --check` 通过。

## 内置浏览器实测

地址：`http://127.0.0.1:5278`，使用上述公开注册创建的合成测试账号，登录走真实页面与公开认证接口，没有注入 token 或写数据库来替代用户流程。

- 首次登录计划页自动读取第 1 版。
- 页面提交“午餐换清淡一些”：午餐由鸡丝蔬菜饭碗换为鸡胸肉西兰花饭，保存为第 2 版；按钮保留焦点。
- 刷新后第 2 版及相同午餐恢复，早餐/晚餐保留。
- 进入历史和详情，切换至第 1 版，原午餐与原营养值仍存在。
- 打开删除对话框，确认提示涵盖整天全部版本且不影响实际餐食；取消后原内容仍可读取。真正删除另由 Playwright 覆盖。
- 重新生成时填写合成资料，不勾选保存身体资料，完成后显示第 3 版。
- 不存在的计划先显示加载态，随后明确提示不存在/已删除/暂不可读，并提供重试和返回。
- 切换到已通过 E2E 删除计划的另一账号，历史显示空态，没有显示前一个账号的计划。
- 320px 内置浏览器检查 `scrollWidth == innerWidth == 320`，卡片和操作保持单列；尺寸覆盖已恢复。

## 调整与边界

- 原规划 API 集成测试缺少 Phase 6 新增的启用运行配置前提，最初返回 503；测试通过已审计 AdminService 配置 Fake Provider 准入后验证正式规划流程。
- 原计划页忽略首次生成的顶层放宽目标字段，新严格存档校验暴露该遗漏；已补齐合同，而非忽略字段。
- 调整提交使用 aria-disabled 与请求守卫防止重入，避免原生 disabled 丢失焦点。E2E 允许 8px 内的原生布局稳定偏移（实际观察 4px），仍拦截向结果区跳转造成的大幅滚动。
- **全仓静态检查未全绿**：全量 mypy 观察到 43 个现存错误，涉及 records/admin/dashboard/memory 及未改动的 Agent API 分支；全量 ESLint 仍有 `SafeProgressStages.tsx` 的组件导出规则、`weeklyReview.ts` 的未使用变量两项。此次改动范围的定向检查通过，未顺带修改无关模块。
- 未验证移动端实体设备、所有辅助技术与完整 200% 缩放矩阵；已完成定向真实浏览器与多宽度 E2E。
- 升级前只有短期线程的旧计划不会自动回填，需要重新生成；临时会话过期后正式餐单仍可读，继续调整需重新生成。

中文教学：`docs/learning/daily-plan-archive.md`。Phase 7 保持用户先前要求的延后状态。
