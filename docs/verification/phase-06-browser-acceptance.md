# Phase 06 浏览器验收记录

**执行日期：** 2026-09-04（Asia/Shanghai）  
**证据边界：** 本记录的浏览器结论只来自 Codex 内置浏览器对真实产品页面和公开 API 的操作。没有使用 Playwright、截图、数据库直写、seed、token 或 Cookie 注入、内部函数作为替代；也不记录邮箱、密码、验证码、token、Cookie、记录标识符、用户原文、原图、密钥、Provider 请求体或完整模型输出。

## 自动化门禁（与内置浏览器证据分层）

| 门禁 | 实际结果 | 可复查结论 |
| --- | --- | --- |
| H5 Playwright：`records-dashboard` | PASS | 专属 guarded runner 在空隔离数据库中先经 admin SPA 创建 RuntimeConfig，再由普通用户完成分析、安全 SSE、确认保存和 Records 四项公开投影。该结果是可重复自动化证据，不替代下文的内置浏览器验收。 |
| 独立后台 Playwright：`admin-management` | PASS，最新 isolated run 为 14.6 秒 | 曾在目录审核对话框超时；已确认原因为提交按钮未进入视口。修复真实 UI 滚动约束、runner viewport 和 in-viewport 断言后，最新隔离运行观察到 RuntimeConfig `201`、审核/发布/失格 `200` 以及普通用户 probe `403`。 |

## Codex 内置浏览器：已通过的真实公开路径

**浏览器环境：** 本地真实 SPA：用户端 `http://127.0.0.1:5178`，独立后台 `http://127.0.0.1:5179`。下列路径均通过实际页面交互和产品公开 API 完成；没有数据库或身份捷径。

| 路径 | 角色 | 可观察结果 | 结论 |
| --- | --- | --- | --- |
| `http://127.0.0.1:5179/admin/model-configs` | 已认证管理员，同一真实 SPA 会话 | 在“变更未来配置”对话框创建启用的、非密钥 RuntimeConfig；页面从 v1 更新为“配置版本 v2”并显示已启用，未显示密钥或 endpoint。 | PASS：管理员只能通过后台 UI 创建未来生效的非密钥配置，服务器确认已在页面可见。 |
| `http://127.0.0.1:5178/app/analyze` → `http://127.0.0.1:5178/app/records` | 新建并验证的普通测试用户 | 提交受控白米饭文本后，页面显示安全的五阶段进度、130 kcal 报告和普通饮食参考；点击“确认并保存”后，Records 显示 130 kcal / 1 餐、7 日趋势表、当日 history 和低覆盖周复盘。页面未显示 Provider、node、stack、reasoning、raw payload 或 secret。 | PASS：普通用户从真实分析、安全流到保存和四项记录投影的公开路径完整可用。 |
| `http://127.0.0.1:5179/admin/login?returnTo=%2Fadmin%2Foverview` → `/admin/forbidden` | 同一普通测试用户 | 真实登录后，应用实际 Bearer probe 拒绝访问并到达 forbidden 页面；仅显示无后台权限和重新登录/返回用户端，未渲染 AdminShell、catalog 或 overview。 | PASS：普通用户认证不等于后台授权，拒绝页面没有私有后台内容。 |

本地调试管理员也经页面完成了同一受控餐食的 analyze → 130 kcal → save → Records 链，累计两餐 / 260 kcal。该结果仅作为调试交叉检查；本验收以普通测试用户的一餐记录为主证据。

## 未在本轮内置浏览器复验的项目

以下项目不因已有 Playwright、API 测试或旧页面记录自动升级为浏览器验收通过：

| 项目 | 当前状态 | 后续复验要求 |
| --- | --- | --- |
| 跨日补记与 history cursor 翻页顺序 | 未在本轮浏览器路径覆盖 | 在隔离真实会话中经页面创建多条跨日记录并翻页。 |
| 周复盘的 success、safety-abstain 与 retryable 状态 | 本轮只观察到低覆盖周复盘 | 在真实页面中分别触发并记录安全状态。 |
| `/admin/overview`、UTC filter 深链接和 RuntimeConfig disable | 本轮不作浏览器结论 | 以已认证管理员的同一 SPA 会话逐项操作并观察。 |
| catalog 失格后的历史 snapshot 稳定性 | 自动化已覆盖生命周期命令，浏览器未复验该特定组合 | 在隔离管理员 UI 中执行失格并以实际用户记录复核历史 snapshot。 |
| 过期管理员会话拒绝 | 未在本轮浏览器路径覆盖 | 在真实会话失效后确认固定重新登录提示与私有缓存不渲染。 |

## 运行历史说明

此前交接中出现过服务不可用/503；后续恢复后的隔离运行和本次页面路径均已可用。现有证据不足以判定那次 503 的根因，因此不作根因归属。

## 复验规则

任何新增结论都必须记录日期、路径、角色和页面可观察结果，并继续遵守本文件的最小化记录边界。Playwright、截图、mock、直接数据库操作或身份材料注入只能作为独立证据，不能替代 Codex 内置浏览器的公开页面验收。
