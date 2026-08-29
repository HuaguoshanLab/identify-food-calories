# Phase 2 双角色专家审核填写参考

> **仅供格式参考，不是专家签署，不得转换为 `expert-signoff-phase2.json`。**
> `true` 仅表示该示例中该项由相应角色明确确认；真实审核必须由于女士和陈先生按实际审阅结果填写。

## 填写规则

- 每个 case 的两位专家栏都必须分别写出五个具名 boolean；不可使用孤立的 `5`、`5/5` 或“通过”代替。
- `missing_ambiguity`（006–010）在最后一栏另写两位专家的 1–5 分数：`于=5；陈=5`。这不是五项确认的替代品。
- 非 Medium case 的最后一栏写 `—`。
- 独立 Judge 分数不由专家填写；它另行由获授权的 Promptfoo 运行生成。

### 可直接复制的单元格格式

```text
于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true
陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true
```

## Case 工作表（完整示例）

| case_id | 类别 | 于女士（`yu-nutritionist`） | 陈先生（`chen-food-data-admin`） | Medium 评分 |
| --- | --- | --- | --- | --- |
| phase02-001 | happy | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | — |
| phase02-002 | happy | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | — |
| phase02-003 | happy | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | — |
| phase02-004 | happy | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | — |
| phase02-005 | happy | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | — |
| phase02-006 | missing_ambiguity | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 于=5；陈=5 |
| phase02-007 | missing_ambiguity | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 于=5；陈=5 |
| phase02-008 | missing_ambiguity | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 于=5；陈=5 |
| phase02-009 | missing_ambiguity | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 于=5；陈=5 |
| phase02-010 | missing_ambiguity | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 于=5；陈=5 |
| phase02-011 | correction | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | — |
| phase02-012 | correction | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | — |
| phase02-013 | correction | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | — |
| phase02-014 | correction | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | — |
| phase02-015 | persistence_isolation | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | — |
| phase02-016 | persistence_isolation | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | — |
| phase02-017 | persistence_isolation | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | — |
| phase02-018 | persistence_isolation | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | — |
| phase02-019 | persistence_isolation | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | — |
| phase02-020 | validation_budget | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | — |
| phase02-021 | validation_budget | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | — |
| phase02-022 | validation_budget | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | — |
| phase02-023 | adversarial | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | — |
| phase02-024 | adversarial | 于：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | 陈：food_code=true; blocking_fields=true; household_portion_auditability=true; authoritative_values=true; hard_validation=true | — |

## 独立 Judge 分数格式（另行提供）

```text
phase02-006: 5
phase02-007: 5
phase02-008: 5
phase02-009: 5
phase02-010: 5
```

这五行必须来自独立 Judge；不能复制到专家签署栏，也不能由于女士或陈先生代填。
