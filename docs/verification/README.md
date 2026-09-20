# Verification Evidence

## 职责

`docs/verification/` 保存跨栈验收的可复查证据。每份记录必须区分已由真实产品页面与公开 API 验证的事实、自动化门禁结果和未完成项；不能把组件测试、截图、数据库操作、伪造 token 或测试 fixture 说成真实浏览器验收。

## 允许依赖

- 可链接项目内 Playwright、pytest 及公开 UI/API 路径。
- 只记录测试账号的角色，不记录邮箱、密码、验证码、Cookie、access token、refresh token、用户原文、原图或完整模型输出。
- 外部环境、浏览器运行时或凭据不可用时，如实记录阻塞原因与复验前置条件。

## 命名与证据状态

文件统一使用 `YYYY-MM-DD-<功能或验证主题>.md`，日期取首次验证或基线记录日期；续验日期写在正文，不因整理文档而改成当前日期。记录必须保留未通过和未覆盖项。

| 路径 | 状态 | 用途 |
| --- | --- | --- |
| [2026-09-04-dashboard-admin-browser.md](2026-09-04-dashboard-admin-browser.md) | 历史验收 | 保留用户端、后台和拒绝流的当时证据；只支撑文件明确记录的版本与路径。 |
| [2026-09-06-h5-restyle-baseline.md](2026-09-06-h5-restyle-baseline.md) | 历史基线 | 保留 H5 视觉改版前的路由、交互和未验证项；不代表当前 UI。 |
| [2026-09-12-recipe-selection.md](2026-09-12-recipe-selection.md) | 本地验收 | 指定菜谱、份量选择、恢复与计划版本的当时证据。 |
| [2026-09-15-planning-optimization.md](2026-09-15-planning-optimization.md) | 本地验收 | 餐单生成与调整、公开后台权限流程和质量门禁的当时证据。 |

当前变更的验收结果优先写入提交、PR 或交付说明，不为每次小改动新建验证报告。只有需要长期引用的发布门禁或跨系统验收才新增文件。
