# 项目研究总结

**项目：** 中式外卖热量识别  
**领域：** 移动端优先、免登录的单图多菜识别与热量区间估算  
**研究日期：** 2026-08-26  
**总体置信度：** MEDIUM-HIGH

## Executive Summary

这不是一个“AI 看图报卡路里”的普通演示，而是一套受约束的测量近似系统：用户上传一张中式外卖套餐图，系统在约 10 秒内识别多个可见菜品、估算份量，并用受控营养目录计算单项及整餐的中心值和可信区间。单图无法观测真实尺度、食物厚度、隐藏油糖和商家配方，因此专家做法不是追求虚假的个位数精度，而是限制到约 100 道高频菜、输出可校准候选、显式拒识目录外输入，并让用户能换菜名、改克数、删除误识别项后立即重算。

首版应收敛为 **Next.js 16 模块化单体 + 一次同步多模态调用 + 本地版本化目录 + 纯函数计算核心**。浏览器先压缩，Node Route Handler 再做字节、魔数、像素、解码和重编码校验；模型只返回受限的 `dishId` 候选、区域和估重，服务端用 Zod 做语义校验，再由受控目录确定性计算热量。架构报告提出的队列、独立 Worker、PostgreSQL 和对象存储是合理的扩展形态，但对 100 条只读数据和 P90 10 秒的 MVP 属于过度设计：首版不落盘原图、不引入异步基础设施，同时保留 `VisionProvider`、版本化契约和纯领域模块；只有真实压测证明同步请求因断连、尾延迟或独立扩缩容而失败时，才把同一 pipeline 移入 Worker。

最大风险不是前端或框架，而是没有合法且可追溯的营养数据、没有真实称重/配方参考集、错误的评测切分，以及图片安全、跨境处理和匿名刷量。路线图必须先关闭数据权利和评测设计，再做目录与计算器，然后接安全图片入口和模型；上线必须由冻结测试集、真机 P90、全链路删除/留存核查、成本硬上限和合规文案共同放行。若 Top-1、Top-3、估重误差或区间覆盖率未达门槛，正确动作是降级范围或阻止发布，不是扩大区间、改免责声明或把模型自报分数包装成置信度。

## Key Findings

### Recommended Stack

详细结论见 [STACK.md](./STACK.md)。版本以研究日基线锁定，补丁升级可做，但模型、提示词、图片预处理、目录或 schema 变化必须重跑同一评测集。

**核心技术：**

- **Node.js 24 LTS + Next.js 16.3.3 App Router：** 同仓承载移动页面和 Node Route Handler，减少一次服务跳转；Sharp 要求完整 Node runtime，禁止用 Edge runtime。
- **React 19.2.8 + TypeScript 6.0.2 strict：** 用局部状态/`useReducer` 管理 `MealDraft`；暂不采用 Next 仍处实验接入状态的 TypeScript 7。
- **OpenAI Node SDK 7.1.x + Responses API：** 服务端完成单次图片推断，使用严格 `json_schema`、固定模型快照、`store:false`；`gpt-5.6-terra` 仅是初始基线，必须与 Sol/Luna 在项目评测集上比较。
- **Zod 4.4.3：** 同时校验上传/API、模型响应和菜品目录；JSON 结构合法不等于业务值正确。
- **Sharp 0.35.3 + file-type 22：** 服务端魔数检测、安全解码、旋转、像素限制、重编码和元数据剥离；浏览器压缩仅改善体验，不是安全边界。
- **版本化 JSON/CSV 目录：** 约 100 道只读菜使用仓库内 `dishId`、别名、营养分布、来源和版本；无后台编辑、账号或历史时不引入 PostgreSQL。
- **Vitest + Testing Library + Playwright + MSW + 自建 eval CLI：** 单元测试守计算与契约，E2E 守移动流程，冻结评测集守模型质量；PR 测试不调用真实模型。
- **Vercel Node Function + WAF + Sentry/平台可观测性：** 首测 `hkg1` 与 `sin1`；区域、图片长边和 `detail` 均由真机数据决定，不靠地理直觉。

### Expected Features

详细结论见 [FEATURES.md](./FEATURES.md)。

**首版 table stakes：**

- 免登录拍照/相册上传；格式、体积、解码、画质和非食物预检失败时给出可执行的重拍提示。
- 一张套餐图输出每个可见菜品的稳定条目，不得只认主菜或把“提到多个食材”算多菜识别。
- 所有菜名归一化到约 100 道受控目录；目录外返回 `unknown/out_of_scope`，不能强猜。
- 单项展示菜名、取整后的估算克数、中心热量和区间；整餐同屏突出中心估值和校准区间，并说明“按常见做法估算”。
- 低置信度项提供 2–3 个目录内候选；支持目录内搜索替换、改克数、删除，并同步即时重算单项和整餐。
- 分析中、超时、429/5xx、结构失败、换图和重试状态完整；重试不得导致重复付费调用。
- 上传前有短而真实的隐私说明，写清第三方处理类别、地域/留存边界和删除方式；首版原图仅内存处理并尽快释放。
- 移动端主流程最多 3 次操作，结果顺序为“整餐总量 → 需确认项 → 其他明细”。

**竞争性能力：**

- 中式外卖专用目录，而非虚假宣称识别任何食物。
- 由真实残差校准的整餐区间，而非统一 `±20%`。
- 只打扰不确定项，并解释份量、油糖和配方误差，不展示伪精确 AI 概率。
- 数据来源、目录版本和计算规则可追溯。

**v1.x / v2+ 再考虑：**

- v1.x：常见份量快捷项、会话内重拍对照、自愿纠错反馈、目录浏览、本地分享卡；必须由真实使用数据触发。
- v2+：扩菜、第二视角/深度、宏量营养素、账号历史和个性化计划。
- 明确不做：社区、排行榜、医疗/减脂建议、长期默认保存原图、条码/OCR/语音/外卖平台导入、目录外自由搜索。

### Architecture Approach

详细结论见 [ARCHITECTURE.md](./ARCHITECTURE.md)。核心依赖只能单向流动：`净化图片 → 视觉观察 → 受控 dishId → 版本化营养参数 → 确定性中心值与区间`。外部供应商放在 adapter 后，领域计算无网络、无框架、无自由文本；前后端共享同一 `calculateMeal()`，禁止复制公式。每次结果绑定模型、提示词、预处理、目录、归一化、校准和计算版本，确保离线回放和用户修正可复现。

**首版组件边界：**

1. **Mobile Web / MealDraft：** 拍照、压缩、状态与可编辑结果；本地调用共享计算器即时重算。
2. **Upload Guard：** 限制字节/像素/帧数，检查魔数，安全解码、自动旋转、重编码、剥离元数据和画质判断。
3. **Analysis Route / Pipeline：** 统一 deadline、幂等、一次有界重试、错误码和版本快照；首版同步执行且不持久化图片。
4. **VisionProvider + Schema Guard：** 封装供应商、严格结构化输出、白名单/范围/去重/项数校验；模型零工具权限。
5. **Catalog / Normalizer：** 版本化 `dishId`、别名、相似菜和 OOD 行为；只读目录是营养查询唯一入口。
6. **Nutrition / Uncertainty Core：** 纯函数计算中心值，并用校准后的份量残差、营养密度误差和同餐相关误差传播整餐区间。
7. **Eval / Observability：** 离线 runner 复用同一 pipeline；线上只记录版本、尺寸桶、耗时、token、错误码和修正代理指标，不记录图片、URL、prompt 或完整模型响应。

**异步架构升级触发条件：** 只有当真实数据证明同步链路频繁因移动断连丢失结果、P90 无法在单次 Function deadline 内完成、图片净化与推断需要独立扩缩容，或需要可恢复的延迟任务时，才引入 `202 + polling`、Worker、队列和短期私有对象存储。只有多人目录编辑、审批、账号历史或版本查询成为需求时才引入 PostgreSQL。两类升级互不捆绑。

### Critical Pitfalls

详细结论见 [PITFALLS.md](./PITFALLS.md)。

1. **把主菜分类当多菜识别：** 评测实例 precision/recall/F1、漏项率、重复率、OOD 拒识和 Top-1/Top-3；米饭与小菜漏检不能被图片级准确率掩盖。
2. **伪造克数和热量精度：** 克数取合理粒度、允许编辑；同时报告 MdAPE、P90 和偏差。单位热量保存菜品级分布，整餐区间用联合误差传播并同时约束覆盖率与宽度。
3. **数据权利或真值自证：** 每条营养记录保留许可、来源、版本和推导链；中国食物成分数据未获书面授权/法律确认前不得上线，USDA 只补适配的基础食材。
4. **评测泄漏和测试集磨损：** 按订单、商家、拍摄批次分组去重，分为 dev/calibration/锁定 test；测试集不能用于调 prompt，参考热量不能直接等于被测目录中心值乘克数。
5. **把 Structured Outputs 和模型分数当真：** Schema 后仍做业务白名单、范围和去重校验；候选阈值来自独立校准集，模型返回的 kcal 一律丢弃。
6. **上传、隐私与提示注入：** 服务端限制解码资源并重编码；模型无工具权限；不记录/长期保存图片；上线前完成 PIIA、供应商留存与跨境路径核查、恶意图片测试和删除链演练。
7. **匿名成本与尾延迟失控：** 单次模型调用、统一 deadline、幂等、防双击、最多一次受控重试、WAF/并发/预算硬上限和 kill switch；只看平均延迟没有意义。

### Launch Blockers

以下任一项未关闭，禁止公开上线：

- 约 100 道菜的来源、商业使用权、版本和字段级推导链不完整。
- 真实外卖评测集没有订单/商家分组、实际称重、可追溯参考热量或独立 calibration/test。
- 发布候选未达到 Top-1 ≥85%、Top-3 ≥95%、克数 MdAPE ≤25%、整餐区间覆盖率 ≥80%，或用过宽区间作弊；还必须补实例召回、漏项率、P90 估重误差和区间宽度护栏。
- 目标移动网络和并发下端到端 P90 >10 秒，或没有每成功餐成本、限流、硬预算、熔断和 kill switch。
- 图片恶意样本、像素炸弹、元数据剥离、日志脱敏、供应商留存、跨境处理、删除链和隐私告知未经验证。
- UI 仍用“精准、AI 称重、健康/减脂/医疗”等误导表述，或用户无法理解中心值只是估计、区间包含配方与用油不确定性。

## Implications for Roadmap

建议拆为 7 个依赖清晰的阶段。不要把“先搭页面再接 AI”当路线图，那会用占位数据固化错误产品语义。

### Phase 1: 数据权利、领域契约与发布规则

**Rationale:** 营养来源、`dishId` 和版本身份是识别、修正、计算与评测共同依赖；数据授权不清本身就是上线阻断项。  
**Delivers:** 约 100 道候选清单的选取方法；catalog/alias/source/recipe schema；字段级来源与许可台账；API/模型/错误码/版本契约；发布门槛定义。  
**Addresses:** 受控目录、目录外状态、可追溯数据。  
**Avoids:** 未授权商用、自由文本进入营养计算、目录更新导致旧结果漂移。

### Phase 2: 真实评测集与冻结测量协议

**Rationale:** 模型、分辨率、置信阈值和区间都不能在没有真值与正确切分时决定。  
**Delivers:** 带实例标注、实测克数、可追溯参考热量和场景标签的数据记录；按商家/订单/拍摄批次分组的 dev/calibration/test；近重复审计；eval CLI 和完整指标定义。  
**Addresses:** Top-1/Top-3、估重、区间覆盖和 P90 验收语义。  
**Avoids:** 测试泄漏、只认主菜、目录中心值自证、只报中位数或无限放宽区间。

### Phase 3: 目录、确定性计算与 Fixture 纠错闭环

**Rationale:** 先完成模型之外的产品核心，模型输出才有合法落点，UI 也能在固定数据上验证而不依赖外部 API。  
**Delivers:** 版本化 JSON/CSV 目录、别名归一化、中心值与区间接口、共享 `calculateMeal()`；用 fixtures 完成整餐/单项展示、候选切换、目录内搜索、改克数、删除和即时重算。  
**Uses:** TypeScript、Zod、Vitest、React/Testing Library。  
**Avoids:** 模型直接生成 kcal、前后端公式漂移、漂亮但无法修正的结果页。

### Phase 4: 安全图片入口与隐私边界

**Rationale:** 任何真实用户图片进入模型前，上传攻击面、元数据、供应商处理和删除承诺必须先闭环。  
**Delivers:** 浏览器压缩；服务端字节/魔数/像素/帧/解码限制、旋转、重编码、EXIF 清除和画质门；无落盘内存链路；日志 denylist；恶意样本与隐私数据流测试；上传告知草案。  
**Uses:** browser-image-compression、file-type、Sharp、Node runtime。  
**Avoids:** 解码炸弹、伪 MIME、图中提示注入扩大权限、原图进入日志/存储、虚假“零留存”承诺。

### Phase 5: 模型适配、识别评测与区间校准

**Rationale:** 此时已有安全图片、受控目录、真实 dev/calibration 数据和确定性计算器，可以用同一基准做可复现选择。  
**Delivers:** `VisionProvider`、Responses API 严格 schema、业务语义 guard、单次多菜观察、unknown/OOS；Terra/Sol/Luna、1280/1600/2048 和 detail 配置消融；候选置信校准、估重残差和整餐联合区间模型。  
**Addresses:** 多菜识别、2–3 候选、估重、中心值与可信区间。  
**Avoids:** 按 demo 选模型、模型自报概率、自动多模型兜底、串行多调用拖垮 10 秒目标。

### Phase 6: 端到端移动体验与生产保护

**Rationale:** 稳定 pipeline 和结果契约完成后再接真实主流程，才能正确设计失败、重试、限流和反馈。  
**Delivers:** Next.js 同步 `/api/analyze` 链路、统一 deadline 与幂等、防双击、超时/429/5xx/重拍状态；本地即时重算；WAF 限流、并发与费用熔断；结构化 traces/metrics；移动端 3 次操作内体验。  
**Addresses:** 免登录上传、分析状态、可恢复失败、最小打扰确认、隐私说明。  
**Avoids:** 重试风暴、重复计费、伪造进度、日志泄露、匿名刷量。

### Phase 7: 锁定测试集发布门禁与合规验收

**Rationale:** 发布决策必须针对完整候选版本和真实链路，不能把各阶段的局部通过拼成“可上线”。  
**Delivers:** 锁定 test 一次性报告；真机移动网络与并发压测；错误/供应商故障注入；安全与删除演练；每成功餐成本看板；隐私、跨境、广告/健康文案和 AI 标识适用性复核；明确 go/no-go。  
**Addresses:** 全部 QLT 门槛和用户对区间的理解。  
**Avoids:** 指标达标但真实漏项、P90 失控、法律风险或虚假精度仍上线。

### Phase Ordering Rationale

- 数据合法性和测量协议先于模型，否则模型对比没有可信真值，后续所有质量结论都可能作废。
- 目录/计算器和 fixture UI 同阶段，先验证确定性纠错闭环；安全图片入口必须在首次真实图片或供应商调用之前完成。
- 推理与校准放在同一阶段，因为候选阈值、份量残差和热量区间都依赖特定 pipeline 的真实预测分布。
- 生产编排采用同步单体起步，避免为了尚未出现的规模付出 Redis、对象存储、队列和一致性成本；异步升级由测量触发，不作为首版默认依赖。
- 可观测性从 Phase 4–6 随功能植入，Phase 7 只做完整性审计和发布判定，不能最后才补日志。

### Research Flags

**规划时需要深研：**

- **Phase 1：** 约 100 道菜的真实频率依据、中国食物成分数据商业授权、标准配方构建方法需要业务/法律研究。
- **Phase 2：** 目标样本量、参考热量方法、实例标注协议、商家分组切分和区间宽度护栏需要统计/领域专家参与。
- **Phase 4：** iOS Safari/HEIC 支持、Sharp 解码资源边界、供应商默认留存与跨境路径需要安全和法律核查。
- **Phase 5：** 模型/分辨率/detail/单或两阶段、置信校准和联合区间传播必须基于项目实验，属于最高研究风险阶段。
- **Phase 7：** AI 生成合成内容标识、广告/健康表述、PIIA 和跨境处理适用性需正式复核。

**标准模式，可跳过额外 research-phase：**

- **Phase 3：** 版本化静态目录、Zod 校验、纯函数计算和 fixture 编辑闭环均是成熟工程模式。
- **Phase 6 的基础 Web 实现：** Next.js Route Handler、移动表单、错误状态、WAF、Sentry 和 Playwright 有成熟官方路径；只需对本项目性能数据做验证。

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH（模型配置 MEDIUM） | Web、Node、Next、SDK、上传和部署结论有官方文档；具体模型、分辨率、detail 和区域必须实测。 |
| Features | MEDIUM-HIGH | 上传、纠错和单图限制有竞品官方资料及多篇综述支持；区间表达、克数编辑和 100 菜清单尚无目标用户验证。 |
| Architecture | HIGH（部署形态 MEDIUM） | 领域边界、安全管线、版本化与纯计算模式可靠；同步单体是基于 MVP 规模的收敛判断，需用 P90/断连数据验证。 |
| Pitfalls | HIGH | 评测、安全、隐私、单图估重和营养误差有法律、OWASP、官方指南和同行评审依据；营养数据许可仍未解决。 |

**Overall confidence:** MEDIUM-HIGH。产品和工程方向清晰，真正的不确定性集中在数据权利、目标数据集、模型能力和用户对区间的理解，而不是框架选择。

### Gaps to Address

- **100 道菜清单：** 必须由真实外卖菜单/订单频率决定，不能直接复制 ChineseFood-100 类别。
- **营养数据许可：** 《中国食物成分表》或其他中式成菜数据的商业使用权未证实；上线前取得书面许可/法律意见，或改用合法自建配方链。
- **模型与图片配置：** `gpt-5.6-terra`、1600 px、`detail: high/auto`、`hkg1/sin1` 都只是基线，不是结论。
- **评测样本量与真值：** 需确定每菜/每场景样本量、配方与油糖参考热量方法、标注仲裁和置信区间。
- **区间模型：** 数据稀疏时应回退到品类/全局层级分布；整餐相关误差和区间宽度门槛待校准。
- **交互理解：** 验证用户能否理解中心值 + 区间，以及更偏好精确克数、步进还是小/常规/大份。
- **隐私与跨境：** 核实供应商训练使用、人工审阅、abuse log、区域、子处理者、ZDR/MAM 可用性和中国境外提供路径。
- **同步到异步触发点：** 在 Phase 6 记录断连率、Function 超时、P90、独立扩缩容需求；只有达到明确阈值才升级 Worker/queue/object storage。

## Sources

### Primary — HIGH confidence

- [Next.js installation and version 16 upgrade](https://nextjs.org/docs/app/getting-started/installation) — Node/App Router/测试与运行时边界。
- [OpenAI Responses API and data controls](https://platform.openai.com/docs/models/default-usage-policies-by-endpoint) — 结构化图片推断、`store`、默认 abuse logs 与 ZDR/MAM 边界。
- [Vercel Functions limitations](https://vercel.com/docs/functions/limitations) — payload、区域与 Function 限制。
- [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) — 上传白名单、魔数、解码和存储安全。
- [OWASP API4: Unrestricted Resource Consumption](https://owasp.org/API-Security/editions/2023/en/0xa4-unrestricted-resource-consumption/) — 匿名端点、上传、执行时间和第三方费用限制。
- [中华人民共和国个人信息保护法](https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm) — 最小必要、告知、留存、委托处理和跨境要求。
- [餐饮食品营养标识指南](https://www.nhc.gov.cn/sps/c100088/202012/9f71d532e5684a54a63090a75eb737fb/files/1732844456998_62722.pdf) — 能量计算须覆盖原料、烹调油与调味品并可追溯。
- [USDA FoodData Central API Guide](https://fdc.nal.usda.gov/api-guide/) — CC0 授权和基础食材数据边界。

### Secondary — MEDIUM confidence

- [AI dietary assessment scoping review](https://www.jmir.org/2024/1/e51432) — 单图尺度、配方、烹调与份量估计限制。
- [Image-based nutrient estimation for Chinese dishes](https://doi.org/10.1016/j.foodres.2021.110437) — 100 类中国菜识别仍有明显 Top-1 挑战，但数据不代表真实外卖套餐。
- [Food image dietary assessment systematic review](https://pmc.ncbi.nlm.nih.gov/articles/PMC10836267/) — 多食物场景、真值和验证方法差异。
- [MyFitnessPal Meal Scan FAQ](https://support.myfitnesspal.com/hc/en-us/articles/360045761612-Meal-Scan-FAQ) — 候选选择、份量调整和手动纠错是成熟交互模式。
- [On Calibration of Modern Neural Networks](https://proceedings.mlr.press/v70/guo17a.html) — 模型分数需独立校准，不能直接解释为概率。

### Unresolved — LOW confidence

- **中国食物成分数据商业许可：** 未找到明确开放商用许可；只能判定“尚未证实”，必须用书面授权或法律意见关闭。
- **模型、区域和图片参数：** 官方资料只证明能力/限制，无法证明对本项目的最优性，必须用冻结项目数据实测。

---
*Research completed: 2026-08-26*  
*Ready for roadmap: yes*
