---
phase: 1
slug: engineering-auth-foundation
status: verified
shadcn_initialized: false
preset: "planned: base-ui, slate, teal, 0.5rem radius"
created: 2026-08-27
---

# Phase 1 — 工程、身份与权限基座 UI Design Contract

> Phase 1 前端视觉与交互的单一事实来源。范围仅包含产品落地页、登录、注册与邮箱验证码、密码重置、隐私/条款、认证启动、最小 `/app`、会话管理和退出。Phase 1 的 admin probe 仅是后端契约；用户 H5 不包含 `/admin` 页面，独立 `admin-frontend/` 延后到 Phase 6。

---

## Design System

| Property | Value |
|----------|-------|
| Tool | shadcn/ui（Phase 1 实现时初始化；当前仓库尚无 `components.json`） |
| Preset | Base UI primitives；Slate 中性色；Teal 品牌色；`0.5rem` / 8px 圆角 |
| Component library | Base UI；仅使用 shadcn 官方 registry 生成的封装 |
| Icon library | Lucide React；线宽统一 2px，图标不承担唯一语义 |
| Font | `Inter, ui-sans-serif, system-ui, sans-serif`；中文回退系统无衬线字体 |
| Theme | 仅浅色；Phase 1 不实现暗色切换 |
| Visual tone | 克制、可信、偏专业健康产品；不使用医疗十字、诊断式文案或夸张渐变 |

设计系统初始化属于实现任务，不属于本规格写作任务。初始化参数必须匹配上表；若 shadcn CLI 生成值不同，以本规格为准进行 token 覆盖。不得为了一个认证页面引入第二套组件库。

---

## Spacing Scale

Declared values（仅使用 4 的倍数）：

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | 图标与文字、字段错误与输入框之间的微间距 |
| sm | 8px | 同组标签、辅助文字、紧凑按钮内容间距 |
| md | 16px | 表单字段、移动端页面边距、卡片内部基础间距 |
| lg | 24px | 卡片 padding、表单区块和会话条目间距 |
| xl | 32px | 页面主要区块、认证标题与表单间距 |
| 2xl | 48px | 桌面页首和内容区的主要分隔 |
| 3xl | 64px | 大屏页面顶部留白；认证页不强制撑出滚动 |

Exceptions：所有可点击控件最小高度和最小触控面积为 44px；这是无障碍命中区例外，不是新的布局间距 token。输入框与主按钮高度 44px，图标按钮视觉可为 20px，但命中区必须为 44×44px。

---

## Typography

全站只能使用 `400` 和 `600` 两个字重，不引入 `500`、`700`。

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Label / helper | 14px | 400 或 600 | 1.4 |
| Body | 16px | 400 | 1.5 |
| Heading | 20px | 600 | 1.3 |
| Display | 28px | 600 | 1.2 |

- 输入、按钮和正文使用 16px，避免移动浏览器聚焦输入框时自动缩放。
- 14px 只用于字段标签、辅助信息、时间、角色和状态；错误文案不得小于 14px。
- 28px 只用于落地页和认证页主标题；`/app` 页面标题使用 20px。
- 会话设备名、邮箱和错误内容允许换行，不以省略号隐藏关键身份信息。

---

## Color

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | Slate 50 `#F8FAFC` | 页面背景、认证启动页、空状态背景 |
| Secondary (30%) | White `#FFFFFF` | 表单卡片、应用顶栏、会话卡片；边框使用 Slate 200 `#E2E8F0` |
| Accent (10%) | Teal 600 `#0D9488` | 主 CTA、当前导航、输入焦点环、选中状态、当前会话标记 |
| Accent hover | Teal 700 `#0F766E` | 主 CTA hover/pressed；不得降低文字对比度 |
| Accent subtle | Teal 50 `#F0FDFA` | 成功提示与角色/当前会话浅色底；文字使用 Teal 800 `#115E59` |
| Primary text | Slate 900 `#0F172A` | 标题、输入值、主要正文 |
| Secondary text | Slate 600 `#475569` | 辅助说明、时间、非关键元数据 |
| Destructive | Red 600 `#DC2626` | 撤销会话、破坏性确认和错误图标；仅限破坏/错误语义 |
| Warning | Amber 700 `#B45309` | 会话即将过期或安全提醒；不用作普通装饰 |

Accent reserved for：`登录并继续`/`发送验证码`/`验证并激活账号` 等每屏唯一主 CTA、表单焦点环、当前导航、当前会话标签、成功状态。普通正文链接默认使用 Slate 700 加下划线，hover 才使用 Teal 700，避免页面到处发绿。

任何状态不能只靠颜色表达：成功、错误、当前会话、验证码过期和重发冷却必须同时有文字；正文与背景达到 WCAG AA，焦点指示与相邻颜色至少 3:1。

---

## Layout Contract

### Public and auth shell

- `/`、登录、注册、验证码、密码重置、隐私与条款页面使用移动端优先布局，`min-height: 100dvh`，水平 page padding 16px；`md` 以上为 24px。
- 落地页的视觉焦点固定为产品价值标题与“创建账号”主 CTA；“登录并继续”和能力说明保持次级层级。认证页的视觉焦点固定为页面标题与主表单 CTA；品牌说明、辅助链接和装饰不能与这些锚点争夺层级。
- 表单容器宽度 `min(100%, 420px)`，居中；手机端不制造无意义的悬浮大阴影，桌面端使用 1px Slate 200 边框和低强度阴影。
- 品牌行位于卡片上方或卡片顶部：名称固定为“饮食健康 Agent”，不得承诺“精准诊断”“医学级”等能力。
- 卡片 padding：手机 24px，`md` 以上 32px。标题、说明、表单、次要链接按 24/32/24px 分组。
- `/` 首屏只介绍产品价值和登录要求，不伪造尚未交付的图片分析结果；主 CTA 为“创建账号”，次 CTA 为“登录并继续”。已登录时主 CTA 替换为“进入应用”。

### Authenticated shell

- `/app` 使用最小应用外壳：顶部栏 + `main`；内容最大宽度 960px，移动端 padding 16px，桌面 24px。
- `/app` 的视觉焦点固定为账号摘要与“登录会话”列表标题；退出按钮和角色标签保持次级层级。
- 顶部栏包含产品名、当前用户邮箱、角色标签和“退出登录”。移动端允许邮箱换行，退出按钮保持 44px 命中区。
- Phase 1 不实现侧边栏、数据图表、Agent 输入框、游客分析或后台导航。为未来功能画假入口会制造错误承诺，禁止。
- 会话列表桌面端按“设备/状态—最近活动—到期时间—操作”对齐；小于 640px 时堆叠成卡片，操作按钮独占底部一行。

### Responsive floor

- 必须在 320px 宽度下无水平滚动，在 200% 浏览器缩放下仍可完成注册、登录、撤销会话和退出。
- 内容顺序在移动端和桌面端保持一致，不依赖 CSS 视觉重排改变键盘阅读顺序。

---

## Route and Page Contract

| Route | Access | Required content | Required states |
|-------|--------|------------------|-----------------|
| `/` | Public | 产品定位、核心能力说明、登录要求、隐私/条款入口、“创建账号”与“登录” | anonymous、authenticated |
| `/login` | Public-only | 邮箱、密码、“登录并继续” CTA、“忘记密码？”、注册链接 | idle、client-invalid、submitting、server-error、rate-limited |
| `/register` | Public-only | 邮箱、密码、确认密码、“发送验证码”、登录链接、密码规则 | idle、client-invalid、submitting、server-error、navigating-to-verify |
| `/register/verify` | Public-only pending flow | 掩码邮箱、单个 6 位验证码输入、“验证并激活账号”、重发倒计时、返回修改邮箱 | idle、submitting、invalid-code、expired、attempts-exhausted、resending、new-code-sent、network-error、retrying |
| `/forgot-password` | Public-only | 邮箱、“发送重置验证码”、返回登录 | idle、client-invalid、submitting、uniform-success、server-error |
| `/reset-password` | Public-only pending flow | 掩码邮箱、6 位验证码、新密码、确认密码、“重置密码”、重发倒计时 | idle、client-invalid、submitting、invalid-code、expired、attempts-exhausted、resending、network-error、retrying、success |
| `/privacy` | Public | 隐私说明正文、“返回首页” | loading-static、ready |
| `/terms` | Public | 使用条款正文、“返回首页” | loading-static、ready |
| `/app` | Authenticated | 邮箱、`user/admin` 角色、会话列表、退出 | bootstrapping、loading sessions、empty-other-sessions、error、revoking |
| unknown | Any | 简洁 404 与返回入口 | authenticated 返回 `/app`；unauthenticated 返回 `/login` |

- 已登录用户访问登录、注册、验证码或密码重置流程时 replace 到 `/app`，不得闪现表单；`/`、`/privacy`、`/terms` 始终可访问。
- `/app` 以及后续标记为 `requiresAuth` 的 H5 路由全部禁止游客访问。未登录深链统一跳转 `/login?returnTo=<encoded-relative-path>`，Phase 1 不提供游客分析。
- `returnTo` 只能是 React Router 已注册且标记 `requiresAuth` 的同源相对路径，必须以单个 `/` 开头，并拒绝 `//`、协议、host、认证页和未知路径；校验失败回退 `/app`。登录成功后使用 `replace` 返回该路径。
- `/register` 提交成功后始终进入 `/register/verify`，不得根据响应文案确认邮箱是否已注册。原始邮箱不得放入 URL；验证页只使用服务端 pending-registration 上下文返回的掩码邮箱。
- 直接访问缺少有效 pending 上下文的 `/register/verify` 或 `/reset-password` 时显示“验证信息已失效，请重新开始。”，主 CTA 分别为“返回注册”或“重新申请重置”。
- 用户 H5 不注册 `/admin` 路由、不显示后台入口、不调用 admin probe。后端 admin probe、RBAC 和管理员 CLI 仍由 Phase 1 后端计划验证；独立 `admin-frontend/` 属于 Phase 6。

---

## Component Inventory

| Component / boundary | Responsibility | Must not own |
|----------------------|----------------|--------------|
| `AuthProvider` | 内存 access token、当前用户、启动 refresh、登录/退出命令、single-flight refresh | 不写 localStorage/sessionStorage/IndexedDB；不管理邮箱验证码生命周期 |
| `AuthBootstrap` | 启动时阻止登录页闪烁，渲染全页可访问 loading | 不显示业务页面骨架，不无限重试 |
| `PublicOnlyRoute` | 已认证用户离开认证流程页面 | 不阻止 `/`、隐私或条款页面 |
| `ProtectedRoute` | 等待 bootstrap；未认证时带安全 `returnTo` 跳登录 | 不接受任意 URL，不允许游客绕过 |
| `LoginForm` | React Hook Form + Zod、字段状态、表单错误与提交 | 不直接操作 token 或 Cookie |
| `RegisterForm` | 邮箱、密码、确认密码、客户端一致性检查，成功后进入验证页 | 不向 API 发送确认密码或 role，不确认账号是否存在 |
| `EmailCodeForm` | 单个 6 位验证码输入、后端错误码映射、10 分钟过期语义、5 次失败终止 | 不在前端自行决定剩余尝试次数，不把验证码持久化 |
| `ResendCodeControl` | 展示 60 秒冷却、重发、新码替换旧码的状态与 live announcement | 不用前端倒计时绕过后端冷却，不显示 Mailpit 操作 |
| `ForgotPasswordForm` | 发送统一响应的重置验证码请求 | 不确认邮箱是否存在 |
| `ResetPasswordForm` | 验证码、新密码与确认密码；成功返回登录 | 不发送确认密码，不复用已成功验证码 |
| `SessionList` | TanStack Query 读取会话、展示当前与其他会话 | 不展示 token、IP 全值或未经批准的指纹信息 |
| `SessionRow` | 安全元数据、当前标签、撤销动作 | 不允许撤销别人的 session id |
| `RevokeSessionDialog` | 明确目标、二次确认、提交中禁止重复操作 | 不乐观移除；服务端成功后才更新列表 |
| `ApiErrorAlert` | 稳定错误码、可操作文案、可选 request id | 不原样渲染后端 exception/detail/HTML |

shadcn 官方组件清单：`Button`、`Input`、`Label`、`Card`、`Alert`、`AlertDialog`、`Badge`、`Separator`、`Skeleton`。Toast 只用于非阻塞成功反馈；表单错误必须留在表单内，不能只发 Toast。

---

## Authentication State Contract

全局认证状态使用明确的判别联合类型，不使用散落的 `isLoading`/`user?` 布尔组合：

```text
bootstrapping
  ├─ refresh success → authenticated(user, accessToken)
  └─ no/invalid cookie → unauthenticated(reason?)

authenticated
  ├─ access 401 → refreshing（共享一个 in-flight Promise，仅重试原请求一次）
  ├─ refresh success → authenticated + retry once
  ├─ refresh failure → unauthenticated(session_expired)
  └─ logout success/failure-with-local-clear → unauthenticated(signed_out)
```

- `bootstrapping` 渲染全页状态“正在确认登录状态…”，同时提供 `role="status"`；不得先显示登录页再跳转。
- refresh 只允许 single-flight。多个并发 401 共用一个刷新请求，原请求最多重放一次，禁止刷新风暴和无限循环。
- access token 只存在 JS 运行内存；refresh token 只能由浏览器通过 HttpOnly Cookie 管理。UI、日志、URL、错误监控和 DOM 都不能出现 token。
- logout 请求无论服务端是否可达，都清空内存 access token；若服务端失败，显示“本机已退出，但服务器会话撤销未确认，请重新登录后检查会话。”，不得伪称远端会话已撤销。
- 认证切换后清理用户级 TanStack Query cache，防止同一浏览器切换账号时看到前一用户数据。

---

## Form and Validation Contract

- 每个字段有永久可见的 `<Label>`；placeholder 不能代替 label。
- 邮箱输入：`type="email"`、`inputMode="email"`、`autoComplete="email"`，显示原始输入，提交前由后端执行最终规范化。
- 登录密码：`type="password"`、`autoComplete="current-password"`。
- 注册密码：`autoComplete="new-password"`；确认密码仅在前端比较，不发送后端。
- Phase 1 统一客户端长度契约为 12–128 个 Unicode 字符；前后端必须共享相同边界测试。不得静默截断、trim 或修改密码。
- 验证码使用一个有可见标签“邮箱验证码”的输入框：`inputMode="numeric"`、`autoComplete="one-time-code"`、`maxLength=6`，可访问名称精确为“6 位邮箱验证码”。只接受 6 个 ASCII 数字；允许一次粘贴完整 6 位值，不拆成六个难以读屏的输入框。
- `/register/verify` 与 `/reset-password` 只显示服务端 pending context 返回的掩码邮箱，例如 `m***@example.com`；不得从 URL 或本地持久化恢复原始邮箱。
- 验证码有效期由后端时间决定，页面文案固定为“验证码 10 分钟内有效。”；前端倒计时只改善体验，不能覆盖后端 expired/attempts-exhausted 结果。
- 重发按钮在 60 秒冷却时禁用，可见文本与可访问名称统一为“{seconds} 秒后可重新发送”；冷却结束后统一为“重新发送验证码”。
- Enter 提交当前表单；提交中禁用所有字段和主 CTA，按钮保留原动作文字并增加 spinner，避免布局跳动和重复请求。
- 首次提交失败后，焦点移动到第一个无效字段；字段错误通过 `aria-describedby` 绑定，表单级错误使用 `role="alert"`。
- 验证页路由进入后先聚焦 `<h1>`；验证码校验失败时聚焦验证码输入并全选；重发成功后清空旧码、聚焦验证码输入，并通过 `aria-live="polite"` 宣告“新验证码已发送，之前的验证码已失效。”
- 客户端校验只用于即时反馈。服务端响应始终权威，前端不能因为 Zod 通过就假定注册、登录或权限成功。

---

## Server Response and Error Mapping

前端只根据稳定的 `error.code` 映射，不解析 `message` 子串。后端 envelope 为 `{ error: { code, message, request_id } }`；未知 code 进入安全兜底。

| HTTP / code | Surface | User copy / behavior |
|-------------|---------|----------------------|
| `422 VALIDATION_ERROR` | 对应字段；无法定位则表单顶部 | 显示后端提供的安全字段消息；聚焦首个错误字段 |
| `401 INVALID_CREDENTIALS` | 登录表单顶部 | “邮箱或密码不正确，请重新输入。” 不区分邮箱是否存在 |
| `202 CODE_DISPATCH_ACCEPTED` | 注册/忘记密码/重发 | 邮箱存在、不存在或已注册场景使用相同状态与 envelope；统一进入下一步并显示“如果该操作可以继续，验证码将发送到你填写的邮箱。” |
| `400 INVALID_VERIFICATION_CODE` | 验证码输入 | “验证码不正确，请重新输入。” 聚焦并全选验证码；不显示服务端未提供的剩余次数 |
| `410 VERIFICATION_CODE_EXPIRED` | 验证页表单顶部 | “验证码已过期，请重新发送。” 禁用提交，恢复动作“重新发送验证码” |
| `429 VERIFICATION_ATTEMPTS_EXCEEDED` | 验证页表单顶部 | “验证码已失效，请重新发送后再试。” 清空验证码并禁用提交 |
| `429 RESEND_COOLDOWN` | 重发控件 | 使用后端安全 `retry_after` 重置“{seconds} 秒后可重新发送”，不发送第二个请求 |
| `409 VERIFICATION_CONTEXT_INVALID` | 验证/重置页 | “验证信息已失效，请重新开始。” 注册流 CTA“返回注册”；重置流 CTA“重新申请重置” |
| `401 SESSION_EXPIRED` | 全局 | 清理内存状态，跳转登录并显示“登录状态已过期，请重新登录。” |
| `404 SESSION_NOT_FOUND` | 会话撤销对话框 | 关闭对话框、刷新列表，提示“该会话已不存在或已被撤销。” |
| `409 SESSION_ALREADY_REVOKED` | 会话列表 | 刷新列表，使用中性反馈，不当作致命错误 |
| `429 RATE_LIMITED` | 当前表单 | “尝试次数过多，请稍后再试。” 若响应给出安全重试时间则显示倒计时 |
| network failure | 当前区域 | “暂时无法连接服务，请检查网络后重试。” 保留非敏感输入；密码是否保留由浏览器表单状态决定，不写存储 |
| `5xx` / unknown code | 当前区域 | “服务暂时不可用，请稍后重试。” 可折叠显示“问题编号：{request_id}” |

错误恢复必须靠明确按钮（“重新尝试”“返回应用”），不能只显示红色句子。任何后端堆栈、SQL、Cookie、token、内部 exception 或原始 HTML 都不得呈现。

---

## Session Management Contract

- `/app` 首屏先显示当前账号摘要，再显示“登录会话”。会话条目字段仅包括：安全设备标签、当前会话标记、最近活动相对时间、到期日期和撤销动作；字段缺失显示“未知设备”，不得伪造精确信息。
- 当前会话置顶并标记“当前设备”；其操作为“退出当前设备”，复用 logout，不显示“撤销”造成语义混乱。
- 其他会话操作文案为“撤销会话”，点击后打开 AlertDialog：标题“撤销这个登录会话？”，正文“该设备将需要重新登录。此操作不会删除账号或饮食数据。”，次按钮“保留这个会话”，破坏性按钮“撤销这个会话”。
- 撤销为悲观更新：按钮进入“正在撤销…”，成功后刷新 query 并把焦点移到列表标题或下一条会话；失败时保留条目和对话框错误。
- 除当前会话外为空时显示标题“暂无其他登录会话”，正文“只有当前设备保持登录。新的设备登录后会显示在这里。” 不显示插画占位。
- 会话加载失败不应登出用户；在列表区域显示“无法加载登录会话”与“重新尝试”。

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Product name | 饮食健康 Agent |
| Landing heading | 拍下或描述一餐，获得可追问的饮食分析 |
| Landing body | 登录后使用餐食分析、记录和规划功能。结果仅作普通饮食参考。 |
| Landing primary / secondary CTA | 创建账号 / 登录；已登录主 CTA 为“进入应用” |
| Login heading | 欢迎回来 |
| Login body | 登录后继续管理你的饮食与登录会话。 |
| Login primary CTA | 登录并继续 |
| Register heading | 创建账号 |
| Register body | 使用邮箱创建你的饮食健康档案。 |
| Register primary CTA | 发送验证码 |
| Register verify heading | 验证邮箱 |
| Register verify body | 输入发送到 {masked_email} 的 6 位验证码。验证码 10 分钟内有效。 |
| Register verify primary / secondary CTA | 验证并激活账号 / 返回修改邮箱 |
| Verification success | 邮箱验证成功，请登录。 |
| Resend enabled / disabled | 重新发送验证码 / {seconds} 秒后可重新发送 |
| New-code notice | 新验证码已发送，之前的验证码已失效。 |
| Invalid / expired code | 验证码不正确，请重新输入。 / 验证码已过期，请重新发送。 |
| Attempts exhausted | 验证码已失效，请重新发送后再试。 |
| Verification retry | 暂时无法验证，请检查网络后重试。 / 重新尝试验证 |
| Forgot-password heading / CTA | 忘记密码 / 发送重置验证码 |
| Login recovery link | 忘记密码？ |
| Reset-password heading / CTA | 重置密码 / 重置密码 |
| Auth secondary links | 返回登录 / 返回注册 / 重新申请重置 |
| Legal links / page return | 查看隐私说明 / 查看使用条款 / 返回首页 |
| Reset success | 密码已重置，请使用新密码登录。 |
| Privacy / terms heading | 隐私说明 / 使用条款 |
| Auth bootstrap | 正在确认登录状态… |
| App heading | 账号与会话 |
| Session empty heading | 暂无其他登录会话 |
| Session empty body | 只有当前设备保持登录。新的设备登录后会显示在这里。 |
| Session load error | 无法加载登录会话。请检查网络后重新尝试。 |
| Logout action | 退出登录 |
| Generic error | 服务暂时不可用，请稍后重试。 |
| Destructive confirmation | 撤销会话：“该设备将需要重新登录。此操作不会删除账号或饮食数据。”；次按钮“保留这个会话”，破坏性按钮“撤销这个会话” |

文案规则：按钮使用“动词 + 对象”；不使用“提交”“确定”“出错了”这类无对象或无行动路径文案；不声称前端“保护了账号”，只描述服务端已验证的状态。

---

## Interaction and Accessibility Contract

- 键盘 Tab 顺序严格跟随视觉顺序；所有操作可用键盘完成。AlertDialog 打开后锁定焦点，Escape 关闭，关闭后焦点返回触发按钮。
- 全局 focus ring：2px Teal 600，offset 2px；不得用 `outline: none` 移除可见焦点。
- 页面 route change 后把焦点移到 `<h1>`（`tabIndex=-1`）；表单失败优先移到首个错误字段。
- 状态消息：加载使用 `role="status"`/`aria-live="polite"`，阻断错误使用 `role="alert"`。短暂 Toast 不作为唯一反馈。
- spinner、锁、盾牌等装饰图标 `aria-hidden="true"`；纯图标按钮必须有可见 tooltip 和 `aria-label`，但本阶段优先使用文字按钮。
- 动效只用于 150–200ms 的颜色、opacity 和轻微位移；遵守 `prefers-reduced-motion`，不得使用循环装饰动画。认证 bootstrap spinner 除外，但必须有文字状态。
- 密码显示切换若实现，按钮文案必须在“显示密码”/“隐藏密码”间更新，并保持字段焦点；不默认显示密码。
- 浏览器自动填充样式必须保持文字、边框和错误状态可读，不用 CSS 禁止密码管理器或粘贴。

---

## Loading, Empty, Error and Success States

| Surface | Loading | Empty | Error | Success |
|---------|---------|-------|-------|---------|
| Auth bootstrap | 居中 spinner + “正在确认登录状态…” | 不适用 | 一次 refresh 失败后进入未登录，不无限重试 | 无闪烁进入目标页 |
| Login | CTA 内 spinner，字段禁用 | 不适用 | 表单内 `ApiErrorAlert`，保留邮箱 | replace 到已校验 `returnTo` 或 `/app` |
| Register | “发送验证码”保留文字并增加 spinner，字段禁用 | 不适用 | 统一错误，不确认邮箱存在性 | replace 到 `/register/verify` |
| Register verify | “验证并激活账号”或“重新发送验证码”保留文字并增加 spinner | 无 pending context 时要求重新开始 | invalid、expired、attempts-exhausted、network-error 均有明确恢复动作 | 激活成功后进入登录并显示“邮箱验证成功，请登录。” |
| Forgot/reset password | CTA 内 spinner，字段禁用 | 无 pending context 时要求重新申请 | 统一发送响应；验证码错误/过期/超限按 error code 映射 | replace 到 `/login` 并显示“密码已重置，请使用新密码登录。” |
| `/app` identity | 2 行 Skeleton，不显示假邮箱 | 不适用 | 认证失败进入登录；网络失败可重试 | 展示服务端 `/me` 返回的邮箱/角色 |
| Session list | 3 个等高 Skeleton 行 | “暂无其他登录会话” | 区域内重试，不登出 | 撤销后刷新并播报结果 |

Skeleton 必须匹配最终布局尺寸，避免布局位移；未知数据不得用假数据占位。

---

## Security and Privacy UI Boundaries

- 前端不保存、不打印、不展示 access token 或 refresh token；Cookie 也不得尝试从 JS 读取。
- 登录、注册和会话请求启用 `credentials: include` 仅针对受控 API origin；不得使用 wildcard origin。
- 用户 H5 不注册 `/admin`、不显示后台入口、不调用 admin probe；后台权限验证属于后端和 Phase 6 独立 `admin-frontend/`。
- 注册表单没有 role 字段，网络 payload 也不能包含 role；任何客户端篡改必须由后端拒绝。
- 验证码、pending registration/reset 上下文和完整邮箱不得写入 localStorage、sessionStorage、IndexedDB 或 URL；验证码输入在成功、重发或离开流程时清空。
- Mailpit 只用于本地开发者查看捕获邮件；生产 UI 不出现“打开 Mailpit”“查看测试邮箱”或任何依赖开发工具的用户动作。
- `returnTo` 只允许同源、已注册、受保护的相对路由；任何绝对 URL、协议相对 URL、未知路由和认证流程路由都回退 `/app`。
- 不显示完整 IP、精确地理位置、浏览器指纹或内部 session/token id。撤销请求使用服务端提供的不可猜测 session id，但不把它作为主要可见文案。
- 认证错误不区分“邮箱不存在”和“密码错误”；注册、忘记密码和重发响应不确认邮箱或账号是否存在。
- 所有成功/安全状态用“已由服务器验证”措辞，前端不得宣称自身构成安全边界。

---

## Testable UI Acceptance Contract

### Component and integration tests

- 落地页、隐私与条款无需认证；`/app` 和所有 `requiresAuth` 深链必须进入登录。恶意 `returnTo`（外域、`//`、未知路由、认证页）必须回退 `/app`，合法受保护路径登录后原样返回。
- 登录/注册每个字段的 label、autocomplete、客户端错误、服务端错误映射和首次错误聚焦均有 Testing Library 测试；精确断言 CTA“登录并继续”和“发送验证码”，确认密码与 role 均不进入请求 payload。
- `/register/verify` 和 `/reset-password` 精确测试 6 位 ASCII 数字约束、`one-time-code`、掩码邮箱、10 分钟过期 error code、最多 5 次失败 error code、60 秒重发冷却和新码使旧码失效的 UI 状态。
- 重发控件逐秒断言可访问名称“{seconds} 秒后可重新发送”，归零后为“重新发送验证码”；重发成功清空旧码、聚焦验证码输入，并播报“新验证码已发送，之前的验证码已失效。”
- 注册、忘记密码和重发在“邮箱存在/不存在”MSW 场景中必须显示相同发送响应；生产组件树与可访问名称中不得出现 Mailpit。
- auth bootstrap 不闪现公开页面；同时到达的多个 401 只产生一次 refresh，原请求最多重试一次。
- 测试 spy 断言 token 未写入 localStorage、sessionStorage、IndexedDB 或 URL。
- 路由表和渲染测试断言用户 H5 不存在 `/admin` 页面或后台导航；Phase 1 前端不调用 admin probe。
- 会话撤销必须经过 AlertDialog；测试按可访问名称精确断言“保留这个会话”关闭且不调用 API，“撤销这个会话”才提交撤销；失败不移除条目，成功后列表刷新且 live region 播报。
- 切换用户后旧用户的 TanStack Query cache 不可见。

### Playwright smoke flow

1. 320px 视口从 `/` 进入注册，提交邮箱/密码/确认密码，验证 payload 没有确认密码与 role，并进入 `/register/verify`。
2. 输入错误码、模拟过期与第 5 次失败；重发后旧码失败，新 6 位码成功激活，返回登录。
3. 未登录直达 `/app?tab=sessions`，跳到带编码 `returnTo` 的登录页；登录后安全返回同一路径。外域 `returnTo` 必须回退 `/app`。
4. 到 `/app` 查看 `/users/me` 账号摘要与当前会话，创建第二会话后撤销它，确认对应设备后续请求失效。
5. 走完忘记/重置密码的统一响应、验证码和重发流程；页面不出现 Mailpit 用户动作。
6. 退出当前设备，返回登录页；浏览器后退不能重新显示受保护数据。仅用键盘重复验证码和撤销对话框流程，并在 200% 缩放下检查无水平滚动。

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | Button, Input, Label, Card, Alert, AlertDialog, Badge, Separator, Skeleton | official registry only — no third-party source to vet — 2026-08-27 |
| Third-party | none | not applicable — 2026-08-27 |

Phase 1 禁止第三方 shadcn registry 和整页 auth block。若实现时新增第三方 block，必须先执行 `shadcn view`、审查网络访问、环境变量读取、动态执行和外部 import，再更新本规格；未经审查不得合入。

---

## Source Decisions

| Source | Decisions applied |
|--------|-------------------|
| `01-CONTEXT.md` | D-31..D-35：独立邮箱验证、摘要/过期/尝试/重发规则、Mailpit 仅本地工具、公开/受保护路由边界、独立后台延后 Phase 6；并继承移动优先/浅色/Slate+Teal/8px |
| `01-RESEARCH.md` | AuthProvider、内存 token、bootstrap refresh、single-flight 401、稳定错误 envelope、会话管理与安全边界 |
| `REQUIREMENTS.md` / `ROADMAP.md` | AUTH-01..06、ARC-01/07/08、公开页面、验证激活、后端 admin probe 与独立后台阶段边界 |
| Existing UI | 0 项：仓库当前无 `frontend/`、`components.json`、Tailwind 配置或可继承组件 |
| Defaulted by UI researcher | Typography、精确色值、响应式尺寸、文案、焦点和空/错/载入状态 |

---

## Checker Sign-Off

- [x] Dimension 1 Copywriting: PASS
- [x] Dimension 2 Visuals: PASS
- [x] Dimension 3 Color: PASS
- [x] Dimension 4 Typography: PASS
- [x] Dimension 5 Spacing: PASS
- [x] Dimension 6 Registry Safety: PASS

**Approval:** verified by `gsd-ui-checker` on 2026-08-27; non-blocking CTA and landing-focus recommendations incorporated
