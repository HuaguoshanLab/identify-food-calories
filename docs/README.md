# Docs

## 职责

`docs/` 保存面向开发者的中文教学和操作文档。这里解释已经落地的工程边界、请求链路和调试方法，不替代 `.planning/` 中的产品决策，也不保存任何密钥、令牌、邮件原文或用户数据。

## 允许依赖

- Markdown 链接到已提交的代码、README 和测试文件。
- 文档中的命令必须可在当前仓库结构中执行，并明确开发库与测试库边界。
- 禁止复制生产密钥、验证码、refresh token、原图/base64 或完整模型思维链。

## 文件索引

| 路径 | 职责 |
|---|---|
| `learning/` | 从前端开发者视角解释后端认证、餐次记录与工程基础 |
| `learning/phase-02-agent-core.md` | 可追问文字餐食 Agent、确定性营养边界、Checkpoint/ledger、SSE、评测和调试的中文教学文档。 |
| `learning/phase-03-multimodal-meal-analysis.md` | 多模态图片安全、Vision Provider、确定性营养、删除链、冻结评测与真实浏览器证据。 |
| `learning/phase-06-dashboard-read-api.md` | 看板餐食快照、完成计划资格投影、签名 keyset cursor 与真实 PostgreSQL 测试证据。 |
| `ui/` | 用户 H5 的跨阶段 UI 基座与组件契约 |
| `verification/` | 可复现实机与浏览器验收记录；只记录路径、角色与可观察结果，不记录账号、密码、令牌或用户数据。 |
