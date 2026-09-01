---
phase: 5
slug: diet-planning-subgraph
status: draft
shadcn_initialized: true
preset: b0 (base-nova/Base UI; components.json baseColor=slate; current CSS tokens are neutral)
created: 2026-09-01
---

# Phase 5 — UI Design Contract

> Visual and interaction contract for the diet-planning subgraph. Generated from the locked Phase 5 context, technical research, existing H5 foundation, and installed UI/UX guidance. It is the implementation source of truth for `/app/plans` and `我的 → 个人资料`.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | shadcn/ui official registry only |
| Preset | `b0` — Base UI `base-nova`, Inter, default radius; retain the committed `components.json` base color `slate` and existing neutral semantic CSS tokens |
| Component library | `@base-ui/react` through shadcn primitives |
| Icon library | Lucide only |
| Font | Existing system sans stack: `Inter, ui-sans-serif, system-ui, sans-serif`; do not load a remote font |
| Source | `frontend/components.json`, `npx shadcn info`, `docs/ui/h5-foundation.md` |

Keep the existing mobile-first H5 shell: `/app/plans` is an `AppShell` Tab root with its one `PageScrollArea` and persistent four-item bottom navigation. Personal-profile pages use `DetailLayout`, so they have the existing back header and no bottom navigation. Do not create a second page-height container, a second vertical scroller, a sidebar, a desktop dashboard, or a brand palette.

Use the existing `Card`, `Alert`, `AlertDialog`, `Badge`, `Button`, `Input`, `Label`, `Separator`, and `Skeleton` primitives. Add only official shadcn Base UI primitives if implementation requires `RadioGroup`, `Select`, `Textarea`, `Form`, or `Progress`; feature components remain in `features/plans/`, while `app/` owns only the “我的” link composition.

---

## Spacing Scale

Declared values for new Phase 5 components (all are multiples of 4):

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Icon-to-label gap; metric label-to-value spacing |
| sm | 8px | Chip groups, compact rows, adjacent controls |
| md | 16px | Default card padding, form-field gap, page section gap |
| lg | 24px | Plan-page top/bottom section spacing; major card padding when needed |
| xl | 32px | Empty/refusal-state breathing room |
| 2xl | 48px | Separation only inside a low-information state |
| 3xl | 64px | Never inside a standard plan result; reserved for a full empty state |

Exceptions: none for new Phase 5 content. Reuse the H5 shell’s existing 12px page-area convention rather than overriding layout padding. Every primary touch target, edit/delete icon action, link row, and dialog action has a minimum 44×44px hit area. Fixed action bars must include `max(16px, env(safe-area-inset-bottom))` bottom padding.

---

## Typography

Use exactly two weights in new Phase 5 components: regular `400` and semibold `600`. Use `tabular-nums` for energy, macro grams, portions, ranges, dates, and replan counts. Do not show nutrition decimals unless the deterministic public API explicitly requires one; this UI defaults to whole kcal and whole grams.

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Display / page `h1` | 28px | 600 | 1.286 (36px) |
| Section `h2` | 20px | 600 | 1.4 (28px) |
| Card title, form control, body | 16px | 400 or 600 for title | 1.5 (24px) |
| Supporting copy, chips, metric labels | 13px | 400 | 1.538 (20px) |

Use semantic `h1 → h2 → h3` order. Inputs always render at 16px to prevent iOS zoom. A card title may use 16px/600; it is not a fifth size. Long recipe names wrap to two lines; navigation and detail-header titles remain one-line truncated by the existing shell.

---

## Color

Use only existing semantic CSS tokens. These proportions describe visual area, not new hard-coded color values. The current light values are recorded solely for audit; components must use the token names so the pre-existing `.dark` reservation keeps working.

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `background` / current `oklch(1 0 0)` | Page canvas, form surface, persistent disclaimer background |
| Secondary (30%) | `card`, `secondary`, `muted` / current near-white neutral tokens | Meal cards, daily overview, inactive metric rows, bottom-navigation surface |
| Accent (10%) | `primary` and `ring` / current neutral semantic tokens | Only the specific items listed below |
| Destructive | `destructive` / current `oklch(0.577 0.245 27.325)` | Delete-profile button, destructive confirmation, deletion failure/success context where appropriate |
| Status | Existing semantic `foreground` + `muted`, `destructive`, and an approved success token if one already exists | Each status must also include text and an icon; do not introduce private green/amber/red hex values |

Accent reserved for: the one primary action in the visible region (`生成今日餐单`, `保存个人资料`, or `新建计划`), the selected activity/goal/speed option, the active “计划” bottom-navigation item, and the visible keyboard focus ring. It is not a decoration color, a card background, or a substitute for a nutritional state. `偏低`、`适中`、`偏高`, relaxed constraints, errors, and refusals must be understandable from their icon and text without color.

Cards use a 1px `border`, base radius 8–10px, and no default shadow. Do not add gradients, glass effects, large illustrations, dense charts, emoji icons, or medical/fitness-gamification graphics.

---

## Screen and Navigation Contract

### `/app/plans` — plan Tab root

1. Keep the existing bottom navigation visible and make “计划，当前页面” the real route-derived current item. The page starts with `h1` “计划” and one concise purpose line: “根据已确认的资料和偏好生成一日三餐参考。”
2. Immediately below the heading, show an inline, non-dismissable `Alert`: “普通饮食参考，不替代医疗建议。” It is informational, not a consent gate and not a modal. Repeat the same sentence in the footer of every generated or adjusted plan.
3. When no active plan is present, render the profile-and-goal review form in this order: body data → activity level → goal and conservative speed → confirmed dietary preferences → “本次使用” persistence control → one fixed bottom action, “生成今日餐单”. Do not show fake food suggestions, recipe imagery, charts, or an empty plan grid before a successful result.
4. When an active plan is present, render daily overview → any relaxation notice → breakfast/lunch/dinner cards → adjustment form → persistent disclaimer. Only the content area scrolls.
5. The route must remain reachable with a normal browser Back action. Do not redirect the user away from `/app/plans` while a profile form has unsaved edits; show a leave-confirmation only when an implementation actually has dirty local form state.

### `我的 → 个人资料`

Add a native `SettingsLinkRow` in “我的”, titled “个人资料”, description “管理身体资料与计划目标”, and a Lucide body/target-appropriate icon. It links to the centralized static route `/app/me/profile`; add this path to `routePaths.ts` and the protected-route set. Keep “饮食偏好与记忆” as its distinct existing link.

`/app/me/profile` uses `DetailLayout` titled “个人资料”. It has three explicit modes:

- View: present only body data and goal/speed/activity values in label-value rows; never render avoidance or taste preferences here. Actions are “编辑个人资料” and a separate destructive “删除个人资料”.
- Empty: heading “还没有保存个人资料”, body “请先在计划页填写身体资料和目标，保存后会在这里显示。”, link “去计划页填写”.
- Edit: use visible labels, units, immediate field errors, a single fixed primary action “保存个人资料”, and a secondary text link “管理饮食偏好” to `/app/me/memories`. It must not contain avoidance/taste inputs or a second preference API write path.

No personal-profile value is written merely because it was prefilled or changed in the plan review. The user must opt in with the plan form’s explicit `保存到个人资料` control or use “保存个人资料” on this detail page.

---

## Profile and Goal Form Contract

All labels are visible and programmatically associated with their controls. Numeric fields use a numeric input mode and a fixed visible unit suffix; placeholder text is an example only. Validate client-side with the same ranges/enums exposed by the public API, then show the server’s authoritative error beside the relevant field without clearing other entered values.

| Field / control | Required interaction and copy |
|-----------------|-------------------------------|
| Height | Required numeric field, label “身高”, unit “cm”. |
| Weight | Required numeric field, label “体重”, unit “kg”. |
| Age | Required numeric field, label “年龄”, unit “岁”; an under-18 response transitions to the high-risk refusal state, never to a plan. |
| Formula selection | Required explicit server-supported option; label “用于目标估算的身体参数”. Never infer or silently default it. Explain that the result is an estimate, not a diagnosis. |
| Activity | Required radio group titled “日常活动水平”. The five options are `久坐`（大部分时间坐着，几乎不运动）, `轻度`（每周有少量轻松活动）, `中度`（每周规律中等强度活动）, `高度`（大多数天有较高强度活动）, `非常高`（高强度训练或体力工作为主）. Each option has a 44px target and a visible selected state. |
| Goal | Required radio group driven by the safe server enum; label “本次目标”. No freeform disease, treatment, medication, or extreme weight-control goal field. |
| Goal speed | Required conservative preset selector driven by `target-policy.v1`; label “目标速度”. Do not offer a custom numeric speed input. If a requested speed is outside policy, show the refusal copy below. |
| Preference summary | Required review section titled “本次饮食偏好”. It reads the existing memory ledger as concise summaries: “忌口：已确认 …” / “口味：已确认 …”, or “忌口：本次确认无” / “口味：本次确认无”. A real link “管理饮食偏好” opens the existing memory page. This screen never provides avoidance/taste text fields, chips with delete controls, or a duplicate editor. |
| Persistence | A separate, clearly labelled control: “将本次身体资料和目标保存到个人资料”. It defaults to its current saved state only after the user can see it; it never writes silently. It does not alter preference memory. |

Before the form’s only primary action, place supporting copy: “生成前会由系统计算目标区间，并校验餐单是否符合已确认约束。” The loading action label is “正在生成餐单…”, is disabled against duplicate submits, and is accompanied by a local status message rather than a frozen screen.

---

## Plan Result Contract

### Daily overview

Place a single `h2` “今日总览” directly after the page header. The overview first names the current goal in plain language, then shows four metric rows/cards in this fixed order: energy, carbohydrate, protein, fat. Every metric uses the identical three-part grammar:

```text
目标：{lower}–{upper} {unit}  ·  计划：{value} {unit}  ·  {偏低 | 适中 | 偏高}
```

Example: `目标：1,800–2,000 kcal · 计划：1,920 kcal · 适中`. The target is a range; never render a single target as a medical prescription. The state label is visible text plus a Lucide status icon. The card may additionally say “由确定性营养计算得出” but must not expose tool names, formulas, raw validator fields, model/provider output, or chain of thought.

### Three meal cards

Render exactly three cards in the fixed order `早餐` → `午餐` → `晚餐`. Each card contains:

- `h3` meal name and its nutrition subtotal using the same range/value/state grammar where applicable;
- one or more controlled dish rows, each with the standard dish name, a suggested gram amount or controlled portion, and compact method/flavour tags;
- a concise constraint line, for example “已遵守：不吃香菜 · 偏好清淡”; it must state the matched user-facing constraint rather than a hidden rule ID;
- no complete recipe, ingredient expansion, cooking steps, shopping list, source/license metadata, recommendation score, or repeated macro dashboard.

Dish rows are informational, not buttons. The only plan-changing affordance is the adjustment form below all three cards; this prevents accidental meal replacement and keeps the initial MVP focused on natural-language feedback.

### Adjustment and recovery

Below the cards, show `h2` “调整这份计划”, a labelled textarea “告诉我们想换什么”, example placeholder “例如：午餐换清淡一些，或不吃香菜”, and the one primary action for that region, “提交调整”. Include helper text: “系统默认只替换直接受影响的菜品，其余餐次和已确认约束会保留。”

On a successful replacement:

1. Return focus to a polite live summary: “已更新{早餐/午餐/晚餐}，其余餐次保持不变。”
2. Add a visible `Badge` “已调整” to the affected meal card only.
3. Under that card, say which old item was replaced, which new user-facing constraint was met, and whether the daily nutrition still falls within each target range.
4. Keep the three-card order and leave the unaffected cards unchanged. Do not ask for an extra confirmation before the user can make another adjustment.

If the feedback target is ambiguous, pause at a contained choice state rather than guessing. Heading: “请确认要调整哪一餐”; body: “你的要求可能影响多餐，请选择要替换的餐次。” Offer only breakfast/lunch/dinner choices and “返回修改描述”; do not expose graph state or all candidate recipes.

---

## Safe Status, Relaxation, and Refusal States

### Safe business-progress events

Render a compact current-state row with `aria-live="polite"`; update its text, not a raw token stream or artificial percent progress. The only allowed backend-to-UI messages are the following stable business summaries:

| Event state | User-visible copy |
|-------------|-------------------|
| `reading_context` | 正在读取已确认的资料与饮食偏好… |
| `calculating_targets` | 正在计算每日目标区间… |
| `composing_plan` | 正在组合一日三餐… |
| `validating_plan` | 正在校验营养与已确认约束… |
| `complete` | 计划已生成。 |
| `needs_input` | 需要你补充或确认信息后继续。 |

Never render model text, provider/model names, prompt fragments, tool calls/results, replan internals, costs, token counts, checkpoint IDs, thread IDs, or hidden exclusions.

### Relaxed energy/macro targets

When deterministic validation reports a permitted relaxation, place a persistent `Alert` immediately below the daily overview and before meal cards. It must be expanded by default and contain all four facts:

1. Heading: “已按现有约束生成餐单，但目标已调整”。
2. Exact affected metric and original target range.
3. Final plan value and the precise deviation amount/direction.
4. The short reason returned from the safe business DTO, followed by “忌口和你明确排除的食物未被放宽。”

Do not hide this in a tooltip, toast, collapsed disclosure, or a vague “已优化” badge. Only energy and macro target ranges may relax; never present avoidance, explicit exclusions, or health-safety boundaries as negotiable.

### Replan limit

At three automatic replans, replace the adjustment submission area with a non-dismissable `Alert`:

> 已完成 3 次自动调整，无法在当前约束内继续修改。你可以新建计划，或修改身体资料和目标后再试。

Its actions are “新建计划” (primary; begins a clearly new planning thread) and “修改个人资料” (secondary link). Do not send a fourth request, silently reset the count, or display a retry button that would violate the bound.

### High-risk health refusal

For `BLOCK_HEALTH_SCOPE`, server-rejected unsafe speed, or a direct high-risk request, replace plan output with an inline `Alert` that receives focus and has `role="alert"`:

> 我们不能为你当前描述的情况生成个性化餐单。孕期或哺乳期、未成年人、疾病或用药、进食障碍或自伤，以及极端减重/增重目标需要专业评估。请咨询医生或注册营养师。你仍可以查看通用、非医疗的均衡饮食原则。

Do not show a candidate plan, an energy target, recipe cards, a “继续生成” action, or a path to bypass the refusal. Preserve the normal shell navigation. A user may correct accidentally entered basic profile values, but the client must not relabel a refusal as an ordinary validation error.

### Loading, empty, and recoverable error

Keep the page shell, heading, disclaimer, and entered form values visible. Use dimension-matched `Skeleton` only for data-dependent summary/card space. For a recoverable API or stream failure, use a local `Alert`:

> 暂时无法生成计划。请检查资料和网络后重试；若问题持续，请稍后再试。

Provide “重新尝试” and retain entered values. Field-level API errors appear beside their control; page-level alerts are only for cross-field, loading, or service failures. Error and success messages must be announced through `role="alert"` or an appropriate live region.

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Plan primary CTA | `生成今日餐单` |
| Plan adjustment CTA | `提交调整` |
| Profile save CTA | `保存个人资料` |
| Empty state heading | `还没有保存个人资料` |
| Empty state body | `请先在计划页填写身体资料和目标，保存后会在这里显示。` |
| Plan error state | `暂时无法生成计划。请检查资料和网络后重试；若问题持续，请稍后再试。` |
| Persistent disclaimer | `普通饮食参考，不替代医疗建议。` |
| Replan-limit state | `已完成 3 次自动调整，无法在当前约束内继续修改。你可以新建计划，或修改身体资料和目标后再试。` |
| High-risk refusal | `我们不能为你当前描述的情况生成个性化餐单。请咨询医生或注册营养师。` |
| Delete-profile confirmation | `删除个人资料后，后续计划将不再读取这些身体资料和目标。此操作无法撤销。` |
| Delete-profile actions | Secondary `取消`; destructive primary `确认删除` |
| Delete-profile success | `个人资料已删除。后续计划不会再读取这些资料。` |

The delete confirmation uses the existing `AlertDialog`, explicitly names the profile data being removed, keeps the destructive action visually distinct, and returns focus to the “个人资料” heading after success. Never delete current long-term preferences; they are owned by the memory page.

---

## Accessibility and Interaction Quality

- Preserve one `main` landmark and one vertical page scroller. Use `nav`, real `Link`/`NavLink`, native `button`, and semantic headings; never make a clickable `div`.
- Every icon-only control needs a Chinese `aria-label`; decorative Lucide icons are `aria-hidden`. Give selected radio options both a programmatic checked state and visible text, never color alone.
- Associate every `Label` and input by `htmlFor`/`id`; make required status programmatically available. Put validation copy next to the failing field and use `aria-describedby`/`aria-invalid`.
- Announce dynamic progress politely; errors/refusals use `role="alert"`. On successful replacement, move focus to the updated summary; on route entry, retain the existing heading-focus behavior.
- The delete dialog has a descriptive relationship, Escape/cancel close behavior, visible focus, and a 44px minimum for both actions. It must not delete on backdrop click or accidental keyboard focus alone.
- Maintain WCAG AA contrast through semantic tokens, visible focus rings, 150–200ms color/opacity feedback only, and the repository’s global `prefers-reduced-motion` override. No hover-only information.
- Verify 320px, 375px, 430px, and centered 768px+ device-container layouts, 200% zoom, keyboard traversal, long dish names, large numeric values, loading, empty, service-error, success, relaxed-target, replan-limit, and high-risk-refusal states. There must be no horizontal overflow or fixed action obscured by a safe area.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official Base UI | Existing: `alert-dialog`, `alert`, `badge`, `button`, `card`, `input`, `label`, `separator`, `skeleton`; if needed: official `radio-group`, `select`, `textarea`, `form`, `progress` | not required — official registry; initialization verified with `npx shadcn info` on 2026-09-01 |
| Third-party registry | none | not applicable — project forbids third-party registry blocks |

No block, component, or template may be imported from a third-party registry. Consequently no third-party `shadcn view` vetting is applicable.

---

## Implementation Boundaries

- The browser only renders validated public DTOs and safe business events. It does not calculate energy, macro targets, target state, relaxation deltas, exclusions, repeat scores, or health-risk decisions.
- Do not add a separate plans event parser if `useAgentEventStream` already supports snapshot/replay behavior. Map the safe planning event enum to the six user-visible messages above.
- Personal profile is the only authoritative body/goal editing surface. The memory feature is the only avoidance/stable-taste editing surface. The plan page reviews both and can capture explicit natural-language feedback through the established audited memory path, but never maintains a parallel preference form.
- This phase ends at a controlled single-day three-meal plan. Recipes, cooking steps, ingredient details, shopping lists, nutritional trend charts, weekly review, and administration are out of scope.

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending
