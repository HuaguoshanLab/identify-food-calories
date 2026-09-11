# Phase 2 Frozen Evaluations

## 职责

`evals/` 保存不含真实用户数据的版本化 Agent 冻结案例、机器证据和发布输入合同。冻结集校验本身不调用 Provider；`evaluate_phase2.py run-code-eval` 则只在受 `tests/run_pg.py` 保护的 `food_agent_test` 上，以 Fake Provider 实际运行 Graph、确定性工具与 PostgreSQL Checkpointer。

## 允许依赖

- Python 标准库、版本化 JSONL 夹具与 Phase 2 AI-SPEC 的状态/工具合同。
- 可被 pytest、Phoenix、Promptfoo 和后续发布报告只读消费。
- 禁止保存真实用户餐食、邮箱、密钥、token、图片、完整模型思维链或 Provider 原始响应。

## 文件索引

| 文件 | 职责 |
|---|---|
| `phase02-cases.jsonl` | append-only 的 24 例冻结集：5 happy、5 missing/ambiguity、4 correction、5 persistence/isolation、3 validation/budget、2 adversarial，带可复算 hash 链。 |
| `validate_dataset.py` | 结构、主路径/追问/修正语义、敏感字段和 hash 链的离线 fail-closed 校验器。 |
| `__init__.py` | 让校验器与评测器以同一 Python package 导入，避免 CLI/pytest 模块漂移。 |
| `evaluate_phase2.py` | 运行/验证 hash-bound code evidence，并锁定后续专家、Judge、Promptfoo 和 release 的 fail-closed 输入合同。 |
| `release_phase2.py` | 独立消费已冻结的 code-eval、正式签署和正式 Judge 安全证据，重算阈值与 Spearman，生成唯一、hash-bound 的 `PASS` 或 `FAIL` 发布报告；独立文件避免为报告逻辑改动而使已审核的 code-eval 哈希失效。 |
| `phase2-code-eval.json` | 当前代码、冻结集、图/Fake 与真实 Provider 选择路径/工具/目录/schema 哈希绑定的 24 条真实 Fake Provider→Graph→工具→Checkpoint 观测证据。 |
| `expert-signoff-v1.schema.json` | Plan 02-17 必须使用的稳定 reviewer roster、双角色、逐 case hash 绑定和 Medium 双评分合同。 |
| `expert-signoff-phase2.template.md` | 于女士与陈先生实际填写用的中文空白审核表；不是签署证据，不能通过 validator。 |
| `expert-signoff-phase2-85971eb9.template.md` | 绑定当前 `phase2-code-eval.json` 文件 SHA-256 `85971eb9…` 的双角色复审工作表；本轮已由于女士、陈先生实际填写，旧表不得转写为本轮正式签署。 |
| `expert-signoff-phase2-85971eb9.json` | 从于女士与陈先生实际填写的当前工作表、以及本轮独立 Judge 分数物化的 hash-bound 正式签署；通过 `validate-signoff`。 |
| `expert-signoff-phase2.reference.md` | 与空白表相同案例顺序的格式参考；展示五个具名确认、Medium 评分与独立 Judge 分数的正确写法，不是签署证据。 |
| `promptfooconfig.yaml` | 12 个固定 Medium 文案样本 × 3 次、固定 `maxRetries: 0`/512 output tokens/串行/无缓存的正式 Judge 配置；当前为 `phase02-judge-json-thinking-disabled.v4`，启用严格唯一 `{"score": 1-5整数}`、OpenAI-compatible `response_format: {type: json_object}`，并经 Promptfoo 0.122.0 OpenAI provider 的 `passthrough` 发送 `thinking: {type: disabled}`。证据只记录该请求合同，不记录 reasoning/response 内容；v4 与旧 v1–v3 运行不可直接比较。 |
| `promptfoo-pilot-phase2.yaml` | 非发布的固定 8 次 Promptfoo pilot；串行、无缓存、`maxRetries: 0`，绝不替代 12×3 发布合同。 |
| `run_promptfoo_pilot.py` | 仅在本地子进程读取 `.env` 的安全 pilot 执行器：调用前按价格快照预留上限、每次后按 usage 复算并在首个异常停止。 |
| `promptfoo-pilot-phase2.json` | 不含原始文案、输出或密钥的 pilot 证据：调用数、usage、成本、hash、失败类别与非发布标识。 |
| `run_promptfoo_release.py` | 已授权 36-call 正式 Judge runner：每次单独执行、无缓存、零重试、预算预留与 usage 记账；失败时仅保存脱敏结构摘要和白名单解析阶段，不保存原始导出、文案、输出或密钥。 |
| `promptfoo-release-phase2.json` | 正式 Judge 的安全结果；失败时也如实记录尝试数、成本状态和失败类别，不能冒充 release pass。 |
| `promptfoo-release-phase2-network-rerun.json` | 通过无凭据网络预检后的重新授权正式运行安全证据；它保留独立尝试历史，不能覆盖先前失败。 |
| `promptfoo-release-phase2-network-rerun-2.json` | 使用修复后的安全解析器进行的独立正式重跑证据；首个可记账异常即停止，不能覆盖或合并此前运行。 |
| `promptfoo-release-phase2-network-rerun-3.json` | 采用结构诊断的独立正式运行安全证据；确认导出形态、case 绑定与 usage 已通过，首个 Judge 分数合同异常即停止。 |
| `promptfoo-release-phase2-v2.json` | 独立的 `phase02-judge-json.v2` 正式运行证据；绑定 v2 prompt/config hash，并在首个无效 Judge 分数后保留安全 usage/cost 后停止。 |
| `promptfoo-release-phase2-v3.json` | 独立的 `phase02-judge-json-mode.v3` 正式运行证据；绑定 JSON-object transport/prompt/config 合同，并在首个无效 Judge 分数后保留安全 usage/cost 后停止。 |
| `promptfoo-release-phase2-v4.json` | 独立的 `phase02-judge-json-thinking-disabled.v4` 正式运行证据；36 次串行调用全部完成，记录安全 usage/cost 与稳定 Judge 分数，不包含模型输出或 reasoning。 |
| `promptfoo-release-phase2-85971eb9-preflight.json` | 当前 code-eval 绑定的无联网预算与合同预检证据。 |
| `promptfoo-release-phase2-85971eb9.json` | 当前 code-eval 绑定的独立正式 Judge 运行证据：36 次串行、无缓存、零重试、首个异常停止；不覆盖历史运行。 |
| `promptfoo-release-network-preflight.json` | 不带凭据、非模型请求的 DNS/TLS/root-401 连通性预检证据。 |
| `expert-signoff-phase2.json` | 仅当 36-call Judge 完成且 Medium Judge 分数稳定时，从真实专家模板和实际 Judge 分数物化的正式签署证据。 |
| `phase2-release.json` | 唯一正式发布判定，精确绑定 dataset/code-eval/signoff/Promptfoo 四个 SHA；任何缺失、网络/产品失败、阈值失败或未定义 Spearman 都是 `FAIL`，绝不冒充 `PASS`。 |
| `phase2-release-85971eb9.json` | 当前 code-eval 的独立 hash-bound 发布判定；本轮为 `FAIL`，因为 Judge 分数序列恒为 4，Spearman 未定义。 |
| `release-failures.json` | 每个专家、hash、评分、相关性、阈值和 Promptfoo 输入门的独立 fail-closed 夹具。 |
| `phase03-cases.jsonl` | 12 条 hash 链接的合成多模态回放案例；不含用户图片，覆盖成功、多菜、模糊、目录外、估重、危险图片、Provider 故障、过期与删除。 |
| `phase03-eval.schema.json` | Phase 3 冻结案例字段、禁止敏感字段和必需场景的版本化合同。 |
| `evaluate_phase3.py` | 用 Fake Vision 回放构建 hash-bound 发布报告；零分母、hash 漂移、缺案例、未经授权目录项或任一关键安全断言均 fail closed。 |
| `phase03-release.json` | 当前 Phase 3 冻结评测结果；只保存安全观察、指标、阈值和 hashes，不保存原图、模型原文或密钥。 |
| `phase_06_3/` | Phase 06.3 混合菜品检索的合成、顺序固定、hash 链绑定的冻结案例与离线 loader。 |

## Phase 3 多模态冻结门

```bash
cd backend
.venv/bin/python -m pytest tests/unit/test_phase03_eval_contract.py -q
.venv/bin/python evals/evaluate_phase3.py \
  --dataset evals/phase03-cases.jsonl \
  --output evals/phase03-release.json
```

报告只在预先定义的目录映射、估重、总量一致性、危险图片拒绝、临时删除和 `OUTCOME_UNKNOWN` 不盲重试门全部满足时写入 `PASS`。这份合成回放证据不替代真实浏览器上传验收，也不代表对真实用户图片的准确率承诺。

## 机器评测

不要手写或复制 `phase2-code-eval.json`。唯一合法生成路径是：

```bash
cd backend
uv run python tests/run_pg.py --env-file .env.test.example -- \
  uv run python evals/evaluate_phase2.py run-code-eval \
  --dataset evals/phase02-cases.jsonl --output evals/phase2-code-eval.json
uv run python tests/run_pg.py --env-file .env.test.example -- \
  uv run python evals/evaluate_phase2.py verify-code-eval \
  --dataset evals/phase02-cases.jsonl --result evals/phase2-code-eval.json
```

校验会拒绝缺少实际执行证据、案例顺序变化、dataset/实现哈希陈旧或只携带静态 expected 字段的文件。机器证据不替代 Plan 02-17 的真人双角色签署，也不替代 Plan 02-18 的已授权付费 Promptfoo 输出。

## 发布输入合同

`expert-signoff-phase2.json` 只能由真实、不同的营养师和食物成分数据管理员逐 case 填写。先在顶层 `reviewers` roster 登记稳定 pseudonym 与固定 role；同一真实审核人必须在所有自己审核的 case 中复用同一 pseudonym，不能每例换名。每个 case 的每个 role 恰好只能出现一条 review，review 的 pseudonym/role 必须与 roster 对应，且同一人不能在同一 case 充当多个角色。两者必须分别确认食物编码、阻塞字段、家庭份量可审计性、权威数值和硬校验。对 Medium 样本还必须提供与 dataset/code-eval/rubric hash 绑定的人类 1–5 分与 Judge 1–5 分；发布时从逐 case 原始分数重新计算 Spearman，禁止写入一个预计算相关系数冒充证据。

`self-test` 只验证失败夹具覆盖，不能产生签署、不能批准付费运行，也不会把任何阈值标为通过。

## 发布报告

正式 Judge 证据必须来自已授权、36 次串行、无缓存、零重试的安全 runner。随后由独立报告器读取四个不可变输入；它不会读取 `.env`、调用模型、保存任何文案或模型输出。报告器只有在所有门都满足时才会让 `verify-release` 返回成功：Critical 100%、High 至少 95%、两类 Medium 平均至少 4、没有 1 分，且基于每条原始配对分数重算的 Spearman 至少 0.70。常数序列没有可定义的 Spearman，因此必须 `FAIL`。

```bash
cd backend
uv run python evals/release_phase2.py release \
  --dataset evals/phase02-cases.jsonl \
  --code-eval evals/phase2-code-eval.json \
  --signoff evals/expert-signoff-phase2.json \
  --promptfoo evals/promptfoo-release-phase2-v4.json \
  --output evals/phase2-release.json
uv run python evals/release_phase2.py verify-release evals/phase2-release.json
```

最后一条命令在 `FAIL` 时以非零状态退出；这是发布门正常的 fail-closed 行为，而不是允许重试或改分的信号。

## 非发布 Promptfoo pilot

`promptfoo-pilot-phase2.yaml` 仅在用户明确授权后由以下命令运行。执行器在自己的子进程读取未提交的 `.env`，不会输出或写入密钥；它先按版本化价格快照、固定 8.00 CNY/USD 上限和每例 32 output-token 上限预留预算，再逐例串行运行。未通过预检、任一网络/产品/未分类失败、或 usage 成本越界都会立即停止，绝不重试刷绿。

```bash
cd backend
uv run python evals/run_promptfoo_pilot.py
```

生成的 `promptfoo-pilot-phase2.json` 只保存模型名、hash、调用尝试/完成数、usage、成本和失败类别；不保存原始 case 文案、模型输出、原始 Provider 响应或密钥。它永远不是 12×3 发布通过证据。
