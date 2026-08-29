# H5 Visual Snapshots

## 职责

本目录保存 `h5-visual.spec.ts` 的八张 430×932、light、reduced-motion Git 视觉基线和一个 Phase 2 待审批 candidate。它们只记录用户可见业务页面，不能包含 Mailpit、验证码、Cookie、令牌或其他敏感数据。

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
| `analyze-phase2-candidate-430-chromium-darwin.png` | Phase 2 已完成分析页面 candidate，受控目录食物名以中文显示；等待 02-17 人工审批，绝不是 official baseline。 |

## Phase 2 Candidate Integrity

`analyze-430-chromium-darwin.png` 是既有 official baseline。生成 candidate 前后必须保存 SHA-256 并逐字 `cmp`；不得通过 `--update-snapshots` 重写该 official 文件。candidate 仅由真实注册、登录、公开分析 API 与完成报告页面生成，固定为 430×932、light、reduced-motion。

- official before: `fba54a9449177837dc6f2496d29e479ad26b3b7d0b707de52c2ca6018df2ab4a`
- official after: `fba54a9449177837dc6f2496d29e479ad26b3b7d0b707de52c2ca6018df2ab4a`
- candidate: `530b6bde4cb90cf7d8a99919c76317c58a34b598fa5ed764b7d8adc7f1d47562`
- `cmp`: PASS
