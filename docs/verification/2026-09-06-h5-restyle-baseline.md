# H5 视觉改版前功能基线

日期：2026-09-06。源码基点：`18af8073c3ce1e0ff721a555355c0bf6c6895d02`。

范围：视觉改版前的功能基线。只记录源码、测试和设计冲突，不修改运行时代码，不代表已经完成视觉改版。开始时 `docs/ui/h5-design-guidelines.md` 与其 README 已有未提交修改，予以保留。

## 1. 已确认的改版边界

- 主要视觉参照为 `/Users/mina/Downloads/饮食健康助手-代码` 的实际样式与页面源码。
- 交互冲突以本地项目为准。保留 API、数据校验、数值口径、认证、状态机、缓存、存档与错误恢复。
- 设计稿没有的本地能力继续保留，以同一套卡片、字体和间距呈现。
- 不迁入模拟数据、定时进度、固定热量范围、宿主 SDK 或第二套 UI 组件库。

## 2. 路由基线

依据：[App.tsx](../../frontend/src/App.tsx)。保留现有路径、认证守卫和链接参数，不换成设计稿路径。

| 页面 | 当前路由 | 布局与行为 |
|---|---|---|
| 公开首页与认证 | `/`、`/login`、`/register`、`/forgot-password` | 公开认证布局，无底部 Tab |
| 验证与密码重置 | `/register/verify`、`/reset-password` | 带返回入口的公开步骤布局 |
| 法律说明 | `/privacy`、`/terms` | 公开可访问 |
| 应用入口 | `/app` | 重定向分析页 |
| 四 Tab | `/app/analyze`、`/app/records`、`/app/plans`、`/app/me` | 认证保护，共享页面壳和四项导航 |
| 账号、资料、会话 | `/app/me/account`、`/app/me/profile`、`/app/me/sessions` | 独立详情布局，无底部 Tab |
| 餐食详情与编辑 | `/app/records/:recordId`、`/app/records/:recordId/edit` | 保留记录标识与编辑入口 |
| 记忆列表与编辑 | `/app/me/memories`、`/app/me/memories/:memoryId/edit` | 保留管理与单项编辑流程 |
| 历史计划与详情 | `/app/plans/history`、`/app/plans/detail?id=…&version=…` | 保留分页、计划标识和版本选择；version 可省略 |
| 未匹配路径 | `*` | 当前回到 `/`；本轮不更改兜底策略 |

用户 H5 不包含管理员页面；独立 `admin-frontend/` 不在本次换肤范围。

## 3. 必须保留的交互

以下为源码及现有测试所定义的行为，不等于本次已逐项完成真实浏览器验收。

| 模块 | 回归底线 | 主要证据位置（相对 frontend/） |
|---|---|---|
| 认证 | 注册→验证码激活→登录；重发冷却、找回密码、刷新身份、受保护页面跳转及退出 | `src/auth/`；`tests/e2e/auth-skeleton.spec.ts` |
| 会话 | 当前会话优先；撤销其他会话需确认；失败可重试；当前会话走退出流程 | `src/auth/AuthSession.test.tsx` |
| 分析 | 文字/图片输入、公开阶段进度、整批追问和候选选择、恢复同一线程、修正与删除确认 | `src/features/agent/components/AnalyzePage.tsx`；`tests/e2e/agent.spec.ts` |
| 营养报告 | 后端权威值、估算重量与部分报告；全部未匹配不能伪装成零热量完整报告 | `src/features/agent/components/AnalyzePage.test.tsx` |
| 保存餐食 | 明确餐次与用餐时间；防重复提交；保存失败保留输入 | 同上；`src/features/records/components/MealRecordEditPage.test.tsx` |
| 记录看板 | 先确认统计时区；冲突时停止看板读取；今日、七日趋势和历史以服务端归属为准 | `src/features/records/components/RecordsPage.test.tsx` |
| 趋势与复盘 | 图表及表格同源；历史分页；覆盖不足只呈现事实；仅可重试失败提供重试入口 | `src/features/records/components/WeeklyTrend.test.tsx`、`WeeklyReview.test.tsx` |
| 个人资料 | 查看、显式保存、字段错误和删除确认；偏好有独立管理入口 | `src/features/plans/components/PersonalProfilePage.test.tsx` |
| 规划输入 | 可填写本次资料、选择是否保存；偏好只读预填且必须复核 | `src/features/plans/components/ProfileGoalForm.tsx` 及其测试 |
| 规划结果 | 时区确认、今日计划恢复、成功自动存档、重新生成及取消、三餐报告 | `src/features/plans/components/PlanPage.tsx`、`SavedPlanPages.test.tsx` |
| 规划调整 | 自然语言调整、歧义餐次确认、约束放宽说明、3 次调整上限、拒绝与失败区分 | `src/features/plans/components/PlanPage.test.tsx` |
| 历史计划 | 日期及版本、上一版/下一版、整份计划删除确认；不影响实际餐食记录 | `src/features/plans/components/SavedPlanPage.tsx` |
| 偏好记忆 | 查看、编辑、确认删除；规划只读白名单偏好，不新增第二个偏好编辑器 | `src/features/memory/`；`tests/e2e/agent.spec.ts` |
| 布局与可访问性 | 一个主滚动区、四 Tab、详情返回、焦点、键盘操作、320px 窄屏 | `src/layouts/layouts.test.tsx`；`tests/e2e/h5-visual.spec.ts` |

## 4. 设计冲突及适配决策

| 设计稿 | 本地事实 | 后续设计方式 |
|---|---|---|
| 计划页必须已有个人资料，只有摘要和跳转编辑 | 支持本次临时资料，用户选择是否保存 | 采用设计稿摘要格和卡片风格，保留可编辑的本次资料区及保存选择，不强制先保存资料 |
| 摘要使用“性别” | 本地字段为目标估算公式的身体参数 | 保留本地字段语义，不把公式参数改造成新增身份字段 |
| 三组偏好含过敏原 | 本地规划读取 `avoidance` 与 `stable_preference` | 按现有白名单显示，不能为了三组卡片新增采集和持久化字段 |
| 热量区间及前端环图计算 | 本地使用后端营养报告，可能包含部分结果 | 图表仅映射已有数据；无上下界不编区间，无宏量值不反推克数 |
| 折叠记录和简单历史计划 | 本地另有记录详情、编辑与餐单版本页 | 保留真实详情入口；采用设计稿卡片外观，不删减页面和动作 |
| 五步模拟进度 | 本地安全 SSE 与权威快照驱动 | 只改进度组件表现；等待、可重试、终止和拒绝不能伪装成完成 |
| 示例设备、模拟退出/应用计划 | 本地有真实身份、会话和存档 | 保留真实请求与成功确认条件 |
| Tab 壳已有固定页头 | 本地页标题位于滚动内容中 | 后续页面框架项统一标题所有权，移除重复标题时保留焦点与可访问名称 |

## 5. 本次自动化检查

环境：Node `v22.23.2`，使用已有前端依赖；未更新依赖或测试快照。

| 检查 | 实际结果 |
|---|---|
| `npm run typecheck` | 通过 |
| `npm run build` | 通过；主 JS 615.48 kB，gzip 186.17 kB，有超过 500 kB 的构建提示；不在本项拆包 |
| `npm run lint` | 失败：`SafeProgressStages.tsx:8` 的组件热更新导出规则；`records/api/weeklyReview.ts:15` 的变量仅用于类型规则 |
| `npm test` 首轮 | 29 个文件、158 条测试；156 通过、2 失败，均在 `AnalyzePage.test.tsx` |
| 分析页单独复跑 | 13/13 通过；首轮长输入测试 5 秒超时，保存测试期望 1 次请求但观察为 0；根因未确认，不能认定为业务故障或已修复 |
| `npm test` 全量复跑 | 29/29 个文件、158/158 条测试通过；未修改测试或业务代码 |

首轮测试与静态检查、构建并行执行；单独复跑通过说明存在运行不稳定性，但不足以证明资源竞争是原因。

## 6. 本次未验证的范围

- 未运行 Playwright 跨栈测试：预检 Docker 返回 socket 访问权限不足，当前默认权限无法连接测试基础设施；未启动跨栈服务。本次没有自动审批拒绝记录。
- 未做 Codex 内置浏览器交互验收或新截图。当前工作是文档基线盘点，没有页面改动；已存在的截图和历史验收不能充当本次结果。
- 未重跑后端测试或真实模型评测；本次不改后端和数据计算。
- `frontend/ARCHITECTURE.md` 中仍将 plans 描述为未来占位，与当前源码不一致；本基线以路由和已实现组件为准，后续维护时同步修正文档。

本基线保留当时的 lint 问题和测试不稳定记录，不代表全部门禁通过。
