# Architecture Research

**Domain:** 移动端优先、免登录的中式外卖多菜热量估算网站
**Researched:** 2026-08-26
**Confidence:** HIGH（组件边界与安全模式）；MEDIUM（模型延迟、区间参数仍需项目评测集验证）

## Architecture Decision

首版采用**模块化单体 API + 独立推断 Worker**，共享同一套领域包和数据契约；不要一开始拆微服务。Web 请求层负责上传、状态查询和目录搜索，Worker 负责耗时且昂贵的图片推断流水线。两者用队列解耦，但菜品目录、归一化、营养计算、区间计算保持清晰的代码模块边界。

这不是“模型看图后直接报热量”的系统。正确的数据依赖只能单向流动：

```text
图片事实 → 视觉候选/估重 → 受控 dishId → 版本化营养参数 → 确定性热量与区间
```

模型不得生成最终营养值；营养计算器不得接收自由文本菜名；前端不得复制一套不同公式。

## Standard Architecture

### System Overview

```text
┌────────────────────── 移动 Web / PWA ──────────────────────┐
│ 拍照/上传  进度轮询  可编辑 MealDraft  共享计算器(即时重算) │
└───────────────┬───────────────────────────┬─────────────────┘
                │ HTTPS                     │ 搜索菜品/上报修正
┌───────────────▼──────────── Edge ─────────▼─────────────────┐
│ WAF、请求体上限、IP/匿名会话限流、Bot/成本保护、Trace ID     │
└───────────────┬─────────────────────────────────────────────┘
                │
┌───────────────▼──────────── API / BFF ──────────────────────┐
│ Upload API │ Analysis API │ Catalog API │ Feedback API       │
│       上传编排/状态机/幂等键/错误契约/匿名会话               │
└──────┬──────────────┬───────────────┬───────────────────────┘
       │              │ enqueue       │
       │       ┌──────▼────────────────▼──────┐
       │       │ Redis/Queue                  │
       │       │ 任务、幂等、短期结果、限流   │
       │       └──────────────┬───────────────┘
       │                      │
┌──────▼──────────┐   ┌───────▼──────── Inference Worker ─────┐
│ 私有临时对象存储 │   │ 质量门 → 模型适配器 → Schema Guard    │
│ sanitized/ TTL  │──▶│ → 菜名归一化 → 置信度校准             │
└─────────────────┘   │ → 营养/区间计算 → 结果快照             │
                      └──────────┬──────────────┬──────────────┘
                                 │              │
                      ┌──────────▼──────┐  ┌────▼──────────────┐
                      │ PostgreSQL       │  │ 多模态模型供应商  │
                      │ 目录/营养/版本   │  │ 仅接收净化后图片  │
                      │ 校准/元数据      │  │ 仅返回结构化识别  │
                      └─────────────────┘  └───────────────────┘

┌──────────────────── Cross-cutting ──────────────────────────┐
│ OpenTelemetry traces/metrics/logs（不记录图片、URL、base64） │
│ 离线 Eval Runner 复用同一 pipeline；评测桶与生产桶物理隔离  │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Owns | Must Not Own | Typical implementation |
|-----------|------|--------------|------------------------|
| Mobile Web | 图片选择、上传进度、轮询、可编辑 `MealDraft`、即时重算 | 模型密钥、营养真值、服务端限流 | PWA/响应式 Web；调用共享纯函数计算包 |
| Edge Gateway | WAF、请求体上限、粗粒度 IP/Bot 限流、TLS | 业务状态、最终成本配额 | CDN/WAF/边缘限流规则 |
| Upload Service | 字节流限制、签名/MIME/像素校验、解码、转码、EXIF 清理、临时对象生命周期 | 菜品识别、营养计算 | 流式读取 + 沙箱化图片解码器 + 私有对象存储 |
| Analysis Coordinator | 分析状态机、幂等、任务入队、截止时间、重试、结果查询 | 解析模型自然语言、营养公式 | API 模块 + Redis/持久队列 |
| Model Adapter | 供应商 API、提示词、结构化输出 Schema、超时、供应商错误映射 | 菜名归一化、最终热量 | `VisionProvider` 接口，每个供应商一个 adapter |
| Schema Guard | 模型响应的结构、数量、范围和枚举约束 | “猜测”缺失字段 | JSON Schema/Zod 等运行时验证；失败最多重试一次 |
| Dish Normalizer | 自由文本/候选 → 受控 `dishId`、Top-3、OOS/unknown | 千卡计算 | 别名词典 + 规则 + 目录内候选重排 |
| Confidence Calibrator | 原始模型分数 → 校准分数/阈值 | 把模型自报 confidence 当概率 | 按 pipeline 版本保存温度缩放/分桶参数 |
| Catalog Repository | 菜品、别名、版本、营养密度、配方波动、数据来源 | 运行模型 | PostgreSQL 真源，Redis/进程内只读缓存 |
| Nutrition Calculator | `dishId + grams + versions` → 单项/整餐中心与区间 | 自由文本、网络调用、未定种子随机数 | 前后端共享的纯、版本化领域函数 |
| Feedback Collector | 用户切换/改克数/删除的 before/after 事件 | 将用户修改自动当真值 | 异步低优先级写入；去标识化；独立 TTL |
| Observability | Trace、低基数指标、错误分类、成本与延迟预算 | 图片、base64、签名 URL、完整模型内容 | OpenTelemetry + 指标/日志后端 |
| Evaluation Harness | 锁定数据集、pipeline run、分片指标、发布门禁 | 只测生产 HTTP 黑盒 | 直接调用共享 pipeline，记录所有版本 |

### Storage Boundaries

| Store | Data | Retention | Rule |
|-------|------|-----------|------|
| PostgreSQL | `dish`, `dish_alias`, `nutrition_profile`, release、分析元数据、修正事件 | 目录长期；匿名元数据按隐私策略短期 | 不存图片 blob；营养/校准版本发布后不可原地修改 |
| Private object store: production | 仅净化后的临时图片；原始上传只在处理流/隔离区短暂停留 | 成功或失败后显式删除；24 小时生命周期兜底 | 禁止公开 ACL/CDN；版本控制关闭或清理历史版本 |
| Private object store: evaluation | 获得许可的评测图片、标注、manifest | 独立治理 | 与生产桶、密钥、生命周期物理隔离；生产图片不能自动流入 |
| Redis/Queue | 限流 token、并发租约、任务、幂等键、短期结果、catalog 缓存 | 秒到小时 TTL | 不能成为目录真源；任务支持至少一次投递 |

## Image Safety Pipeline

浏览器压缩只优化体验，**不是安全边界**。服务端必须对送入模型的字节重新完成全套校验。

```text
multipart byte stream
  → 总字节上限（建议初始值 10 MB）
  → 扩展名 + 声明 MIME 快速拒绝
  → magic bytes/真实格式检测
  → 解码器像素上限（建议初始值 20 MP）及内存/CPU 超时
  → 拒绝 SVG、动图、多页、损坏/嵌套文件
  → 自动旋转（读取 orientation 后丢弃元数据）
  → 重编码为单帧 JPEG/WebP，剥离 EXIF/ICC/注释
  → 尺寸/亮度/清晰度质量门
  → 随机 UUID 对象名写入私有临时存储
  → 仅 Worker 的短时凭据可读
```

支持格式只覆盖真实移动端需求：JPEG、PNG、WebP、HEIC/HEIF（前提是部署解码器已安全启用并测试）。不接收用户提供的远程图片 URL，否则引入 SSRF；不把原始文件名用于路径或日志。OWASP 建议扩展名白名单、不要信任 `Content-Type`、校验签名、随机化文件名、限制大小、站点根目录外存储，并对图片重写。

显式删除是主机制，对象生命周期是故障兜底，不能拿“配置 TTL”冒充立即删除。若模型供应商会保留图片/请求，应用侧删除不能解决第三方保留；上线前必须核实所选 endpoint 的 `store`、默认保留期和 ZDR/区域选项。

## Multi-dish Recognition Contract

模型输出是**未归一化视觉观察**：

```ts
type VisionObservationV1 = {
  schemaVersion: "vision-observation.v1";
  scene: {
    containsFood: boolean;
    quality: "ok" | "too_dark" | "blurry" | "occluded" | "not_food";
  };
  items: Array<{
    observationId: string;
    box: { x: number; y: number; width: number; height: number }; // 0..1
    visibleLabelCandidates: Array<{ label: string; rawScore?: number }>;
    estimatedGrams: number;
    gramsPlausibleRange: { low: number; high: number };
    visibility: "clear" | "partial" | "mixed";
  }>;
};
```

Schema Guard 检查最大菜品数、bbox/克数范围、有限数值、候选数、重复框、字符串长度和额外字段。Structured Outputs 能保证结构遵守 JSON Schema，但不能保证字段值正确，因此结构校验后仍需领域校验。

首版用一次供应商调用完成多菜观察，但通过 `VisionProvider` 保留替换点：

```ts
interface VisionProvider {
  observe(input: SanitizedImageRef, ctx: PipelineContext): Promise<VisionObservationV1>;
}
```

只有评测证明单调用对小菜格、遮挡、混菜失败，才在 adapter 内替换为“检测/切图 → 分区识别”。两阶段细节不能泄漏到 API 或营养模块，否则换模型会造成全链路重写。

## Dish-name Normalization

归一化是独立、可测试的受控模块：

1. Unicode/全半角/空白/常见后缀规范化，保留原始标签供诊断。
2. 先查标准名和人工维护别名（地区叫法、套餐菜单叫法）。
3. 在**当前 catalog release 的约 100 道菜内**做模糊匹配/候选重排。
4. 合并映射到同一 `dishId` 的重复候选并重新排序。
5. 低于校准阈值返回 `unknown` 或 `out_of_scope`，绝不硬映射到“最像”的菜。
6. 只把 `dishId`、展示名、校准分数交给计算器和客户端；自由文本不能进入营养查询键。

别名包含来源和生效版本。目录更新生成新 `catalogVersion`，旧结果引用旧版本，避免同一结果因目录更新而漂移。

## Nutrition and Uncertainty Calculation

### Deterministic Center Estimate

```text
itemCenterKcal = editedOrEstimatedGrams × kcalPer100g / 100
mealCenterKcal = Σ itemCenterKcal
```

`kcalPer100g` 来自受控 `nutrition_profile`，携带数据来源、配方版本和适用范围。模型返回的 kcal 字段即使存在也必须丢弃。

### Interval Model

区间至少建模：

- 份量误差：视觉估重残差，按菜品/品类、遮挡、餐盒参照分层；样本不足回退到品类/全局。
- 营养密度误差：同名菜用油、糖、肉菜比例和酱汁导致的 `kcal/100g` 分布。
- 整餐共同误差：同一商家/同一餐偏油等相关因素，不能假设各菜完全独立。

建议用版本化经验残差分布做确定种子的 Monte Carlo 或等价分位数传播，输出单项和整餐 P10/P90（最终分位点由校准集确定）。整餐区间从联合样本计算，**不能简单相加每项上下界**；后者无法对应 80% 覆盖率。用独立 calibration split 调整区间膨胀因子，再在锁定 test split 验收 `P(low ≤ referenceKcal ≤ high) ≥ 80%`。

模型 raw score 也必须在 calibration split 上做温度缩放或分桶校准，阈值依据校准后正确率设置。现代神经网络分数常未校准，不能把模型写出的 0.92 展示成“92% 准确”。

### User Correction Path

前端维护 `MealDraft`，每次改克数、换菜名或删除都调用共享 `calculateMeal()` 纯函数，在本地一帧内重算；修正不依赖网络往返。

```ts
type MealDraftItem = {
  itemId: string;
  dishId: string;
  grams: number;
  source: "model" | "user";
};

calculateMeal(draft, {
  catalogVersion,
  calibrationVersion,
  calculatorVersion,
  deterministicSeed,
});
```

候选响应携带该 `dishId` 所需的版本化计算参数；搜索替换时从 Catalog API 获取。反馈上报时服务端重校验 `dishId` 和克数范围。修正事件只是“疑似错误”，未经人工标注不能写入评测真值或别名表。

## API Contracts

所有响应包含 `schemaVersion` 和 `traceId`；可重试写操作要求 `Idempotency-Key`。错误统一为 `{ code, message, retryable, traceId, details? }`，前端只基于稳定 `code` 分支。

### `POST /v1/uploads`

- 输入：`multipart/form-data`，只允许一个 `image`；不接受 URL/base64 JSON。
- 成功 `201`：`{ uploadId, expiresAt, sanitized: true, width, height, traceId }`。
- 错误：`413 IMAGE_TOO_LARGE`、`415 UNSUPPORTED_IMAGE_TYPE`、`422 IMAGE_DECODE_FAILED | IMAGE_TOO_DARK | IMAGE_TOO_BLURRY`。
- `uploadId` 是不透明随机 ID，不返回对象存储 key/签名 URL。

### `POST /v1/analyses`

- 输入：`{ uploadId }`；Header 含 `Idempotency-Key` 和匿名会话 token。
- 成功 `202`：`{ analysisId, status: "queued", statusUrl, expiresAt }`。
- 同一会话 + 同一幂等键 + 相同 body 返回同一 `analysisId`；body 不同返回 `409 IDEMPOTENCY_CONFLICT`。
- `410 UPLOAD_EXPIRED`；配额耗尽返回 `429` + `Retry-After`；过载返回 `503 CAPACITY_EXHAUSTED`，不要把注定超 10 秒的请求无限排队。

### `GET /v1/analyses/{analysisId}`

```ts
type AnalysisResponseV1 =
  | { status: "queued" | "processing"; progressStage: string; retryAfterMs: number }
  | { status: "needs_retake"; reasonCode: string; guidance: string[] }
  | { status: "failed"; error: ApiError }
  | {
      status: "succeeded";
      result: {
        items: Array<{
          itemId: string;
          box: { x: number; y: number; width: number; height: number };
          selectedDishId: string | null;
          candidates: Array<{
            dishId: string;
            displayName: string;
            calibratedConfidence: number | null;
            calculationProfile: unknown;
          }>;
          grams: { center: number; low: number; high: number };
          energyKcal: { center: number; low: number; high: number };
          warningCodes: string[];
        }>;
        mealEnergyKcal: { center: number; low: number; high: number };
        disclaimerCodes: string[];
        versions: {
          model: string; prompt: string; catalog: string;
          normalization: string; calibration: string; calculator: string;
        };
      };
    };
```

`unknown`/`out_of_scope` 是正常业务结果，不是 500。模型超时/不可用与“不含食物”必须分开，才能正确重试和统计。

### `GET /v1/catalog/search?q=...&catalogVersion=...`

- 只返回受支持菜品和计算参数，最多 10 条；限制查询长度、字符集和频率。
- `catalogVersion` 默认当前发布版；编辑旧结果优先固定到原分析版本。

### `POST /v1/feedback/corrections`

- 输入：`analysisId`, `itemId`, `action`, `before`, `after`, `resultVersions`，不上传图片。
- 返回 `202`，失败不阻塞用户编辑。
- 服务端校验克数范围与受控 `dishId`；事件去标识化并单独设 TTL。

## Job State Machine and Failure Policy

```text
uploaded → sanitized → queued → inferencing → normalizing → calculating → succeeded
                └──────────────→ needs_retake
queued/inferencing/normalizing/calculating ────────────────→ failed
任意非终态 ───────────────────────────────────────────────→ expired
```

- Worker 使用租约 + compare-and-set 转移，保证至少一次投递不会产生两份对外结果。
- 第三方超时、429、5xx：在总 10 秒预算内最多一次带抖动重试；重试仍用相同 pipeline 版本。
- Schema 非法：严格输出模式下最多一次重新请求；禁止用正则“修 JSON”。
- 非重试错误：损坏图片、明确不含食物、OOS，不进入重试。
- 供应商熔断时快速 `503`；首版不要未经同一评测集验证就静默切备用模型，否则质量分布和区间校准失效。

### Latency Budget for QLT-05

| Segment | P90 budget | Action when exceeded |
|---------|------------|----------------------|
| Upload + sanitize + quality gate | 0.8 s（不含用户上行网络） | 降低目标长边、检查解码器并发 |
| Queue wait | 0.5 s | 并发扩容；预测排队过长则快速 503 |
| Model inference | 7.0 s | 供应商超时；按 model/prompt/image-size 分片 |
| Normalize + calculate + persist | 0.4 s | 目录内存缓存、批量查询 |
| Poll/network/headroom | 1.3 s | 轮询退避 250→500→1000 ms |

这是初始工程预算；最终按“上传完成到结果可理解”的端到端指标验收，不能只看模型 API 延迟。

## Cache and Rate-limiting Design

### What to Cache

| Cache | Key | TTL/invalidation | Notes |
|-------|-----|------------------|-------|
| Catalog release | `catalog:{version}` | 不变版本可长期缓存 | 发布新版本即换 key，不做原地失效 |
| Idempotency result | `idem:{anonSession}:{key}` | 30–60 min | body hash + analysisId，防重复付费调用 |
| Analysis status/result | `analysis:{id}` | 30–60 min | PostgreSQL 可只留最小审计元数据 |
| Same-session exact retry | `img:{anonSession}:{sha256}:{pipelineVersion}` | 10–30 min | 仅同匿名会话复用，避免跨用户关联 |

生产环境禁止全局按图片 hash 共享模型结果；同一餐图片是否存在本身可能敏感，感知 hash 还会碰撞。不要缓存签名 URL、原始图片或未版本化的模型响应。

### Layered Limits

1. Edge：按 IP/子网/风险信号限制上传字节和突发请求。
2. Application：按匿名会话 + IP 的 token bucket 限制昂贵的 `POST /analyses`。
3. Concurrency：每会话最多 1–2 个进行中分析；全局按供应商设并发 semaphore。
4. Budget circuit：按分钟/小时 token 或费用预算拒绝/降载，防无限模型账单。
5. Queue admission：若预计等待使 P90 超标，返回可重试 503，而不是接受后卡死。

初始阈值只是配置（例如每匿名会话 10 分钟 5 次分析），必须根据 NAT 误伤、正常重拍和成本调整。单进程内存计数在多实例下会被绕过；应使用 Redis 原子 token bucket/sliding window 或托管边缘限流。

## Observability Contract

每次分析一个根 trace，至少包含：

```text
http.upload
  └─ image.validate → image.decode → image.reencode → object.put
analysis.enqueue
worker.run
  ├─ image.quality
  ├─ gen_ai.inference
  ├─ response.schema_validate
  ├─ dish.normalize
  ├─ confidence.calibrate
  ├─ nutrition.calculate
  └─ result.persist → object.delete
```

根 span 记录 `analysis_id`（内部随机 ID）、`pipeline_version`、各组件版本、图像尺寸桶、item_count、结果状态。不要记录图片、base64、对象 key、签名 URL、原始提示/响应或自由文本菜名。模型遥测库若默认抓取 prompt/content，必须显式关闭。

### Required Metrics

| Type | Metrics |
|------|---------|
| Reliability | 成功率、needs-retake、schema-invalid、供应商超时/429/5xx、删除失败、队列重投 |
| Latency | 端到端及各 span p50/p90/p99、queue lag、poll-to-visible |
| Cost | 图片尺寸、input/output tokens、费用估算、重试成本、缓存命中 |
| Product quality proxies | unknown/OOS、候选切换、克数修改、删除率；明确标注为 proxy，不当准确率 |
| Guardrails | Edge 429、应用 429、并发拒绝、预算熔断、超限字节 |
| Offline quality | Top-1/Top-3、克数 MdAPE、区间覆盖/宽度、难例分片校准误差 |

标签控制为低基数：`provider/model/promptVersion/catalogVersion/errorCode/qualityBucket`；禁止用完整 UA、IP、菜名原文或 analysisId 做 metrics label。OpenTelemetry 的统一语义约定适合 spans/metrics/logs，但 GenAI 属性应由一个 adapter 集中映射，避免规范演进散落全库。

## Evaluation-set Architecture

评测不是上线前跑一次脚本，而是与生产 pipeline 同级的系统组件。

### Dataset Record

```ts
type EvalMealV1 = {
  sampleId: string;
  imageRef: string;               // 仅评测桶内部引用
  consentAndLicenseRef: string;
  restaurantGroupId: string;      // 防数据泄漏分组
  sceneTags: string[];            // 光照、角度、餐盒、遮挡、混菜、相似菜
  items: Array<{
    canonicalDishId: string;
    boxOrMask: unknown;
    measuredGrams: number;
    referenceKcal: number;
    referenceMethod: string;
  }>;
  mealReferenceKcal: number;
  annotationVersion: string;
};
```

### Split and Version Rules

- `dev`：提示词、模型选择、归一化规则迭代。
- `calibration`：置信度映射、低置信阈值、克数/热量区间参数。
- `test`：锁定发布门禁，不参与调参；只在候选 release 上运行。
- 按餐厅/商家/拍摄批次分组切分，不能让同一商家近重复图片跨 split。
- manifest 记录数据集 hash、标注版本、菜品目录版本、排除样本及原因；禁止静默覆盖。

每次 run 绑定以下完整身份：

```text
datasetVersion + model + promptVersion + imagePreprocessVersion
+ normalizationVersion + catalogVersion + calibrationVersion + calculatorVersion
+ codeCommit
```

### Release Gates

| Requirement | Metric | Required slice reporting |
|-------------|--------|--------------------------|
| QLT-01 | 菜品 Top-1 ≥ 85% | 每菜/宏平均、相似菜、混菜、遮挡 |
| QLT-02 | 菜品 Top-3 ≥ 95% | unknown 处理与候选去重后计算 |
| QLT-03 | 单项 grams MdAPE ≤ 25% | 饭/肉菜/蔬菜/小配菜、份量桶 |
| QLT-04 | 整餐 reference kcal 区间覆盖 ≥ 80% | 同时报告平均区间宽度，防“无限宽作弊” |
| QLT-05 | 有效请求端到端 P90 ≤ 10 s | 真机网络、图片尺寸、模型供应商分片 |

没有实验室测定时，`referenceKcal` 应明确是“称重食材/成品 + 可追溯营养数据/标准配方”的参考值，不能称绝对真值。生产修正可进入待标注候选池，但必须取得许可、脱离默认图片删除链路并人工复核；否则只保留去标识化修正事件。

## Recommended Project Structure

```text
apps/
├── web/                       # 移动 UI、上传、轮询、MealDraft 编辑
├── api/                       # Upload/Analysis/Catalog/Feedback HTTP 边界
└── worker/                    # 队列消费与 pipeline 状态机
packages/
├── contracts/                 # API/事件/模型输出 schema + 版本
├── domain/
│   ├── catalog/               # dishId、别名、release repository
│   ├── nutrition/             # 中心值与区间纯函数
│   └── corrections/           # MealDraft 与修正事件
├── image/                     # 安全解码、转码、质量门
├── inference/
│   ├── provider/              # VisionProvider adapters
│   ├── normalization/         # 受控菜名映射
│   └── calibration/           # confidence/interval 参数加载
├── pipeline/                  # 编排上述模块，不包含 HTTP
├── persistence/               # PostgreSQL/Redis/object store adapters
└── observability/             # OTel 属性映射、指标、redaction
evals/
├── manifests/                 # 锁定数据集清单与 split
├── annotations/               # schema，不放敏感图片本体
├── runners/                   # 直接调用 packages/pipeline
└── reports/                   # 版本化指标、分片和混淆矩阵
```

依赖方向必须是 `apps → pipeline → domain/contracts`，基础设施通过接口注入；`domain` 不导入 Web 框架、数据库 SDK 或模型 SDK。`web` 与 `worker` 共享 `contracts` 和 `nutrition`，从根上避免客户端重算漂移。

## Patterns to Follow

### Versioned Pipeline Snapshot

每个结果保存模型、提示、目录、校准、计算版本，不只保存最终数字。这样用户修正、离线回放和回归定位才能复现。目录发布采用 immutable release；新版本只影响新分析。

### Ports and Adapters Around External Risk

模型、对象存储、队列、营养数据源都在 adapter 后。最需要替换的是模型供应商和图片存储，不是领域公式。adapter 把第三方错误映射为内部稳定错误码，不把供应商响应直接返给浏览器。

### Idempotent Async Orchestration

分析用 202 + 轮询，而不是让 HTTP 连接绑住模型调用。幂等键、任务租约、状态机和终态快照解决重复点击、移动网络重试和 Worker 崩溃。首版无需 WebSocket/SSE；10 秒窗口内短轮询更简单。

### Pure Calculation Core

所有热量和区间计算是无 I/O 纯函数，输入显式版本化，输出稳定。它同时跑在 Worker、浏览器和 eval runner；任何一处单独实现公式都是缺陷。

## Anti-Patterns

### Model-generated nutrition

**错误：** 让模型同时输出菜名、克数和 kcal。  
**后果：** 不可审计，改克数时无法一致重算，模型升级造成热量漂移。  
**替代：** 模型止于视觉观察；最终计算只接受受控 `dishId`。

### Treating self-reported confidence as probability

**错误：** 展示模型输出的 0–1 分数并按固定 0.7 阈值决定候选。  
**后果：** Top-3 和低置信体验没有统计含义。  
**替代：** 在 calibration split 上校准并按 pipeline version 发布阈值。

### Adding item interval bounds

**错误：** `meal.low = Σ item.low`、`meal.high = Σ item.high`。  
**后果：** 区间覆盖含义错误，忽略同餐相关误差。  
**替代：** 联合误差传播 + held-out coverage calibration。

### Global image/result deduplication

**错误：** 按感知 hash 跨用户缓存结果。  
**后果：** 形成敏感关联，相似图碰撞还会串餐。  
**替代：** 只做同匿名会话、短 TTL、精确 hash 幂等复用。

### Logging model content

**错误：** 把 base64、签名 URL、完整 prompt/response 放进 trace。  
**后果：** 临时图片删除策略被日志永久绕过。  
**替代：** 只记录版本、尺寸桶、token、延迟、错误码和匿名 ID。

### Auto-learning from corrections

**错误：** 用户点候选菜就自动把选择标成真值。  
**后果：** 探索和误操作会污染训练/评测集。  
**替代：** 修正只是待审核信号，经许可和人工标注后才能入集。

### Premature microservices

**错误：** 上传、归一化、计算各部署一个服务。  
**后果：** 版本一致性、Trace、事务和本地开发复杂度暴涨。  
**替代：** 模块化单体 + 单独 Worker；测到瓶颈后再按安全/扩缩容边界拆。

## Scaling Considerations

| Scale | Architecture adjustments |
|-------|--------------------------|
| 0–1k DAU | 单区域 API + Worker，托管 PostgreSQL/Redis/对象存储；先把评测和删除做对 |
| 1k–100k DAU | API/Worker 独立扩缩；Redis 共享限流；按供应商并发扩 Worker；对象删除失败告警 |
| 100k+ DAU | 按测量拆图片净化或推断服务；多区域需保证数据驻留和版本一致；独立成本配额服务 |

第一个瓶颈大概率是模型并发/费用，不是 PostgreSQL；第二个是图片解码 CPU/内存。不要先做数据库分片。队列必须有最大深度和 admission control，扩容不能突破供应商速率上限。

## Dependency-driven Build Order

路线图按以下依赖顺序切阶段；顺序不能颠倒：

1. **数据契约与质量基线**
   - 定义 `dishId`、API schema、`VisionObservationV1`、版本集合、错误码、评测记录 schema。
   - 建约 100 道菜的 catalog release 骨架与 eval manifest/split 规则。
   - 原因：没有稳定 ID 和版本，识别、修正、计算、评测全会返工。

2. **受控目录 + 确定性计算 + Fixture 编辑闭环**
   - 建 `dish/alias/nutrition_profile`、中心值/区间接口和共享 `calculateMeal()`。
   - 用静态 fixture 做结果页：改克数、换候选、删除、即时总计。
   - 原因：先证明模型之外的产品价值；也是模型输出唯一合法落点。

3. **安全图片入口与短期存储**
   - 做字节/签名/像素/解码/重编码、质量门、私有对象、显式删除 + 生命周期兜底。
   - 覆盖恶意文件、解码炸弹、旋转、HEIC、模糊/过暗测试。
   - 原因：模型只能接触净化图片，不能先接模型再补安全。

4. **评测集采集与离线 Runner**
   - 形成 dev/calibration/test，覆盖相似菜、混菜、遮挡、光照、餐盒与称重。
   - Runner 产出 Top-1/3、MdAPE、覆盖率、延迟分片。
   - 原因：模型和单双阶段选择必须由同一数据集决定，不能靠 demo 观感。

5. **模型 Adapter + Schema Guard + 菜名归一化**
   - 接一个通用多模态模型，严格结构化输出，映射目录，支持 unknown/OOS。
   - 在 dev 集比较提示、图片尺寸和必要时两阶段方案；不要调 test。
   - 原因：此层依赖安全图片和目录，同时为校准产生原始预测。

6. **置信度与热量区间校准**
   - 用 calibration split 拟合候选阈值、估重残差、营养密度和整餐相关误差，发布 `calibrationVersion`。
   - 原因：没有真实预测残差就不能凭空设计可信区间。

7. **异步在线编排、缓存与成本保护**
   - 202/轮询、状态机、幂等、同会话缓存、分层限流、并发/费用熔断、超时与删除 finally。
   - 按 10 秒预算做负载和故障测试。
   - 原因：先有稳定 pipeline 才能正确设计重试，否则重试只会放大费用。

8. **真实端到端 UI 与修正反馈**
   - 接通上传/进度/结果/重拍；本地即时重算；反馈异步上报。
   - 维持主流程不超过 3 次操作。
   - 原因：UI 依赖稳定结果 schema，但 fixture 阶段已消除交互风险。

9. **可观测性硬化与锁定测试集发布门禁**
   - 审计 trace/metrics/redaction、删除告警、成本 dashboard；在锁定 test + 真机链路验收全部 QLT。
   - 埋点从前面各阶段同步加入，本阶段是完整性审计，不是最后才开始加日志。

### Research Flags for Roadmap

- **Phase 4–6 需要深研：** 样本量、参考热量、模型/分辨率、单双阶段、置信度与区间校准。
- **Phase 3 需要安全审查：** HEIC 解码供应链、像素/内存限制、对象历史版本删除、供应商保留政策。
- **Phase 7 需要压测：** 供应商速率、冷启动、queue admission、重试是否仍满足 10 秒。
- **Phase 1–2 属于标准工程：** 目录、纯计算器、fixture 编辑闭环应尽早完成，不等模型选型。

## Sources

- [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) — 上传白名单、MIME/签名、随机文件名、大小限制和图片重写；**HIGH**。
- [OpenAI Structured Outputs](https://openai.com/index/introducing-structured-outputs-in-the-api/) — JSON Schema 与视觉输入兼容，结构正确不代表值正确；仅说明 adapter 边界，不锁定供应商；**HIGH**。
- [OpenAI API Data Controls](https://platform.openai.com/docs/models/default-usage-policies-by-endpoint) — endpoint 默认保留、`store` 和 ZDR 行为可能不同；**HIGH（OpenAI）/ MEDIUM（泛化）**。
- [Amazon S3 Object Lifecycle](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html) — expiration 可作存储侧删除兜底；**HIGH**。
- [Cloudflare Rate Limiting Rules](https://developers.cloudflare.com/waf/rate-limiting-rules/) — 边缘按特征、时间窗和阈值限制 API 滥用；**HIGH**。
- [Redis Rate Limiter](https://redis.io/docs/latest/develop/use-cases/rate-limiter/) — 多实例共享配额、token bucket/sliding window 和原子更新；**HIGH**。
- [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/concepts/semantic-conventions/) — traces/metrics/logs 统一属性；**HIGH**。
- [On Calibration of Modern Neural Networks](https://proceedings.mlr.press/v70/guo17a.html) — 分类分数常未校准，温度缩放是可用基线；**HIGH（论文）/ MEDIUM（迁移本项目）**。
- [MLflow Evaluation Datasets](https://mlflow.org/docs/latest/genai/datasets/) — golden set、真实 trace/人工样本和跨版本比较；工具可替换，原则适用；**HIGH**。
- [NIST AI 800-3 announcement](https://www.nist.gov/news-events/news/2026/02/new-report-expanding-ai-evaluation-toolbox-statistical-models) — 评测需明确测量目标、假设和不确定性；**HIGH**。

## Open Questions

- 模型、输入分辨率和单/两阶段尚未确定；必须用 Phase 4–5 同一数据集比较。
- 每道菜可获得的称重/配方样本量决定能否做菜品级区间；稀疏时回退品类级层次模型。
- 中国食物成分表/标准菜谱商业授权仍需法律核实；架构应为每条营养记录保留 source/license 元数据。
- 生产图片推荐推断结束显式删除、24 小时生命周期兜底；最终还要结合故障恢复价值和供应商保留政策确认。

---
*Architecture research for: 中式外卖热量识别 MVP*
*Researched: 2026-08-26*
