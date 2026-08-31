# Phase 2 双角色专家审核空白表

这是一份**空白工作表**，不是签署证据，不能作为 `expert-signoff-phase2.json` 提交或通过 validator。请由真实审核人独立填写；不要让执行者代填确认项或评分。

## 固定输入

- rubric：`phase02-rubric.v1`
- dataset SHA-256：`0c837864750b30d97f545010c763f2540086d545922b515923c684cae57b66ac`
- 当前 code-eval SHA-256：`7cb6a35291e1204ecf9ee5f6fa19ebbb27d457e02b7814afd0100f05b8801ebf`。填写前仍须重新运行 `shasum -a 256 backend/evals/phase2-code-eval.json`；若结果变化，必须重新审阅并逐条写入新值，绝不能使用旧 Summary 的 SHA。

## 审核人 roster（已确认角色，未构成签署）

| 稳定 pseudonym | 真实角色 | 使用规则 |
| --- | --- | --- |
| `yu-nutritionist` | 于女士，营养师 | 于女士审核的每一个 case 一律使用此代号。 |
| `chen-food-data-admin` | 陈先生，食物成分数据管理员 | 陈先生审核的每一个 case 一律使用此代号。 |

真实姓名与 pseudonym 的对应关系应由项目负责人在本表以外安全留存；不要把联系方式、证件信息、密钥或真实用户数据写入仓库。

## 每条 review 的独立确认

于女士和陈先生应各自为每一个 case 填写一条 review。对每条 review，分别写出是否确认下列五项；只有审核人实际确认后，最终 JSON 才能写 `true`：

1. `food_code`：受控食物编码正确。
2. `blocking_fields`：追问/阻塞字段正确。
3. `household_portion_auditability`：家庭份量有可审计依据；没有依据时应正确追问克数。
4. `authoritative_values`：权威营养数值来自受控目录，而非模型。
5. `hard_validation`：硬校验、安全边界和失败处理正确。

`missing_ambiguity` 的五个 case 还必须由两位专家各自给出 `medium_human_score`（1–5）。Promptfoo Judge 分数尚未授权，留空；它不由两位专家代填。

## Case 工作表

在每行的「于/陈」栏分别填入五项结论、必要说明和（仅 Medium）分数。请不要把同一人换 pseudonym，也不要让同一人承担同一 case 的两个角色。

| case_id | 类别 | 于女士（`yu-nutritionist`） | 陈先生（`chen-food-data-admin`） | Medium 评分 |
| --- | --- | --- | --- | --- |
| phase02-001 | happy | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | — |
| phase02-002 | happy | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | — |
| phase02-003 | happy | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | — |
| phase02-004 | happy | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | — |
| phase02-005 | happy | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | — |
| phase02-006 | missing_ambiguity | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 于=__/5；陈=__/5 |
| phase02-007 | missing_ambiguity | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 于=__/5；陈=__/5 |
| phase02-008 | missing_ambiguity | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 于=__/5；陈=__/5 |
| phase02-009 | missing_ambiguity | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 于=__/5；陈=__/5 |
| phase02-010 | missing_ambiguity | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 于=__/5；陈=__/5 |
| phase02-011 | correction | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | — |
| phase02-012 | correction | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | — |
| phase02-013 | correction | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | — |
| phase02-014 | correction | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | — |
| phase02-015 | persistence_isolation | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | — |
| phase02-016 | persistence_isolation | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | — |
| phase02-017 | persistence_isolation | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | — |
| phase02-018 | persistence_isolation | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | — |
| phase02-019 | persistence_isolation | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | — |
| phase02-020 | validation_budget | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | — |
| phase02-021 | validation_budget | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | — |
| phase02-022 | validation_budget | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | — |
| phase02-023 | adversarial | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | — |
| phase02-024 | adversarial | 于：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | 陈：food_code=__; blocking_fields=__; household_portion_auditability=__; authoritative_values=__; hard_validation=__ | — |

## 导出与验证

项目负责人应把两位实际审核人的结果转写到新建的 `backend/evals/expert-signoff-phase2.json`：

- 顶层 `reviewers` 必须含两个固定条目：`yu-nutritionist`/`nutritionist` 和 `chen-food-data-admin`/`food_composition_data_steward`。
- 每 case 必须各有一条营养师和一条数据管理员 review；每一条都绑定同一个 rubric、dataset hash、code-eval hash。
- `judge_scores` 必须等待独立、已授权的 Promptfoo 运行；本表和两位专家都不能填充或代替它。

完成后运行：

```bash
cd backend
.venv/bin/python evals/evaluate_phase2.py validate-signoff \
  --dataset evals/phase02-cases.jsonl \
  --code-eval evals/phase2-code-eval.json \
  --signoff evals/expert-signoff-phase2.json
```
