# Phase 06.3 Frozen Retrieval Evaluations

## 职责

`phase_06_3/` 保存混合菜品检索的版本化、合成且可复算的冻结案例。它在检索实现之前锁定唯一精确 `PASS`、非精确 `ASK`、资格拒绝和故障降级的输入合同；每案还比较 direct Tool、餐食分析图与饮食规划图的安全检索投影（动作、选中 ID、候选 ID 顺序和固定关系默认值），三者不一致即使调用次数相同也会使 release 失败。不保存真实用户或 Provider 内容。

冻结评测固定以 Fake provider 运行，保证 CI 可复现且不消费密钥；它认证的目标是生产 `text-embedding-v4` / `1024` / `dashscope-text-embedding-v4-1024.v1` 向量空间。激活仍要求该身份的不可变构建已对完整目录快照写入全部完成证据，因此 Fake 评测本身不能激活任何空间，也不能替代真实 DashScope 调用。

2026-09-12 验收范围更正：用户确认当前真实目录不包含“番茄炒蛋”和“西红柿炒鸡蛋”，撤销这组菜名的真实检索及计划替换验收。其未召回不作为真实检索质量失败，也不要求补录菜谱。现有同名合成案例自行构造目录数据，保留用于机制回归；不得将其结果解释为真实目录或 DashScope 的召回能力。

规划入口评测先在回滚事务中构造三条可计算的基准餐菜谱，通过生产规划图生成完整餐单，再以 `feedback="午餐换成…"` 进入真实调整检索分支。检索目标不关联菜谱，因此两图与直接工具的检索返回应一致，而规划层还必须拒绝替换、保留原餐单。这里的三入口一致性指检索工具输出，不代表最终用户页面候选一致。激活集成测试使用本次真实生成的临时 release；历史报告仅供离线合同测试，不通过修改其哈希冒充当前源码的运行证据。

## 允许依赖

- Python 标准库、版本化 JSONL 和本目录离线校验器。
- 后续检索实现和 CI 可以只读消费本数据集。
- 禁止网络、数据库、模型调用，以及真实身份、餐食、身体/健康、图片、提示词、Provider 原文或向量数据。

## 文件索引

| 文件 | 职责 |
|---|---|
| `cases.jsonl` | 24 条以上的合成、顺序固定、hash 链绑定的检索案例。 |
| `evaluate.py` | 严格校验 schema、顺序、类别覆盖、隐私 allowlist、hash 链和三入口检索语义一致性的离线 runner。 |
| `activate.py` | 受控激活入口；actor UUID 或本地 email lookup 二选一，后者只解析 UUID；目标/原因/幂等键和 release 路径均由服务重新校验权限与证据。 |
| `langfuse_publish.py` | 默认不运行的本地实验镜像；仅在 `--publish-langfuse` 下验证完整 PASS release 后导出严格 allowlist 投影。 |
| `langfuse_retention.py` | 仅手工执行的 UTC 30 天详细实验 trace 删除与异步回查；结果只写 stdout JSON。 |
| `__init__.py` | 让 pytest 与离线 runner 使用同一评测包路径。 |

## 可选本地 Langfuse 镜像

Langfuse 不是在线 tracing、CI 门禁或发布权威；Phoenix 仍是唯一在线 tracing 路径。
只有冻结评测已经完成后，才可复制根目录 `.env.langfuse.example` 为未提交的
`.env.langfuse`，替换全部占位符，并显式运行：

```bash
docker compose --env-file .env.langfuse -f docker-compose.langfuse.yml up -d
cd backend
uv run --env-file ../.env.langfuse --extra dev python evals/phase_06_3/langfuse_publish.py --publish-langfuse
```

发布器在创建客户端前拒绝任何未知字段，以及 query、候选正文、用户、餐食、身体/健康、图片、base64、prompt、Provider、向量、密钥、response 或思维链字段。它只镜像合成 case ID/hash、版本/hash、受控候选 ID、PASS/FAIL 与锁定 assertion score；原始 release 字节与判定在发布前后均保持不变。

## 详细实验记录的 30 天留存

本地开源 Langfuse 默认不会自动删除记录。开发者可在已配置的独立 Langfuse 环境中手工运行：

```bash
cd backend
uv run --env-file ../.env.langfuse python evals/phase_06_3/langfuse_retention.py purge --older-than 30d --verify --format json
```

该命令固定只查询 `phase063.frozen_case` 的 trace，使用同一个 UTC cutoff：`timestamp <= now - 30 days`。
它不读取或按 PASS/FAIL、分数、用户、餐食、提示词或其他 payload 过滤；因此成功和失败实验受到相同处理。
每次查询、批量删除、回查与退避都受页面、批次、尝试次数和总截止时间约束。Langfuse 的 trace 删除会级联其 observation 和 score，且可能异步完成；命令会反复回查，未能在界限内证明删除完成时以非零状态退出。

stdout 仅输出以下临时 JSON，不创建 purge 文件、业务数据库记录、评测数据集或 Git artifact：

```json
{"cutoff_utc":"...","scanned":0,"requested":0,"verified_deleted":0,"remaining_overdue":0,"status":"PASS"}
```

失败时 stderr 只有安全状态码，不能把服务响应、trace payload、密钥或 URL 写入日志。若要保存运行结果，由操作者在应用外显式重定向 stdout；这不是应用的数据留存机制。
