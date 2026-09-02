# Offline Evaluation Fixtures

## 职责

`evals/` 保存可重复执行的离线评测输入。它不是产品数据、模型日志或 Provider 回包的归档处；所有内容必须是去标识化的合成资料。

## 允许依赖

- 允许 Python 标准库 loader、冻结 JSON catalog 和后续使用 Fake Provider 的测试。
- 不得依赖真实 Provider、数据库、网络、用户会话或真实健康记录。
- 不得保存用户原文、邮箱、图片定位符、完整 State、Provider body 或 reasoning。

## 文件索引

| 路径 | 职责 |
|---|---|
| `fixtures/` | 按能力分组的版本化、去标识化评测 catalog。 |
