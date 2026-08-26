# 技术栈研究

**产品：** 移动端优先的中式外卖热量识别网站  
**研究日期：** 2026-08-26  
**总体置信度：** 高（Web/部署/SDK）；中（模型选择与图片分辨率，必须用项目评测集验证）

## 结论先行

首版应做成一个 **Next.js 16 单体应用**：React 页面、一个 Node.js Route Handler、受控菜品目录和纯函数热量计算放在同一仓库。不要拆独立前端、FastAPI、数据库和任务队列。一次请求的正确链路是：浏览器压缩 → 服务端再次验证/规范化 → OpenAI Responses API 返回严格结构 → 映射到本地菜品 ID → 本地确定性计算热量与区间 → 浏览器即时编辑重算。

模型候选基线用 `gpt-5.6-terra`，不是因为官方证明它最懂中餐，而是它是当前官方定义的“质量/成本平衡”档，并同时支持图片输入和 Structured Outputs。是否能达到 Top-1 85%、Top-3 95%、P90 10 秒，只能由项目自己的中式外卖评测集决定。该结论置信度为 **中**；任何不经过评测就把模型名写死为“最佳”的结论都是假的。

100 道只读菜品不值得上数据库。用经过来源审查、版本化的 JSON/CSV 目录，构建时用 Zod 校验；运行时只按 `dish_id` 查表。USDA FoodData Central 只补基础食材，不应被当成中式成菜数据库。中国食物成分数据的商业授权在本次官方检索中未得到可直接复用的公开许可证明，上线前必须完成授权核查。

## 推荐栈

### 核心技术

| 技术 | 固定版本/配置 | 用途 | 推荐理由与置信度 |
|---|---:|---|---|
| Node.js | `24.19.x LTS` | 本地、CI、Vercel Functions 运行时 | Node 24 是当前 LTS；OpenAI Node SDK 官方也把 24 列为推荐工具链。不要用已 EOL 的 Node 20。**高** |
| Next.js App Router | `16.3.3` | 页面、Route Handler、静态菜品目录、BFF | 一套代码覆盖移动 Web 与服务端 API；16.3.3 是研究日 npm `latest`，要求 Node `>=20.9`。单体比双服务更利于 10 秒延迟目标。**高** |
| React / React DOM | `19.2.8` | 上传、结果编辑、即时重算 UI | React 官方当前稳定大版本为 19.2；与 Next 16 兼容。状态只用 `useReducer`/局部状态，不加 Redux/Zustand。**高** |
| TypeScript | `6.0.2`，严格模式 | 全栈类型和菜品 schema | **故意不装 npm `latest` 7.0.2**。TS 7 已稳定，但 Next 16.3 仍通过实验开关接入，且 7.0 不再提供旧 JS Compiler API，已有 Next 集成缺陷。MVP 先固定 6.0.2；等 Next 的 TS 7 支持转为稳定后再升。**高** |
| Tailwind CSS | `4.3.1` | 移动端样式 | Next 默认路径、产物小、触控断点表达直接。只建立少量设计 token，不引入大型组件库。**高** |
| OpenAI Node SDK | `7.1.x` | 调用 Responses API | 官方 TypeScript SDK；Node 24 在其支持矩阵内。服务端调用，API Key 绝不下发浏览器。**高** |
| OpenAI Responses API | `POST /v1/responses` | 图片输入、严格 JSON 输出 | 官方接口支持 text/image 输入与 JSON 输出；用 `text.format.type=json_schema`，不要用旧 `json_object` 模式。设置 `store:false`。**高** |
| 多模态模型 | 默认候选 `gpt-5.6-terra`；评测 `sol/terra/luna` | 多菜识别、候选名、估重 | Terra 官方定位为质量/成本平衡，并支持图片输入和 Structured Outputs。`reasoning.effort: none` 作为低延迟基线，同时评测 `low`。最终选择由真实集的准确率、估重、P90 和单次成本共同决定。**中** |
| Zod | `4.4.3` | API 输入、模型输出、菜品目录三处校验 | 一份 schema 同时约束 JSON Schema、运行时解析和 TypeScript 类型；模型结构正确不等于业务值合法，返回后仍需再次校验。**高** |

### 图片上传与压缩

| 技术 | 版本/配置 | 用途 | 具体用法 |
|---|---:|---|---|
| 原生 `<input type=file>` | `accept="image/jpeg,image/png,image/webp"`、`capture="environment"` | 拍照/相册 | 不做原生 App，不要引入相机 SDK。允许文件选择兜底；不能只信 `accept` 和 MIME。 |
| `browser-image-compression` | `2.0.2`（固定） | 上传前压缩 | Web Worker 模式；长边从 **1600 px** 起测，目标 JPEG/WebP 约 1–2 MB，去除 EXIF。该库成熟但更新不活跃，必须做 iOS Safari 回归；若兼容问题出现，再替换为自维护 Canvas/ImageBitmap 工具。 |
| `file-type` | `22.0.1` | 服务端魔数识别 | 只放行 JPEG/PNG/WebP。它只是“最佳努力”提示，不能代替解码校验。 |
| `sharp` | `0.35.3` | 服务端解码、自动旋转、二次缩放与重编码 | Node runtime 中限制原始字节、像素数和通道；`rotate()` 处理方向，最长边限制在实验确定值，去元数据后统一输出 JPEG/WebP。Sharp 0.35.3 也是 Next 16.3.3 的可选依赖版本。 |

上传接口采用 `multipart/form-data` 的 Route Handler，服务端顺序必须是：先检查 `Content-Length` 和读取上限 → 魔数 → Sharp 解码与像素上限 → 规范化 → 调模型。Vercel Function 请求/响应 payload 上限是 **4.5 MB**，所以压缩后请求目标必须明显低于该值（建议不超过 3 MB）；超过就前端提示重拍/重选，不要先存 Blob 再绕限制。

1600 px 只是起始配置，不是结论。上线前用同一评测集对 1280/1600/2048 长边与 `detail: high/auto` 做准确率、P90、token 成本对比。GPT-5.6 的 `auto/original` 会保留更高原始细节，也会增加 token 和延迟，因此生产不要无脑传手机原图。

### 结构化识别与确定性计算

模型只允许输出视觉判断，不允许输出最终营养值。建议响应 schema：

```typescript
type VisionDish = {
  region: { x: number; y: number; width: number; height: number } // 0..1
  candidates: Array<{ dishId: string; visualConfidence: number }> // 2-3 个，dishId 必须在白名单
  estimatedGrams: number
  gramsLow: number
  gramsHigh: number
  qualityFlags: Array<'occluded' | 'mixed' | 'blurred' | 'no_scale_reference'>
}

type VisionResult = {
  imageQuality: 'ok' | 'too_dark' | 'too_blurry' | 'no_food'
  dishes: VisionDish[]
}
```

提示词中直接提供约 100 个 `dish_id + 中文规范名 + 少量同义词` 白名单；模型输出 `dishId`，服务端拒绝目录外 ID。`visualConfidence` 只能作为未经校准的排序信号，不能直接展示成“85% 准确”。低置信度阈值需要在留出集上做可靠性校准。

热量计算是纯函数：

```text
kcal_center = grams × kcal_per_100g / 100
kcal_low/high = 份量区间 × 菜品单位热量区间，再按校准规则传播
```

编辑菜名、克数、删除条目后在浏览器本地立即重算；不再次调用模型。

### 营养数据

MVP 的数据层是仓库内版本化文件，而不是运行时 API：

```text
data/
  dishes.v1.json          # 100 道规范菜
  aliases.v1.json         # 别名 → dish_id
  sources.v1.json         # 来源、版本、授权、访问日期
  recipes.v1.json         # 标准配方及不确定性参数
```

每道菜至少保存：`dish_id`、规范名、别名、`kcal_per_100g_center/low/high`、标准份量分布、来源 ID、来源版本、推导方法、审核人和更新时间。应用构建时执行 schema 校验和引用完整性测试；营养目录版本写入每次识别结果日志，保证可追溯。

USDA FoodData Central 的 2026-04 下载或 API 可用于米饭、猪肉、食用油等基础食材；数据为 CC0/公共领域，官方建议注明来源。不要在用户请求链路实时查询 FDC：外部延迟没有价值，100 道菜应提前整理进本地目录。中国成菜数据应来自已获授权的《中国食物成分表》/机构数据或项目自建标准菜谱；未确认商业许可前不得把抓取数据直接塞进产品。

**数据库触发条件：** 只有出现后台多人编辑、审批流、历史版本查询或用户账户/历史记录时，才引入 PostgreSQL。首版没有这些需求。

### 测试与评测

| 工具 | 版本 | 覆盖范围 | 规则 |
|---|---:|---|---|
| Vitest | `4.1.10` | 热量纯函数、区间传播、schema、别名归一化、图片校验 | 使用稳定 4.x；不要上 5.0 RC。所有目录数据做参数化校验。 |
| React Testing Library | `16.x` | 上传、错误提示、候选切换、克数编辑、删除 | 测用户可见行为，不测内部 state。 |
| Playwright | `1.62.1` | iPhone/Android 视口、拍照上传替身、全流程、可访问性 | Next 官方推荐用于 E2E；至少覆盖 Chromium + WebKit。异步 Server Component 优先 E2E，不硬塞进单元测试。 |
| MSW | `2.x` | OpenAI/Route Handler 网络替身 | PR 测试禁止打真实模型；固定成功、拒绝、超时、schema 错误、429/5xx 样本。 |
| 自建 eval CLI（TypeScript） | 项目代码 | Top-1、Top-3、估重 MRE、区间覆盖率、P50/P90、成本 | 不引入 LangChain/LangSmith 作为评测前提。输入清单 + JSONL 输出 + 指标脚本足够。模型 live eval 在定时/手动 CI 跑，不在每个 PR 跑。 |

发布门槛直接编码为 CI 断言：Top-1 ≥85%、Top-3 ≥95%、克数中位相对误差 ≤25%、总热量区间覆盖率 ≥80%、有效请求 P90 ≤10 秒。每次模型、提示词、图片分辨率或菜品目录变更都必须重跑同一冻结测试集。

### 部署、安全与监控

| 技术 | 版本/配置 | 用途 | 为什么 |
|---|---:|---|---|
| Vercel | Next.js 原生部署，Node 24，Fluid Compute | CDN + Node Function | MVP 运维最少，I/O 等待型 AI 请求适配良好；Sharp 需要完整 Node runtime，**不要用 Edge runtime**。 |
| Function region | 首测 `hkg1`，对照 `sin1` | 降低中国用户上传与返回时延 | Vercel 默认 `iad1`，对本产品不合理。最终按真实中国网络和 OpenAI API 往返测量选择，不能只看地理距离。 |
| Vercel WAF Rate Limiting | `/api/analyze` 按 IP/JA4 固定窗口 | 防刷与模型成本保护 | 全计划可用，不必为首版再加 Redis。先 Log 观察，再限流/429。 |
| Cloudflare Turnstile | 按攻击情况启用 | 无登录场景的人机校验 | 免费且可独立使用；仅在异常流量或限流频繁时呈现。服务端 Siteverify 必须校验，客户端 token 本身不算保护。 |
| Sentry Next.js SDK | `10.x`（实施时锁定最新补丁） | 前后端错误、trace、告警 | 记录压缩、Route Handler、OpenAI、解析、计算阶段 span；关闭默认 PII，`beforeSend` 删除图片/base64/原始 prompt。 |
| Vercel Observability + Speed Insights | Speed Insights `2.x` | Function 延迟/错误、Core Web Vitals | 平台原生，首版足够；Vercel 官方支持 OpenTelemetry，也可后续导出。 |

结构化日志只记录：内部 `request_id`、OpenAI request ID、目录/提示词/模型版本、输入字节与尺寸、各阶段耗时、token usage、条目数、错误码和用户修正事件。**禁止记录图片 base64、原图 URL、完整提示词或可能含内容的模型原始响应。**

核心看板/告警：

- `/api/analyze` P50/P90/P99、超时率、429/5xx、schema 解析失败率；
- OpenAI 延迟、token/请求、估算成本/请求、模型/提示词版本；
- `no_food`/模糊/过暗占比、平均识别条目数；
- 候选切换率、克数修改率、删除率——这是在线质量信号，不是准确率真值；
- 移动端 LCP/INP/CLS 和上传失败率。

OpenAI Responses 请求设置 `store:false`，应用自身不落盘原图，内存处理后释放。注意：`store:false` 不等于供应商零留存；OpenAI 官方说明默认 abuse monitoring 日志最长可保留 30 天，只有获批的 Zero Data Retention/Modified Abuse Monitoring 才改变该层。隐私文案必须如实写，不能承诺“图片绝不留存”。

## 安装基线

```bash
# runtime
pnpm add next@16.3.3 react@19.2.8 react-dom@19.2.8 \
  openai@7.1.0 zod@4.4.3 \
  browser-image-compression@2.0.2 file-type@22.0.1 sharp@0.35.3 \
  tailwindcss@4.3.1 @sentry/nextjs@^10 @vercel/speed-insights@^2

# development and tests
pnpm add -D typescript@6.0.2 eslint eslint-config-next@16.3.3 \
  vitest@4.1.10 jsdom @testing-library/react@^16 \
  @testing-library/user-event msw@^2 @playwright/test@1.62.1
```

提交 `pnpm-lock.yaml`，CI 用 `pnpm install --frozen-lockfile`。上面的补丁版本是研究日基线；安全补丁可以升级，但模型、schema、图片库和 Next 升级后必须跑回归与 eval。

## 备选方案

| 推荐 | 备选 | 何时才切换 |
|---|---|---|
| Next.js 单体 Route Handler | FastAPI/Python 服务 | 真正引入 PyTorch/YOLO/分割、GPU 推理或 Python 数据管道时；不是为了“AI 项目看起来更专业”。 |
| 本地版本化 JSON/CSV | PostgreSQL + Drizzle | 有后台编辑、审批、用户历史或运行时频繁更新时。 |
| `gpt-5.6-terra` 候选 | `gpt-5.6-sol` | Terra 在冻结集达不到质量线，且 Sol 的增益足以抵消成本/P90；不能靠主观感觉切。 |
| `gpt-5.6-terra` 候选 | `gpt-5.6-luna` | Luna 在所有质量门槛上过线，且成本/吞吐成为主要瓶颈时。 |
| 单次多模态调用 | 检测/分割 + 分类两阶段 | 单次调用在拥挤餐盒、相邻小菜上系统性漏检，且分割实验证明能显著提升指标时。 |
| Vercel Node `hkg1/sin1` | 国内云 Node 容器 + 国内模型供应商 | 产品必须大陆境内部署、ICP/数据本地化或中国网络 SLA 成为硬要求时；需单独做合规和模型能力研究。 |
| Vercel WAF | Upstash Redis ratelimit | 需要用户级配额、跨入口共享配额或更复杂滑动窗口，且 WAF 规则不够时。 |

## 明确不要用

| 不要用 | 原因 | 用什么代替 |
|---|---|---|
| TypeScript 7 直接作为默认编译器 | Next 16.3 支持仍带实验性与集成缺口，MVP 没必要拿构建稳定性换编译速度 | TS 6.0.2；稳定支持后再迁移 |
| `chat-latest`、旧 Chat Completions + JSON mode | `chat-latest` 会滚动更新且官方建议生产用 GPT-5.6；旧 JSON mode 只保证合法 JSON，不保证 schema | Responses API + `json_schema` + 服务端 Zod |
| 让模型直接报 kcal/100g 或总热量 | 无法审计、会漂移、违反受控营养数据要求 | 模型只报 `dish_id`/克数，程序查表计算 |
| LangChain/LlamaIndex/Agent 框架 | 单模型、单调用、无工具链；增加抽象、依赖和排障面 | 官方 OpenAI SDK + 20–30 行适配层 |
| 默认上 YOLO/分割模型 | 没有标注数据和证据说明两阶段更准，只会加训练/部署/延迟 | 先做单调用基线和错误分析 |
| Prisma/PostgreSQL/向量数据库 | 100 条受控只读数据完全不需要运行时存储和语义检索 | 版本化 JSON + 精确 ID/别名映射 |
| Vercel Edge runtime | Sharp 原生依赖、完整 Node API和较长 AI 调用都更适合 Node runtime | Vercel Node.js Function |
| 原图直传或永久对象存储 | 容易撞 4.5 MB 限制、增加隐私风险和成本 | 浏览器压缩 + 内存处理 + 立即释放 |
| 自动 Sol 二次兜底 | 最差延迟和成本不可控，容易破坏 P90 10 秒 | 一次调用返回候选，让用户修正；离线决定单一生产模型 |

## 版本兼容与升级提醒

| 组合 | 结论 |
|---|---|
| Next `16.3.3` + React `19.2.8` + Node `24.x` | 官方/包元数据兼容，推荐基线。 |
| Next `16.3.3` + TypeScript `6.0.2` | 保守稳定基线。Next 最低要求 TS 5.1。 |
| Next `16.3.x` + TypeScript `7.0.2` | 可通过实验 `useTypeScriptCli` 路径接入，但现阶段不用于 MVP。 |
| Sharp `0.35.3` + Node `24.x` | Sharp 0.35 要求 Node ≥20.9；Next 16.3.3 自身将 0.35.3 列为可选依赖。 |
| `file-type@22` + Node `24.x` | v22 要求 Node ≥22 且是 ESM；Next 项目可用。 |
| Vitest `4.1.10` | 当前稳定；5.0 仍是 RC，禁止装 prerelease。 |
| Playwright `1.62.1` | 固定包和 CI 浏览器镜像同版本，避免找不到浏览器二进制。 |

## 来源

### 官方与一手来源（高置信度）

- [Next.js 安装与系统要求](https://nextjs.org/docs/app/getting-started/installation) — Node ≥20.9、TypeScript、App Router 默认配置。
- [Next.js 16 升级说明](https://nextjs.org/docs/app/guides/upgrading/version-16) — Node/TS/浏览器要求及 Turbopack 默认。
- [npm registry: Next.js 16.3.3](https://registry.npmjs.org/next/latest) — 研究日 `latest`、peer/optional dependencies。
- [React 版本页](https://react.dev/versions) 与 [npm registry: React](https://registry.npmjs.org/react/latest) — React 19.2 稳定线与 19.2.8。
- [Node.js 下载/发布状态](https://nodejs.org/en/download/current) — Node 24 LTS；Node 20 已 EOL。
- [TypeScript 7.0 官方发布](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/) — 原生端口、与 TS 6 并存方式和 API 缺口。
- [Next.js 对 TypeScript 7 的集成讨论](https://github.com/vercel/next.js/discussions/95633) — 实验 CLI 路径与兼容背景。
- [OpenAI 当前模型指南](https://developers.openai.com/api/docs/models) — GPT-5.6 Sol/Terra/Luna 定位及图片能力。
- [GPT-5.6 Terra 模型页](https://developers.openai.com/api/docs/models/gpt-5.6-terra) — 图片输入、Responses、Structured Outputs、价格与限额。
- [OpenAI Responses API](https://developers.openai.com/api/reference/cli/resources/responses/methods/create) — 图片输入、JSON 输出、`store` 等请求参数。
- [OpenAI Structured Outputs API schema](https://developers.openai.com/api/reference/cli/resources/beta/subresources/responses) — `json_schema` 优先于旧 `json_object`。
- [OpenAI 数据控制](https://platform.openai.com/docs/models/default-usage-policies-by-endpoint) — API 不默认训练、abuse logs、Responses 存储与 ZDR/MAM。
- [OpenAI Node SDK 源码与 Node 支持策略](https://github.com/openai/openai-node/blob/main/NODE_VERSION_POLICY.md) — Node 24 推荐。
- [OpenAI Node SDK package.json](https://github.com/openai/openai-node/blob/main/package.json) — SDK 7.1.x 与 Node 引擎要求。
- [Vercel Function 限制](https://vercel.com/docs/functions/limitations) — 4.5 MB payload、时长/内存。
- [Vercel Function 区域](https://vercel.com/docs/functions/configuring-functions/region) 与 [区域价格表](https://vercel.com/docs/functions/usage-and-pricing) — 默认 `iad1`、`hkg1`/`sin1` 可用。
- [Vercel WAF Rate Limiting](https://vercel.com/docs/vercel-firewall/vercel-waf/rate-limiting) — 全计划、按 IP/JA4 固定窗口。
- [Cloudflare Turnstile 服务端校验](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/) 与 [计划](https://developers.cloudflare.com/turnstile/plans/) — 免费、token 必须服务端验证。
- [Sharp 0.35.3 包元数据](https://github.com/lovell/sharp/blob/main/package.json) 与 [0.35.0 变更](https://github.com/lovell/sharp/blob/main/docs/src/content/docs/changelog/v0.35.0.md) — 当前版本和 Node 下限。
- [file-type 官方仓库](https://github.com/sindresorhus/file-type) — 魔数检测能力及“不保证文件有效”的安全边界。
- [browser-image-compression 官方仓库](https://github.com/Donaldcwl/browser-image-compression) — Web Worker、尺寸/体积压缩及 v2.0.2。
- [USDA FoodData Central API 指南](https://fdc.nal.usda.gov/api-guide/) 与 [2026-04 下载](https://fdc.nal.usda.gov/download-datasets/) — API、CC0、更新批次和数据类型。
- [Next.js 测试指南](https://nextjs.org/docs/app/guides/testing) — Vitest/Playwright 角色及 async Server Component 的 E2E 建议。
- [Vitest 发布页](https://github.com/vitest-dev/vitest/releases) — 4.1.10 稳定、5.0 RC。
- [Playwright 发布页](https://github.com/microsoft/playwright/releases) — 1.62 稳定线。
- [Sentry JavaScript SDK](https://github.com/getsentry/sentry-javascript) — 官方 Next.js SDK 与 10.x 稳定线。
- [Vercel Observability](https://vercel.com/docs/observability)、[OpenTelemetry](https://vercel.com/docs/tracing/instrumentation) 与 [Speed Insights](https://vercel.com/docs/speed-insights) — 平台监控能力。

### 仍需项目实证（中/低置信度）

- `gpt-5.6-terra` 是否优于 Sol/Luna：**中**，官方只证明能力和产品定位，没有中式外卖基准。
- 1600 px、`detail: high` 是否为最佳图片配置：**低**，必须用困难样本做分辨率消融。
- `hkg1` 是否比 `sin1` 更快：**低**，受中国网络、模型端点和用户位置影响，需真机测量。
- 中国食物成分数据的商业授权：**低/未解决**，本次未找到可直接证明可商用复用的官方许可文本；上线前走数据授权与法务核查。

---
*Stack research for: 中式外卖热量识别 MVP*  
*Researched: 2026-08-26*
