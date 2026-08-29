# Phase 2 Frozen Evaluations

## 职责

`evals/` 保存不含真实用户数据的版本化 Agent 冻结案例及其离线校验器。它验证案例语义、hash 链和安全边界；不调用 Provider、数据库或生产 API。

## 允许依赖

- Python 标准库、版本化 JSONL 夹具与 Phase 2 AI-SPEC 的状态/工具合同。
- 可被 pytest、Phoenix、Promptfoo 和后续发布报告只读消费。
- 禁止保存真实用户餐食、邮箱、密钥、token、图片、完整模型思维链或 Provider 原始响应。

## 文件索引

| 文件 | 职责 |
|---|---|
| `phase02-cases.jsonl` | append-only 的 24 例冻结集：5 happy、5 missing/ambiguity、4 correction、5 persistence/isolation、3 validation/budget、2 adversarial，带可复算 hash 链。 |
| `validate_dataset.py` | 结构、主路径/追问/修正语义、敏感字段和 hash 链的离线 fail-closed 校验器 |
