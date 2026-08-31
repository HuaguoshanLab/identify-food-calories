# Phase 3: 多模态餐食分析闭环 - Research

**Date:** 2026-08-31  
**Scope:** Qwen-VL 受控接入、图片安全链、现有 Agent 接线、评测与用户端闭环。  
**Research status:** Ready for planning; production provider configuration must still be verified against the selected Model Studio region and model snapshot at implementation time.

## Executive Summary

Phase 3 不是“给现有页面加一个上传按钮”。它要把不可信的二进制图片安全地变为一次性、受审计、可删除的临时输入，再把不可信的视觉输出约束成独立的 Pydantic DTO，最后才允许它进入既有 LangGraph 和确定性营养工具。视觉模型只能提供候选、置信度与估重线索；受控目录与确定性计算继续是营养数值的唯一真相。

推荐按 MVP 垂直切片组织：先交付可拒绝/可删除的图片处理和 Fake Vision Provider，再接入图和确定性工具，随后接入 H5 页面、SSE 状态和冻结评测。不要先把 Provider、数据库和 UI 分成三个互不连通的大层；那会制造一堆无法端到端验证的半成品。

## Official Findings

### Qwen-VL request and structured output

- Model Studio 的 DashScope 和 OpenAI-compatible Chat API 都支持图文消息。图像可以是公开 URL、Data URL/base64 或本地文件；产品不能把 base64 写入数据库、日志或 SSE，因此服务端短时文件路径/受限 URL 才是合理的应用边界。[Qwen API via DashScope](https://help.aliyun.com/en/model-studio/qwen-api-via-dashscope) [OpenAI-compatible Chat](https://help.aliyun.com/en/model-studio/qwen-api-via-openai-chat-completions)
- Qwen-VL 的图像 token 和效果受 `min_pixels`/`max_pixels` 影响；供应商默认值与可用上限随模型版本而变。应用必须自己设置产品安全像素上限，Provider 设置独立、版本化的模型像素预算，不能依赖浮动默认值。[Qwen API via DashScope](https://help.aliyun.com/en/model-studio/qwen-api-via-dashscope)
- 结构化抽取优先使用非 thinking 模式的 JSON 输出。`json_object` 要求提示中包含 JSON 且只保证有效 JSON；JSON Schema 严格模式只支持部分模型。无论使用哪一种，客户端仍必须做 Pydantic 校验，禁止把“模型说它是 JSON”误认为业务契约已成立。[Structured output](https://help.aliyun.com/en/model-studio/qwen-structured-output) [Model Studio error codes](https://help.aliyun.com/en/model-studio/error-code)
- 调用结果的唯一请求 ID、输入/输出 token 计数和视觉图像 token 可用于最小运行审计与成本记录；在流式场景需要显式请求 usage。不能把控制台约一小时后的聚合统计当作单请求的实时对账 API。[Qwen OCR API reference](https://help.aliyun.com/en/model-studio/qwen-vl-ocr-api-reference) [Model usage](https://help.aliyun.com/en/model-studio/model-usage-statistics)

### 地区、留存和成本

- Model Studio 支持多个区域，官方明确请求数据和结果数据储存在所选区域；推理节点所在范围由 service deployment scope 决定。因此“上传即删除”仅能承诺本应用临时副本的删除，不能暗示 Provider 不处理或不留存任何数据。上线前必须选择区域/部署范围并将真实合同写入隐私详情。[Regions and access domains](https://help.aliyun.com/en/model-studio/regions/)
- 官方说传输加密且不把客户数据用于训练，但这不等于零留存、也不等于任意地区合规。产品文案必须区分“本服务删除本地临时副本”和“第三方模型按其所选区域和服务条款处理”。[What is Model Studio](https://help.aliyun.com/en/model-studio/what-is-model-studio)
- Qwen-VL 按输入和输出 token 计费，图片 token 属于请求成本；价格和模型快照会变，配置必须有 model ID、价格快照版本与每 token 价格，测试一律使用 Fake Provider。[Model pricing](https://help.aliyun.com/en/model-studio/model-pricing)

### 安全上传

- 浏览器的 MIME、文件扩展名和 `accept` 属性不是安全机制。后端必须允许列表格式、限制请求和解码后尺寸、真实解码、去元数据、随机服务器文件名、禁止执行/公开直链，并在完成、失败和超时路径删除临时文件。
- 压缩炸弹、伪造 MIME、超大像素、畸形图像、EXIF GPS/相机信息和 API 超时都必须有可测的拒绝或清理路径。图片解码必须发生在大小和像素的有界策略内，不能把未验证原图直接传给 Provider。
- 不引入“永久对象存储”或公共 OSS URL 作为快捷方案；它会直接违反原图不长期保存和最小数据暴露原则。若 Provider 只能消费 URL，URL 必须是不可猜测、短时有效、只读且在请求完成后删除的临时对象；是否需要这一分支由选定 API 的真实能力决定。

## Existing Code and Reusable Patterns

| Concern | Existing implementation | Phase 3 direction |
| --- | --- | --- |
| Provider boundary | `backend/app/providers/reasoning/{ports,dto,factory,fake,deepseek}.py` 已有 Protocol、工厂、Pydantic DTO、Fake 与真实 HTTP adapter | 新建同构 `providers/vision/`，不污染 reasoning port，也不让 Graph 依赖 HTTP payload。 |
| Failure semantics | `ProviderFailureKind` 区分 transient、permanent 与 outcome_unknown；DeepSeek 对运输层不确定结果不盲重试 | Vision Provider 复用该失败分类；请求 ID、调用 attempt 与 digest-only 图片引用用于状态未知对账。 |
| Agent ownership/SSE | `backend/app/agent/{api,service,graph,state}.py` 已绑定登录用户、线程恢复和安全业务事件 | 视觉上传和识别进入同一 `thread_id`，SSE 只传安全摘要和阶段，不传图片、base64、原始模型文本。 |
| Nutrition truth | `backend/app/nutrition/` 提供受控目录与确定性计算/校验 | Vision DTO 只能形成候选/grams estimate；所有公开数值仍经 search/calculate/validate 工具。 |
| H5 interaction | `frontend/src/features/agent/components/AnalyzePage.tsx` 已有文本分析、集中补充、定向修正和线程恢复 | 在同一页面增加拍照/相册、隐私提示、图片错误、视觉进度、估重标签和文字降级，不创建并行流程。 |

## Recommended Architecture

### 1. Upload and temporary image boundary

1. `POST /api/v1/agent/threads` 的多模态变体或独立受保护上传步骤接收 `multipart/form-data`；任何新公开端点必须进入 OpenAPI client generation。
2. `ImageSafetyService` 按允许 MIME/扩展名、字节数、真实解码格式、宽高、像素总数验证；剥离元数据并以随机临时文件名写入应用控制目录。
3. 仅保存不可逆 `sha256`、字节数、规范化 MIME、尺寸、状态、创建/删除时间和当前线程关联等最小元数据。绝不保存原图、base64、EXIF 或可公开访问的固定 URL。
4. 由 `try/finally`、失败补偿与周期性清理共同保证删除。成功、Provider 明确拒绝、验证失败、超时、用户删除和未完成过期都必须可测试地清理。

### 2. Vision Provider contract

`VisionModelProvider.analyze_meal_image(request: VisionMealRequest) -> VisionMealResponse` 应接收已验证的临时文件引用和版本化 prompt/模型/像素预算，不接收 HTTP `UploadFile` 或数据库 ORM。

最小响应 DTO：

- `items[]`: 用户可读原始菜名、受控的 preparation/portion clues、估计克数（可空）、每个字段的置信度、整项置信度、可选位置线索。
- `model_alias`、`provider_request_id`、`usage`（含 image/prompt/completion token）、`latency_ms`、`prompt_version`。
- 不得包含模型思维链、原始提示、原图或未上限的自由文本。

Pydantic schema 不通过即为 `PERMANENT / PROVIDER_SCHEMA_INVALID`，不重试；模型输出中任何目录映射都只能是 hint，仍走已有目录工具。

### 3. Graph and idempotency

- 新的视觉识别节点只在图片状态为 `validated`、没有完成识别结果且运行预算未耗尽时调用 Provider。
- 保存 request key、provider request ID、请求开始/完成/未知状态、计量快照和无敏感图片 digest。客户端断线或刷新按既有 `thread_id` 恢复，不能重复上传或重新调用。
- `OUTCOME_UNKNOWN` 不可“自动重试一次”。先用供应商真实支持的请求状态/幂等能力对账；若 API 没有单请求查询或幂等键，安全默认是停止并让用户明确创建新尝试。计划必须把“是否存在该 Provider 能力”的验证任务列为阻断项。
- 正常 transient 的单次自动重试必须受既有循环、调用、时长、费用预算共同限制，并保持同一应用 request key。

### 4. UI and report

- 上传区在首屏展示拍照与相册选择、可展开隐私详情、支持限制和非医疗免责声明。
- 后端状态驱动可访问的阶段文案：校验图片、识别菜品、等待补充、查询目录、计算营养、校验、完成/失败/已降级；不展示 token、内部节点或模型原文。
- 报告逐项展示受控菜名、grams、是否估算、置信度、四项营养和整餐合计；部分结果/未知项目不可被伪装成完整餐食。
- Phase 3 的确认只确认报告/继续定向修正，不能写入餐食历史；保存确认餐食属于 Phase 4。

## Frozen Evaluation Strategy

测试集必须版本化、hash 绑定，且不含可识别个人信息或原图长期存储。最小类别：

| 类别 | 必须覆盖的情况 | 验证信号 |
| --- | --- | --- |
| 单菜/多菜 | 受控目录可映射的 1、2、3+ 道菜 | item recall、正确目录映射、每项与总计一致 |
| 模糊/目录外 | 相近候选、未知菜、混合已知/未知 | 最多 3 个候选、必须追问/明确未计入，禁止臆造 |
| 份量 | 高置信估重、低置信估重、无份量 | 估重标记、不确定性、低可信度追问 |
| 图片安全 | 假 MIME、损坏/解码失败、超大小/超像素、含 EXIF、压缩炸弹样本 | 稳定错误代码、Provider 零调用、临时文件删除 |
| Provider 故障 | 429/5xx、schema 无效、timeout/outcome unknown | 一次受控重试、零盲重调、降级文字链、无重复计费记录 |
| 生命周期 | 成功、失败、超时、用户删除、清理任务 | 原图不存在；数据库和 SSE 无 base64/原图；最小审计可追溯 |

质量门槛必须在实施前由计划固定为样本数、指标、阈值、允许空值规则与 fail-closed 报告算法；不要拿 Phase 2 的 Spearman 失败合同照抄到分类/估重任务。对估重应使用单位一致的 MAE/MAPE 或区间命中率，对目录映射使用 macro precision/recall，且分母为零时失败而非“跳过”。

## Verification Stack

1. **单元：** Pydantic DTO、fake vision provider、文件验证、EXIF 去除、临时删除、失败分类、请求 key 状态机。
2. **真实 PostgreSQL 集成：** Alembic、线程所有权、最小图片元数据、删除链、重试/对账状态和 Agent resume。
3. **API 合约：** multipart 的 401/403/422、安全错误 schema、OpenAPI、SSE 不泄露敏感数据、同一线程恢复。
4. **前端：** Testing Library + MSW 验证上传控件、隐私披露、集中补充、估重标记、失败与文字降级。
5. **跨栈：** Playwright 在隔离 PostgreSQL 上走真实登录、文件选择/图片提交、追问、报告修正和文字降级。
6. **内置浏览器：** 必须走真实 H5 和公开 API，验证拍照/相册可达路径、错误与成功/追问状态；若宿主浏览器无法提供相机权限，明确记录此限制并用真实文件选择路径覆盖。

## Plan Risks and Required Decisions

| Risk | Planning rule |
| --- | --- |
| 把本地删除说成 Provider 零留存 | 隐私 UI 文案必须由最终区域、部署范围和供应商条款验证后写定；无证据不得作出绝对承诺。 |
| 超时后二次调用导致重复费用 | `OUTCOME_UNKNOWN` 先对账；若官方 API 无请求级对账/幂等能力，必须终止自动重试。 |
| 图片被模型直接“算出营养” | 视觉 state 只保存候选/估重；最终报告只能来自现有确定性工具。 |
| 相机在桌面/测试环境不可用 | 浏览器能力检测后保留相册选择；真实 E2E 以文件选择为主，相机入口单独做 capability 行为测试。 |
| 评测只测成功图片 | 冻结集和 release script 必须包含拒绝、模糊、目录外、低可信度、Provider 失败和删除链。 |

## Sources

- [Alibaba Cloud: Qwen API via DashScope](https://help.aliyun.com/en/model-studio/qwen-api-via-dashscope)
- [Alibaba Cloud: OpenAI-compatible Chat](https://help.aliyun.com/en/model-studio/qwen-api-via-openai-chat-completions)
- [Alibaba Cloud: Structured output](https://help.aliyun.com/en/model-studio/qwen-structured-output)
- [Alibaba Cloud: Regions and access domains](https://help.aliyun.com/en/model-studio/regions/)
- [Alibaba Cloud: Model pricing](https://help.aliyun.com/en/model-studio/model-pricing)
- [Alibaba Cloud: Model usage](https://help.aliyun.com/en/model-studio/model-usage-statistics)

---

*Phase: 3-multimodal-meal-analysis*
*Research completed: 2026-08-31*
