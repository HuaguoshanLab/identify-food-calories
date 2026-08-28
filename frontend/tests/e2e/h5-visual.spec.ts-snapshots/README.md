# H5 Visual Snapshots

## 职责

本目录保存 `h5-visual.spec.ts` 的八张 430×932、light、reduced-motion Git 视觉基线。它们只记录用户可见业务页面，不能包含 Mailpit、验证码、Cookie、令牌或其他敏感数据。

## 允许依赖

- 只允许由本目录相邻的 `h5-visual.spec.ts` 通过 Playwright `toHaveScreenshot` 生成。
- 只允许固定的 `h5-visual@example.test` 测试账号；会话日期由测试显式 mask。
- 默认 E2E 命令不得更新本目录；视觉变更必须进入 Plan 09 人工审查。

## 文件索引

| 文件 | 页面状态 |
| --- | --- |
| `landing-430-chromium-darwin.png` | 公开首页 |
| `login-430-chromium-darwin.png` | 登录 |
| `register-430-chromium-darwin.png` | 注册 |
| `analyze-430-chromium-darwin.png` | 分析 Tab 占位 |
| `me-430-chromium-darwin.png` | 我的 Tab |
| `account-430-chromium-darwin.png` | 账号资料 |
| `sessions-430-chromium-darwin.png` | 登录会话 |
| `revoke-dialog-430-chromium-darwin.png` | 撤销会话确认弹窗 |
