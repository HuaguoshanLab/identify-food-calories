---
task: 260905-lfe
status: complete
date: 2026-09-05
---

# 独立重量换算与补充恢复

## 实现

- `agent/weight.py::parse_weight_grams` 独立纯函数，规则版本 meal-weight-input.v1。支持已确认单位、完整匹配、Decimal、转换后 0–2000g（不含零），非法输入抛固定安全异常。
- JSON 补充、JSON 修正和单问题纯文本回复共用该方法；Graph 的重量转换也复用。首次完整餐食描述仍由 Provider 解析，不声称变成任意自然语言单位解析器。
- HTTP 对非法重量返回 INVALID_WEIGHT / 422，在改写运行和 checkpoint 前拒绝。其他无效恢复输入进入 Graph 时也保留等待状态。
- UI 保留完整单位与待更正输入；不重复维护前端换算公式。修正重量不再截取数字。通用文字失败不再误报图片识别失败。
- 无新增依赖、数据库迁移、目录业务数据修改或 Phase 推进。

## 验证

- 后端定向测试：84 passed（单位解析、JSON/文本共用、运行时、上下文、API 契约、多模态）。Ruff 通过。
- 前端 Agent 范围：3 files / 18 tests passed；typecheck、build 通过。构建有既有大 chunk 提示，非失败。
- 隔离 PostgreSQL：1 passed / 2 deselected；多次错误保持完整快照，未知目标仍 waiting，0.1kg 恢复为完成，3两修正，不重复模型解析。
- OpenAPI generate-all / check-all 通过。生成过程同时补齐此前未同步的既有 diet-planning operation，仅同步生成物，未开发规划功能。
- 实际内置浏览器 5178：西兰花等待重量 → 100kg 超限保留输入 → 100斤同样拒绝 → 0.1kg 同一会话完成，100.0g / 35.0 kcal → 修正“西兰花改为2两”，100g / 35.0 kcal。未点击确认保存。
- 既有失败会话恢复页显示“本次餐食分析未完成”，不再显示“图片未能识别”。
- 本次未运行完整仓库回归或新增 Playwright 全链套件；交付证据是定向组件/领域/API/真实 PostgreSQL 测试及内置浏览器真实交互。

## 测试过程中处理

旧纵向测试缺少 Phase 6 的运行配置准入，且未计入后续新增的显式偏好捕获工具；在隔离测试中通过 AdminService 配置测试策略，并更新事实断言。测试 Provider 仍强制 Fake，不绕过准入、不访问付费模型。

## 提交

- `c721aab`：重量解析、后端恢复与测试、生成契约同步。
- `4709532`：前端保留单位/输入、错误提示、组件测试与中文教学。
