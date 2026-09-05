---
status: resolved
trigger: "客户端先输入食物名，再补充克重后没有生成热量；一次输入名称与100g正常"
mode: diagnose-only
created: 2026-09-05
updated: 2026-09-05
---

# 克重补充导致分析失败

## Symptoms

- expected: 缺少重量时追问，提交有效克重后继续计算。
- actual: 用户报告补充后未生成报告，且文字分析显示“图片未能识别”。
- reproduction: 食物描述不含重量，进入克数补充框后提交。
- timeline: 用户本次报告；首次发生时间未知。
- uncertainty: 用户原始补充框的确切输入尚未确认；不能断言其输入了单位。

## Current Focus

- hypothesis: 补充输入带单位时严格数值解析失败；Service 改写等待状态后，Graph 的无操作返回被归为失败。
- next_action: 等用户要求修复后，补充输入规范化、无效恢复保留等待状态、文本/图像错误提示区分及回归测试。
- scope: 仅分析原因，不修改业务代码。

## Evidence

- 内置浏览器真实页面对照：描述“西兰花”，追问填纯数字 `100`，成功显示 35.0 kcal。
- 另一轮相同描述进入追问，填 `100g`，复现截图同样的“本次分析暂未完成”和“图片未能识别”。没有点击确认保存，诊断产生分析会话但未新增餐食记录。
- `AnalyzePage.tsx:214` 对克重只 trim 后原样放入 JSON；`service.py:536` 附近对 JSON 答案直接返回，不走下方自然语言克重正则。
- `graph.py:701` 使用 Decimal(str(value))，`100g`、`100克` 无法解析；`_apply_resume` 返回原 state。
- `service.py:273` 在恢复前将 previous.status 从 waiting_input 改为 accepted；graph 的无效答案无操作返回因此保留 accepted，而不是 waiting_input。
- `service.py:431` 将既非 waiting_input、limit_reached 又非 completed 的返回归为 failed / ANALYSIS_NOT_COMPLETED。
- `AnalyzePage.tsx:67` 的恢复提示除两个特定错误码外一律使用图片失败文案，没有区分文字分析。
- 无网络的现有 Fake Provider / Tool 对照实验：相同等待状态经过 Service 同款 accepted 改写后，`100` -> completed、3 次营养工具；`100g` 和 `100克` -> accepted / ask_user、0 次营养工具、原对象返回。该实验不验证真实营养值，仅验证状态分支。

## Eliminated

- 西兰花目录完全缺失：纯数字追问分支实际成功计算。
- 所有补充请求均无法恢复：同上，正常数字可恢复。
- 图片模型故障：复现场景未上传任何图片，错误提示来自通用前端兜底。

## Resolution

- root_cause: 输入约定不一致，叠加 Service/Graph 状态恢复契约冲突；通用错误误用图片文案。
- fix: 未实施。
- verification: 真实浏览器成功/失败对照、源码调用链、离线状态机对照；未跑完整回归测试，因为本次仅诊断且未改业务代码。
- remaining_uncertainty: 原用户失败是否由带单位或其他无效克重触发，需要原始输入确认；这里已证明一条可复现的相同故障路径。

## 后续修复（用户确认后）

已在 quick 260905-lfe 修复并验证：独立重量方法、支持单位转换、错误输入拒绝且保持等待、文字/图片提示区分。84 项后端测试、18 项前端测试、1 项真实 PostgreSQL 恢复测试通过；内置浏览器验证100kg/100斤拒绝后0.1kg继续及2两修正。完整证据见相应 quick SUMMARY，原诊断的不确定性保留，不倒改历史事实。
