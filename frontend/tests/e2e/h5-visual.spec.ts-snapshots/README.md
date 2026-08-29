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
| `analyze-430-chromium-darwin.png` | 已由用户精确 SHA 批准并在 Plan 02-18 机械晋升的 Phase 2 完成分析 official baseline。 |
| `me-430-chromium-darwin.png` | 我的 Tab |
| `account-430-chromium-darwin.png` | 账号资料 |
| `sessions-430-chromium-darwin.png` | 登录会话 |
| `revoke-dialog-430-chromium-darwin.png` | 撤销会话确认弹窗 |
| `analyze-phase2-candidate-430-chromium-darwin.png` | Phase 2 已完成分析页面的批准来源工件，受控目录食物名以中文显示；它与 current official baseline 字节相同。 |
| `phase2-visual-approval.json` | 用户对 Phase 2 candidate 的精确 SHA 批准，以及 Plan 02-18 的机械晋升记录、旧/新 official SHA 与时间。 |

## Phase 2 Candidate Integrity

candidate 仅由真实注册、登录、公开分析 API 与完成报告页面生成，固定为 430×932、light、reduced-motion。任何 future visual change 仍必须产生新 candidate、得到新的精确 SHA 人工批准，再以 `cmp` 机械复制；不得通过 `--update-snapshots` 覆盖 official。

- official before: `fba54a9449177837dc6f2496d29e479ad26b3b7d0b707de52c2ca6018df2ab4a`
- approved source candidate: `530b6bde4cb90cf7d8a99919c76317c58a34b598fa5ed764b7d8adc7f1d47562`
- official after Plan 02-18 promotion: `530b6bde4cb90cf7d8a99919c76317c58a34b598fa5ed764b7d8adc7f1d47562`
- candidate: `530b6bde4cb90cf7d8a99919c76317c58a34b598fa5ed764b7d8adc7f1d47562`
- approved candidate → official `cmp`: PASS

`phase2-visual-approval.json` 记录了用户于 `2026-08-29T08:50:45Z` 对上述 candidate SHA 的显式批准，以及 Plan 02-18 的晋升。视觉批准不等于发布通过：专家签署和 Promptfoo machine evidence 已独立完成，但当前 release report 仍因常数 paired score 的 Spearman 未定义而 `FAIL`。
