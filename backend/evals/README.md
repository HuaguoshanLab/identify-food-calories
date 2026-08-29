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
| `phase2-code-eval.json` | 当前代码、冻结集、图/Provider/工具/目录/schema 哈希绑定的 24 条真实 Fake Provider→Graph→工具→Checkpoint 观测证据。 |

## 机器评测

不要手写或复制 `phase2-code-eval.json`。唯一合法生成路径是：

```bash
cd backend
.venv/bin/python tests/run_pg.py --env-file .env.test.example -- \
  .venv/bin/python evals/evaluate_phase2.py run-code-eval \
  --dataset evals/phase02-cases.jsonl --output evals/phase2-code-eval.json
.venv/bin/python tests/run_pg.py --env-file .env.test.example -- \
  .venv/bin/python evals/evaluate_phase2.py verify-code-eval \
  --dataset evals/phase02-cases.jsonl --result evals/phase2-code-eval.json
```

校验会拒绝缺少实际执行证据、案例顺序变化、dataset/实现哈希陈旧或只携带静态 expected 字段的文件。机器证据不替代 Plan 02-17 的真人双角色签署，也不替代 Plan 02-18 的已授权付费 Promptfoo 输出。
