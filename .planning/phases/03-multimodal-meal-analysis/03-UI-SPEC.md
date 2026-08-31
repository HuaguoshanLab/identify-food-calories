---
phase: 03
slug: multimodal-meal-analysis
status: approved
shadcn_initialized: true
preset: base-nova / Base UI
created: 2026-08-31
reviewed_at: 2026-08-31
---

# Phase 03 — UI Design Contract

> Visual and interaction contract for the mobile H5 multimodal meal-analysis flow. It extends, and never weakens, `docs/ui/h5-foundation.md`.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | Tailwind CSS v4 + shadcn/ui |
| Preset | Existing `base-nova / Base UI` registry primitives |
| Component library | shadcn Base UI only; no second component library |
| Icon library | Lucide only: `Camera`, `ImagePlus`, `ShieldCheck`, `CircleAlert`, `CircleCheck`, `RefreshCw`, `MessageSquareText`, `ChevronRight` |
| Font | Existing system sans stack; no remote font download |
| Canvas | 430px-wide H5 baseline, 320px minimum, centered device container at >=768px |
| Color | Existing semantic tokens only: `background`, `foreground`, `card`, `muted`, `primary`, `destructive`, `border`, `ring` |

The UI/UX reference suggested a branded accent and remote type pairing, but both conflict with the existing H5 contract. They are rejected. This phase uses the existing semantic token system and system font stack.

---

## Spacing Scale

Declared values (all are valid under the H5 4px grid):

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | icon/text gaps, inline labels |
| sm | 8px | paired controls, candidate rows |
| md | 12px | normal page inset, card padding |
| lg | 16px | section separation, important card padding |
| xl | 20px | heading-to-content separation |
| 2xl | 24px | major card/section separation |

Exceptions: `10px` is allowed only where the cross-phase H5 contract permits compact horizontal page inset. No arbitrary margins; components use flex/grid `gap`.

---

## Typography

| Role | Size | Weight | Line Height | Contract |
|------|------|--------|-------------|----------|
| Page `h1` | 28px | 700 | 36px | One page title only: “分析这餐” |
| Section `h2` | 20px | 600 | 28px | Upload, progress, supplement, report, recovery sections |
| Card title/label | 16px | 600/500 | 24px | Upload source, food name, report item |
| Body | 15px | 400 | 24px | Privacy summary, food clues, recovery explanation |
| Supporting/status | 13px | 400/500 | 20px | Limits, confidence wording, disclaimer, error detail |
| Numeric nutrition | 14–16px | 500/600 | 20–24px | Always `tabular-nums`; unit adjacent to value |

All file inputs and numeric controls remain at least 16px. Long food names wrap; top-bar titles truncate; no text may force horizontal scrolling.

---

## Visual Hierarchy and Screen States

### Analysis tab root (`/app/analyze`)

It remains an `AppShell` tab root with the existing bottom navigation and one vertical content scroll area. It does not create a fullscreen upload root or a second fixed bottom action bar.

1. `h1` “分析这餐” and concise statement: “图片用于本次估算；营养数值由受控目录计算。”
2. **Primary upload card**: clearly visible first action, two equal 44px+ source controls:
   - `Camera` + “拍照” invokes the browser capture-capable file input when supported.
   - `ImagePlus` + “从相册选择” opens file selection.
   - Both controls have visible text, not icon-only semantics.
3. Collapsible/compact privacy row with `ShieldCheck`: “仅用于本次分析；完成或超时后删除。” The disclosure expands to distinguish local temporary deletion from third-party model processing; it must not claim provider zero retention.
4. Limits/help line and field-level error region directly under the upload control.
5. **Secondary text path**: a visually secondary button/link “改为文字描述这餐”. It is available on the root, but never competes with the primary upload CTA. It becomes the first recovery action after permanent visual failure.

### Local validation, upload, and recognition

- Before sending: selected file name and non-sensitive normalized format/size are shown; never preview EXIF, path, base64, GPS or raw binary.
- Validating/uploading/recognizing use one persistent status card with icon + text, `aria-live="polite"`, and no full-page spinner. The content shell and bottom navigation remain available.
- Stable user-visible stages are: “正在检查图片”, “正在识别菜品”, “等待补充信息”, “正在计算营养”, “正在校验结果”, “分析完成”. Internal graph node names, tokens, Provider names, raw error strings and thoughts never render.
- A pending request disables duplicate source controls and primary submission. It does not remove the current status explanation.

### Clarification state

- One card titled “需要补充的信息” contains all blocking questions. It lists already understood items first, then each missing field.
- A food ambiguity presents no more than three full-width selectable candidate buttons with radio-like selected state, preparation/portion clue and visible selected text. An “补充名称” text field follows when the options do not fit.
- A grams clarification uses a visible label, decimal `inputMode`, unit `克`, and explanation of whether the displayed number is a visual estimate. Submit remains one full-width primary button: “提交补充信息”.
- The page must not force a confirmation round for reliable unique items.

### Completed report

1. **Report header and summary first:** “营养分析报告”, total energy, and an explicit estimated/not-estimated qualifier. Do not invent a calorie range if the backend returns only deterministic point values; display error source in words instead.
2. **Food item cards next:** controlled food name, grams, “估算重量” badge/text if applicable, confidence wording that never pretends exact measurement, kcal and protein/fat/carbohydrate with tabular figures.
3. **Partial/unaccounted warning** precedes totals when any item is excluded; it names excluded items and says the meal total is incomplete.
4. **Correction last:** one labeled field with an example and primary “应用修正” action. It preserves the same thread and recalculates only affected items.
5. Phase 3 report confirmation means “确认本次分析结果” as a non-persistent acknowledgement/status; it cannot say “已记录” or create a history entry. Deleting the analysis keeps the existing destructive dialog.

### Failure and recovery

| Failure class | User title | Supporting copy | Primary recovery |
| --- | --- | --- | --- |
| Unsupported/dangerous image | “这张图片无法安全分析” | “请选择符合格式和大小要求的餐食图片。” | “重新选择图片” |
| Temporary service failure | “服务暂时不可用” | “系统已完成一次安全重试，未重复提交同一分析。” | “重试分析” |
| Outcome unknown | “正在确认本次请求状态” | “为避免重复收费，系统不会自动再次提交。” | Show resolved result if available; otherwise “发起新的分析” |
| Vision output invalid/permanent failure | “图片未能识别” | “你可以改用文字描述这餐。” | “改为文字描述这餐” |
| Budget/limit reached | “本次分析达到运行上限” | “请使用新的分析，或改为文字描述。” | “开始新的分析” / text fallback |

Every failure includes text, icon and a recoverable action. Red/destructive color is supplementary only. Error messages use `role="alert"`; ongoing status uses `aria-live="polite"`.

---

## Interaction and Accessibility Contract

- Every clickable upload source is a native `<button>`/associated `<input type="file">` control, minimum 44×44px, with visible label and programmatic name.
- Camera is progressive enhancement. If capture is unavailable or denied, the control explains this and retains “从相册选择”; it never blocks the file path.
- File validation errors attach with `aria-describedby` to the file input region; candidate selection exposes selected state; disabled/loading buttons preserve status text.
- Focus remains logical after file selection, validation failure, entering clarification, completed report and dialog closure. Modal delete confirmation uses existing `AlertDialog` focus management.
- 150–200ms color/opacity transition maximum; no entrance animation is required. All added motion observes global `prefers-reduced-motion` rules.
- 320px, 375px and 430px must retain a single-column layout with no horizontal scroll; 200% zoom preserves card text, source controls and recovery actions.
- Alt text is not used for user photos because the raw photo is not displayed; if a processed visual preview is introduced later, it must have neutral text such as “待分析的餐食图片”，and must still be deleted with the source.

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Page title | 分析这餐 |
| Primary upload actions | 拍照 / 从相册选择 |
| Upload privacy summary | 仅用于本次分析；完成或超时后删除。 |
| Privacy detail | 图片会由第三方视觉模型处理；本服务会在本次分析完成或超时后删除临时副本。 |
| Secondary text path | 改为文字描述这餐 |
| Empty/status state | 选择一张餐食图片，系统会识别菜品并在需要时向你确认。 |
| Estimated weight marker | 估算重量，可能与实际份量存在偏差。 |
| Partial result warning | 以下项目未计入总量：{items}。当前总量不是完整餐食。 |
| Temporary failure | 服务暂时不可用。系统未重复提交同一分析，请重试或改为文字描述。 |
| Outcome unknown | 正在确认本次请求状态。为避免重复收费，系统不会自动再次提交。 |
| Permanent vision failure | 图片未能识别。你可以改用文字描述这餐。 |
| Non-medical disclaimer | 本结果仅供一般饮食参考，不替代医疗建议。 |
| Destructive confirmation | 删除这次分析？这会关闭当前会话并提交数据清理请求，无法撤销。 |

Forbidden copy: “精准识别”、“绝对准确”、“零留存”、“已保存餐食”、“医疗建议”。

---

## Component and Registry Safety

| Registry | Blocks used | Safety gate |
|----------|-------------|-------------|
| Existing shadcn Base UI registry | `Button`, `Card`, `Input`, `Label`, `Alert`, `AlertDialog`, `Badge`, `Skeleton`, `Separator` | Existing approved registry; no new third-party block |
| Lucide | Existing icon package only | Use named SVG icons; never Emoji |

No third-party registry, visual preset, remote font or upload UI package may be added in Phase 3 without a separate safety review.

---

## Browser and Visual Acceptance Contract

- Preserve existing 430×932 screenshot baseline discipline. New/changed baselines require explicit human review; tests may not overwrite them.
- Component tests cover root upload controls, disclosure, unsupported file error, disabled/loading state, candidate selection, estimated-weight marker, partial report, recovery buttons and keyboard focus.
- Playwright uses the existing real auth/API setup to submit a real test image, exercise clarification, correction and text fallback; it must not insert database rows or copy tokens to manufacture results.
- Codex built-in browser verifies the actual H5 with a real file-selection path, including successful/clarification and error/recovery states. Camera behavior is verified when browser permission is available; otherwise report its unavailable capability explicitly rather than claiming camera acceptance.

---

## Checker Sign-Off

- [x] Dimension 1 Copywriting: PASS — concrete Chinese copy distinguishes estimate, deterministic nutrition, third-party processing and Phase 4 persistence boundary.
- [x] Dimension 2 Visuals: PASS — focal order and every root/processing/clarification/report/failure state are declared; no decorative/medical/gamified treatment.
- [x] Dimension 3 Color: PASS — existing semantic tokens only; status never relies solely on color.
- [x] Dimension 4 Typography: PASS — H5 type scale, numeric formatting and Chinese/system font rules are concrete.
- [x] Dimension 5 Spacing: PASS — 4px scale, one-column H5 shell and touch targets align with `h5-foundation.md`.
- [x] Dimension 6 Registry Safety: PASS — existing shadcn Base UI/Lucide only; no new registry or unsafe upload package.

**Approval:** approved 2026-08-31
