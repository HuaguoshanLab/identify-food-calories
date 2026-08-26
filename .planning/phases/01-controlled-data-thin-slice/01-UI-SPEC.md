---
phase: 1
slug: controlled-data-thin-slice
status: draft
shadcn_initialized: false
preset: "Vite + Base UI; Slate; Inter/System sans; Lucide; radius 8px; light-only"
created: 2026-08-26
---

# Phase 1 — UI Design Contract

> 面向“单菜受控热量计算”薄切片的视觉与交互契约。实现必须遵守本文件、`01-CONTEXT.md` 的 D-01 至 D-06，以及版本化 REST/OpenAPI 契约。

---

## Scope and Flow

- 仅交付一条路径：搜索并选择一道受支持菜品 → （可选）修改预填克数 → 点击“计算热量” → 查看单项热量。
- 默认主路径恰为 3 个动作：输入菜名/别名、选择菜品、点击“计算热量”。克数已由菜品的 `typicalServingGrams` 预填，修改克数是可选行为，不应阻塞默认路径。
- 不得在本阶段加入图片上传、菜品识别、多菜组合、热量区间、营养来源/授权展示、历史记录、删除或结果修正闭环。
- 克数输入只更新本地表单状态；仅点击主按钮才可发起 `POST /api/v1/calculations`。浏览器不得复制热量公式。

## Design System

| Property | Value |
|----------|-------|
| Tool | shadcn/ui（官方 CLI） |
| Initialization | 实施前必须在 `frontend/` 内通过官方 Vite/Base UI 初始化：`npx shadcn@latest init --template vite --base base`；在 CLI 交互中固定 Slate、Inter/System、Lucide、8px radius 与 light-only。生成并提交 `components.json`。当前仓库尚未初始化。 |
| Preset | Vite + Base UI；Slate；Inter/System sans；Lucide；8px radius；仅浅色主题 |
| Component library | shadcn/ui 的 Base UI registry；不得引入或保留 `@headlessui/react`，避免两个 primitive 系统并存。 |
| Icon library | Lucide React；仅用于输入状态、错误和加载等辅助含义，图标不得单独承担说明。 |
| Font | `Inter, ui-sans-serif, system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif`。中文优先使用系统字形；不伪造产品字体或品牌字标。 |
| Theme | light-only；不实现主题切换或深色模式。 |
| Radius | 8px（表单控件、卡片、按钮统一使用），圆角不超过此值。 |

---

## Layout and Responsive Contract

- Mobile-first。页面背景为 dominant surface；内容列宽 `100%`，内联 padding `16px`，在 `min-width: 640px` 时居中并限制为 `560px`。不使用桌面侧栏或两栏布局。
- 页面从上到下固定为：标题与一句说明 → 计算表单卡片 → 结果/反馈区域。首屏必须完整看到菜品搜索框、克数框和主按钮；结果在提交后显示于同一页面，自动滚动仅在结果不在可视区域时发生。
- 首屏的视觉焦点是计算表单卡片及其“计算热量”主按钮；成功计算后，焦点转为结果卡片中高对比、最大字号的 kcal 数字。标题不得与此操作焦点竞争。
- 标题区与表单卡片间距 `24px`；卡片内各字段间距 `16px`；输入标签与控件间距 `8px`；克数输入与单位“克”之间间距 `8px`。
- 可交互控件高度至少 `44px`，全宽显示；主按钮高度 `48px`。不使用悬停作为唯一反馈，移动端无需 hover 才能理解状态。
- 结果卡片仅在一次成功计算后显示。表单值被修改后，旧结果保留但必须显示“已修改输入，请重新计算”，且不能把旧数值表述为当前输入的结果。

## Component Inventory

| Component | Structure and behavior |
|-----------|------------------------|
| App shell | 单列 `<main>`；页面语言 `lang="zh-CN"`；标题 `h1` 为“计算这道菜的热量”。 |
| Search combobox | shadcn Base UI Combobox。可输入中文标准菜名或别名；选项展示“标准菜名”，有匹配别名时以次行小字显示“匹配：{alias}”。不能使用原生 `<select>`。 |
| Grams field | 有关联 `<label>` 的 decimal input，`inputMode="decimal"`，右侧静态单位“克”。选中菜品后以 API 返回的 `typicalServingGrams` 覆盖预填值；允许用户精确编辑。 |
| Primary button | 全宽、实心 accent 按钮，文字固定为“计算热量”。无有效菜品或克数时禁用；mutation pending 时禁用并显示“正在计算…”。 |
| Result card | 成功后显示标准菜名、`{grams} 克` 和强调数字“约 {kcal} 千卡”。不显示区间、来源、许可状态或配方说明。 |
| Status/alert | 搜索、计算、输入错误和请求失败均使用文本状态；错误使用 `role="alert"`，成功与加载使用 `aria-live="polite"`。 |

---

## Spacing Scale

Declared values (all are multiples of 4):

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Icon-to-text gap; matched-alias line separation |
| sm | 8px | Label-to-field gap; inline field-unit gap |
| md | 16px | Page gutter; card padding; default control gap |
| lg | 24px | Section separation; title-to-form gap |
| xl | 32px | Large card/result separation |
| 2xl | 48px | Narrow-screen top/bottom page padding |
| 3xl | 64px | Wide-screen vertical breathing room only |

Exceptions: interactive controls have a minimum 44px height and the primary CTA has a fixed 48px height; no other exceptions.

---

## Typography

Use exactly these four sizes and two weights. Do not introduce a third weight for visual decoration.

| Role | Size | Weight | Line Height | Usage |
|------|------|--------|-------------|-------|
| Label / helper | 14px | 400 | 1.5 | Field labels, match aliases, hints, errors |
| Body | 16px | 400 | 1.5 | Inputs, option names, explanatory text |
| Heading | 20px | 600 | 1.2 | `h1`, card title, result label |
| Display | 28px | 600 | 1.2 | Calculated kcal number only |

Numerals in grams and kcal use tabular figures when the chosen system font supports them. Body text never falls below 14px.

---

## Color

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `#F8FAFC` (Slate 50) | Page background and default open space |
| Secondary (30%) | `#FFFFFF` | Form and result card surfaces; input fill |
| Accent (10%) | `#0F766E` (Teal 700) | Primary CTA background, focused input/combobox ring, selected option indicator, and calculated kcal display only |
| Destructive | `#DC2626` (Red 600) | Input-validation and request-error icon/text only; no destructive user action exists in this phase |
| Primary text | `#0F172A` (Slate 900) | All headings, body and input text |
| Muted text / border | `#475569` / `#CBD5E1` (Slate 600 / 300) | Helper text; default control/card borders |

Accent reserved for: “计算热量” button, keyboard focus ring, selected combobox option marker, and the successful kcal number. It must not color all links, icons, backgrounds, or body copy.

Use `#FFFFFF` text on the accent CTA. Error feedback must include text and an icon/shape in addition to red; color alone is never a state signal.

---

## Interaction and State Contract

| State | Trigger | Required UI behavior and Chinese copy |
|-------|---------|--------------------------------------|
| Initial empty | No dish selected | Combobox placeholder: “搜索菜名或别名，例如：宫保鸡丁”。Below it show “从受支持菜品中选择一道菜后即可计算。” Primary button disabled. |
| Searching | Non-empty search query is fetching | Keep the typed query visible; options panel shows “正在搜索菜品…”。Do not clear a current selection or trigger calculation. |
| Search results | API returns matches | Show a keyboard-navigable list. Each option has standard name; matched alias appears only if applicable. `Enter` selects the highlighted option; `Escape` closes the list. |
| No dish found | Successful search returns zero results | Panel text: “未找到“{query}”。请换用常见菜名或别名再试。” Keep the query editable; show no fabricated near-match. |
| Search failed | Dishes request errors | Inline alert: “暂时无法搜索菜品。请检查网络后重试。” Provide a visible “重试搜索” button and retain the query. |
| Dish selected | User chooses an option | Close panel; display selected standard name; fill grams with `typicalServingGrams`; move focus to grams only when selection was made with keyboard, otherwise retain normal touch focus behavior. |
| Invalid grams: empty | Submit with no grams | Inline field error: “请输入克数。” Focus the grams field; do not send a request. |
| Invalid grams: format/range | Non-numeric, `<= 0`, or `> 3000` | Inline field error: “请输入大于 0 且不超过 3000 的克数。” Preserve typed value; do not silently coerce it and do not send a request. |
| Missing dish on submit | No valid selected dish | Inline error: “请先选择一道菜。” Focus the combobox; do not send a request. |
| Calculating | Valid form submitted | Primary CTA changes to “正在计算…”, becomes disabled, and a polite live region announces “正在计算热量”。Prevent duplicate requests. |
| Calculation success | API returns `{dishId, dishName, grams, kcal}` | Result card announces “计算完成”。Copy: heading “这道菜约含”； display “{kcal} 千卡”； detail “{dishName} · {grams} 克”。Use backend-provided result only. |
| Calculation failed | Network error, timeout, or 5xx | Alert: “暂时无法计算热量。请检查网络后重试。” Show an enabled “重新计算” button; keep the selected dish and grams unchanged. |
| API validation/not supported | API rejects selected dish or grams | Alert uses API’s safe structured message; fallback copy: “菜品或克数无效，请检查后重新计算。” Return focus to the relevant field. |
| Stale result | Selected dish or grams changes after success | Keep result visually subdued and show “已修改输入，请重新计算。” The stale kcal must not use accent color until recalculated. |

The UI may debounce search requests by 250ms, but debounce is only for `GET /api/v1/dishes?query=`. Grams changes never invoke `POST /api/v1/calculations`.

---

## Accessibility and Motion

- Use semantic `main`, `form`, `label`, `button`, and listbox/combobox semantics supplied by Base UI. Every input has a visible text label; placeholder text is never the sole label.
- Combobox supports keyboard arrows, Enter, Escape, and focus return. Its open state, active option, result count, loading, and errors must be announced through its accessible name/status text.
- On client validation failure, focus the first invalid field. On server validation failure, map the structured field error to the corresponding control with `aria-invalid="true"` and `aria-describedby` pointing to the visible error text.
- Maintain a visible `2px` accent focus ring with at least `2px` offset. Focus is never removed or replaced only by a color fill.
- Icons have `aria-hidden="true"` when adjacent text already names the state. Icon-only controls are not part of this phase; if introduced later they require an accessible name and 44px target.
- Use only opacity/color transitions of 150ms for combobox, button and result state. Respect `prefers-reduced-motion: reduce` by removing transition duration. No automatic carousel, count-up animation or layout-shifting spinner.

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Page title | 计算这道菜的热量 |
| Intro | 搜索一道受支持的菜品，确认克数后即可计算。 |
| Primary CTA | 计算热量 |
| Empty state heading | 先选择一道菜 |
| Empty state body | 搜索菜名或别名，系统会填入常见外卖份量；你也可以自行修改。 |
| No-result state | 未找到“{query}”。请换用常见菜名或别名再试。 |
| Search error | 暂时无法搜索菜品。请检查网络后重试。 |
| Calculation error | 暂时无法计算热量。请检查网络后重试。 |
| Success result | 这道菜约含 {kcal} 千卡 |
| Stale-result notice | 已修改输入，请重新计算。 |
| Destructive confirmation | 不适用：本阶段没有删除或其他破坏性操作。 |

Do not claim “精准”“零误差”“称重级”“医疗级”，也不要在 Phase 1 解释图片、模型、热量区间或营养数据来源。

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official (Base UI) | `button`, `card`, `input`, `label`, `alert`, `combobox` | not required — official registry only |
| Third-party registries | none | not applicable — no third-party block may be added without `shadcn view` review and recorded evidence |

---

## Implementation Notes for Planner and Executor

- Initialize the Vite frontend first, then run the official shadcn Vite/Base UI CLI from `frontend/`; verify `components.json` exists and records the selected system before adding components. Do not add Headless UI.
- Use TanStack Query for dish-search query state and calculation mutation state. Search errors and calculation errors must remain separate, exactly as in the state table.
- The result component consumes the FastAPI response. The frontend must not calculate, round, or infer kcal from per-100g data.
- UI acceptance tests must cover keyboard combobox selection, alias match display, auto-filled grams, invalid grams with zero POST calls, pending duplicate-submit prevention, success result, no matches, search failure, calculation failure, and stale-result notice.

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending
