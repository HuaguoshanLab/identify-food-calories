# Verification Evidence

## 职责

`docs/verification/` 保存跨栈验收的可复查证据。每份记录必须区分已由真实产品页面与公开 API 验证的事实、自动化门禁结果和未完成项；不能把组件测试、截图、数据库操作、伪造 token 或测试 fixture 说成真实浏览器验收。

## 允许依赖

- 可链接项目内 Playwright、pytest 及公开 UI/API 路径。
- 只记录测试账号的角色，不记录邮箱、密码、验证码、Cookie、access token、refresh token、用户原文、原图或完整模型输出。
- 外部环境、浏览器运行时或凭据不可用时，如实记录阻塞原因与复验前置条件。

## 文件索引

| 路径 | 职责 |
| --- | --- |
| `README.md` | 验收证据目录边界与索引。 |
| `phase-06-browser-acceptance.md` | Phase 06 用户 H5、后台、拒绝流和自动化门禁记录；明确区分实际 Codex 内置浏览器观察、可重复 Playwright 与 blocked/failed 回归，后两者不能冒充实机验收。 |
