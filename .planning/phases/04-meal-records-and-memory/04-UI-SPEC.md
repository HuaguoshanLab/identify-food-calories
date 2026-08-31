---
phase: 4
slug: meal-records-and-memory
status: approved
shadcn_initialized: true
preset: base-nova / Base UI
created: 2026-08-31
---

# Phase 4 — UI Design Contract

> Phase 4 的用户 H5 视觉和交互合同。实现、测试与浏览器验收必须遵守本文件及 `docs/ui/h5-foundation.md`；若冲突，以 H5 基座规范为准。

---

## Scope and Route Contract

| Route | Layout | Responsibility |
|---|---|---|
| `/app/analyze?thread=:threadId` | `AppShell` | 已完成报告卡末尾提供显式“确认并保存”。 |
| `/app/records` | `AppShell` | 日期倒序分组的已保存餐食、局部 loading/error、真实空态。 |
| `/app/records/:recordId` | `DetailLayout` | 餐食快照详情、顶部编辑入口、底部危险操作区。 |
| `/app/records/:recordId/edit` | `DetailLayout` | 可编辑用餐时间与允许修改的餐食字段；固定底部保存操作。 |
| `/app/me/memories` | `DetailLayout` | 长期记忆列表、来源/时间、编辑与删除。 |
| `/app/me/memories/:memoryId/edit` | `DetailLayout` | 单条记忆编辑；固定底部保存操作。 |

- `/app/records` 保持底部 Tab；详情、编辑和记忆管理页隐藏 Tab 并保留返回顶栏。
- 所有导航使用 React Router 真路径与正常 history push。删除成功返回上一层的有效列表；保存成功回到相应详情，不能用全局 replace 清空用户历史。
- 本阶段不增加趋势图、筛选面板、数据导出、撤销删除或示例餐食。

## Design System

| Property | Value |
|----------|-------|
| Tool | Tailwind CSS v4 + shadcn/ui official Base UI registry |
| Preset | Existing `base-nova` / Base UI; no new preset or component library |
| Component library | Base UI primitives through existing `frontend/src/components/ui/` |
| Icon library | Lucide React only |
| Font | Existing system sans-serif; no remote font loading |
| Visual direction | 可信、克制、清爽的单列饮食工具；信息优先，非医疗机构、非健身游戏化 |

`ui-ux-pro-max` 的“Minimal Single Column”、明确 CTA、空态引导、确认弹窗、可见焦点与局部加载建议适用。它推荐的紫/橙色、远程字体、滚动吸附和高刺激动效与已冻结 H5 基座冲突，明确拒绝。

## Spacing Scale

沿用 `docs/ui/h5-foundation.md` 的 4px 网格与既有例外，不新增私有 spacing token。

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | 图标与文字的紧凑间隙 |
| sm | 8px | 列表内部、日期标签与次级操作 |
| compact | 10px | 紧凑列表的横向内边距（既有 H5 例外） |
| page | 12px | 记录列表、详情与表单的常规横向边距 |
| md | 16px | 卡片重点内边距、区块间距与空态 |
| lg | 20px / 24px | 详情区块和页面重大分隔 |

固定底部保存栏与危险操作区使用 `padding-bottom: max(16px, env(safe-area-inset-bottom))`；页面内容预留其高度，不允许被按钮遮挡。

## Typography

| Role | Size | Weight | Line Height | Usage |
|------|------|--------|-------------|-------|
| Page heading | 28px | 700 | 36px | 每页唯一 `h1`，如“餐食记录”“饮食偏好与记忆” |
| Section heading | 20px | 600 | 28px | 日期组、营养汇总、记忆类别 |
| Card title | 16px | 600 | 24px | 餐食摘要、记忆内容 |
| Body | 15px | 400 | 24px | 说明、菜品与来源文本 |
| Supporting | 13px | 400 | 20px | 时间、版本、来源、错误说明 |
| Numeric value | 15–16px | 500–600 | 24px | kcal、克数、日期；必须使用 `tabular-nums` |

长餐食名称最多两行；顶栏标题单行截断。所有编辑表单输入文字至少 16px，避免 iOS 自动缩放。

## Color and States

只使用现有 shadcn/Tailwind 语义 token，业务组件禁止十六进制色值、私有灰阶或第二套状态色。

| Role | Token / Value | Usage |
|------|---------------|-------|
| Surface | `background`, `card`, `muted` | 页面、分组标题、卡片与 skeleton |
| Content | `foreground`, `muted-foreground` | 主文本、辅助文本、版本与来源 |
| Primary action | `primary`, `primary-foreground` | “确认并保存”“保存修改”且每个操作区仅一个 |
| Focus | `ring` | 所有键盘焦点与可编辑控件 |
| Destructive | `destructive`, `destructive-foreground` | “删除记录”“删除记忆”及确认弹窗最终操作 |
| Success | Existing semantic success treatment or text + `CircleCheck` | “已保存”“已删除”；不得只靠绿色表达 |

Accent reserved for：当前 Tab、单个主提交按钮、可见焦点和明确成功状态。不得用 accent 装饰所有卡片、列表或次级链接。`.dark` 只作为语义 token 兼容目标，不新增主题切换。

## Page and Interaction Contracts

### 1. 分析报告确认保存

- 仅在线程为 `completed`、报告完整且未保存时，于报告卡片末尾显示一个全宽 44px 主按钮：`确认并保存`。
- 按下后按钮进入不可重复提交的 loading 状态（`正在保存…`）；失败在按钮附近显示问题与可恢复操作，不把浏览器错误或后端细节原样暴露。
- 成功后原位变为带文字与图标的 `已保存` 状态，并提供次级入口 `查看记录`；不得自动跳走，避免用户失去报告上下文。
- 该按钮不是“重新确认营养结果”；它只创建用户明确确认的权威餐食记录，报告中估算重量仍保留原有不确定性标记。

### 2. 餐食记录根页

- `h1` 为“餐食记录”；按 `consumed_at` 的本地日期倒序分组。日期组标题为语义 `h2`，使用如“今天”“昨天”或完整日期，禁止用无意义的时间线装饰。
- 每个可点击记录项至少包含用餐时间、餐食名称摘要、总热量和保存状态；使用真实 `Link`/button 语义、44px 最小命中区、可见 hover/pressed/focus 状态。
- 首屏和刷新期间保留 AppShell/Tab，仅在内容区显示与最终记录项尺寸相符的 skeleton；错误态包含“暂时无法加载记录”和“重新加载”操作。
- 空态文案固定为：标题 `还没有已保存的餐食`；正文 `完成一次分析后，确认保存的餐食会出现在这里。`；唯一主操作 `去分析`，跳转 `/app/analyze`。禁止假数据、示例记录和全屏空白。

### 3. 餐食详情与编辑

- 详情页标题为“餐食详情”；显示实际用餐时间、保存/更新时间、目录/计算版本、来源状态、整餐汇总与逐项营养。时间、克数、kcal 和营养数值使用 `tabular-nums`。
- 顶栏右侧提供文字或 Lucide 图标的 `编辑` 操作，并有可访问名称。编辑进入独立 `/edit` 路由，不允许详情行内自动保存。
- 编辑页只展示可修改字段；每项有可见 label、单位提示和字段级校验。固定底部唯一主按钮为 `保存修改`，加载时为 `正在保存…`，成功后返回详情并显示安全成功提示。
- 详情/编辑页的末尾危险操作区以弱分隔线隔开，包含 `删除这条记录` 次级危险按钮。点击后打开 Base UI AlertDialog：标题 `删除这条记录？`；说明 `删除后会立即停止在记录和后续建议中使用，且无法撤销。`；取消 `保留记录`；最终操作 `确认删除`。
- 删除确认后立即返回并从列表移除，显示 `已删除`；不展示 Mem0、pgvector、同步进度、Provider、内部 ID 或重试信息。

### 4. “我的”中的记忆管理

- `/app/me` 在既有账号资料、登录会话之下新增真实入口 `饮食偏好与记忆`，说明文本 `查看和管理会影响后续建议的偏好。`，采用既有设置列表与右箭头模式。
- 记忆管理页 `h1` 为“饮食偏好与记忆”，按类别展示 `目标`、`忌口`、`稳定偏好`。每项显示内容、来源和创建/更新时间；临时表达自动保存的项目不得被包装成医疗/过敏诊断。
- 记忆条目进入独立编辑页；编辑后来源显示为 `用户手动维护`。列表空态只显示真实空状态和返回操作，不承诺系统会自动学习。
- 删除入口位于记忆详情/编辑页末尾危险操作区，使用与餐食完全相同的确认、焦点、立即移除和安全反馈语义。

## Copywriting Contract

| Element | Copy |
|---------|------|
| Report primary CTA | `确认并保存` |
| Report success | `已保存` / `查看记录` |
| Records empty heading | `还没有已保存的餐食` |
| Records empty body | `完成一次分析后，确认保存的餐食会出现在这里。` |
| Records empty CTA | `去分析` |
| Memory entry | `饮食偏好与记忆` — `查看和管理会影响后续建议的偏好。` |
| Loading submit | `正在保存…` / `正在保存修改…` |
| Load error | `暂时无法加载记录` — `请检查网络后重新加载。` |
| Delete confirmation | `删除这条记录？` / `删除后会立即停止在记录和后续建议中使用，且无法撤销。` |
| Delete confirmation actions | `保留记录` / `确认删除` |
| Delete success | `已删除` |
| Retrieval disclosure | `已参考你的忌口：{memory_text}` |

## Accessibility and Responsive Acceptance

- 使用 `h1 → h2 → h3`、`main`、`nav` 和真实按钮/链接；图标按钮均有 `aria-label`。字段的 `label` 与 `id` 明确关联。
- Base UI dialog 必须 focus trap，关闭后焦点回到触发删除的操作；删除不可在键盘焦点不明的情况下执行。
- 加载、空态、错误、成功、估算/来源和危险状态一律使用文字/图标加颜色，不只用颜色；动态状态用 `aria-live="polite"`。
- 44×44px 最小命中区；320px 与 200% 缩放无横向滚动；430×932 为视觉基线；768px 以上仍在 430px 设备容器内呈现。
- 只保留 AppShell 或 DetailLayout 各自唯一纵向滚动区；固定底部栏不覆盖内容；动效 150–200ms 且 `prefers-reduced-motion` 下显著弱化。

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official Base UI | Existing `Button`、`Card`、`Input`、`Alert`、`AlertDialog`、`Skeleton`、`Badge`、`Separator` | Official existing components only; no third-party registry or new UI library |

## Checker Sign-Off

- [x] Dimension 1 Copywriting: PASS — 明确保存、删除、空态、错误、来源提示均有具体中文文案。
- [x] Dimension 2 Visuals: PASS — 单列 H5、页面/路由、信息层级、loading/empty/error/success 具体且与既有基座一致。
- [x] Dimension 3 Color: PASS — 仅语义 token；明确了 primary/destructive/focus 的受限用途。
- [x] Dimension 4 Typography: PASS — 字号、字重、行高、数字表现和中文截断规则可执行。
- [x] Dimension 5 Spacing: PASS — 4px 网格、既有例外、固定栏安全区和页面边距明确。
- [x] Dimension 6 Registry Safety: PASS — 限定已有官方 shadcn Base UI 与 Lucide，禁止新增注册表/库。

**Approval:** approved 2026-08-31
