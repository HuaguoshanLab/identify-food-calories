# Phase 06.3 Frozen Retrieval Evaluations

## 职责

`phase_06_3/` 保存混合菜品检索的版本化、合成且可复算的冻结案例。它在检索实现之前锁定唯一精确 `PASS`、非精确 `ASK`、资格拒绝和故障降级的输入合同；不保存真实用户或 Provider 内容。

## 允许依赖

- Python 标准库、版本化 JSONL 和本目录离线校验器。
- 后续检索实现和 CI 可以只读消费本数据集。
- 禁止网络、数据库、模型调用，以及真实身份、餐食、身体/健康、图片、提示词、Provider 原文或向量数据。

## 文件索引

| 文件 | 职责 |
|---|---|
| `cases.jsonl` | 24 条以上的合成、顺序固定、hash 链绑定的检索案例。 |
| `evaluate.py` | 严格校验 schema、顺序、类别覆盖、隐私 allowlist 与 hash 链的离线 loader。 |
| `activate.py` | 受控激活入口；只接受 actor/目标/原因/幂等键和 release 路径，所有权限与证据由服务重新校验。 |
| `__init__.py` | 让 pytest 与离线 runner 使用同一评测包路径。 |
