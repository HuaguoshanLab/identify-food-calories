# Weekly Review Fixture Catalog v1

## 职责

`weekly_review/` 冻结周复盘的去标识化合成输入。`loader.py` 是唯一入口：它先检查版本、14 个固定 case、字段白名单与隐私禁令，再返回可供 Fake Provider 评测使用的结构化数据。

## 允许依赖

- 允许 `weekly_review_cases.v1.json`、Python 标准库和后续离线 Fake Provider 测试。
- 不得依赖 Graph、数据库、真实 Provider、网络、用户身份或生产运行账本。
- 禁止保存用户原文、邮箱、图片 locator、完整 State、Provider body、reasoning、密钥或 token。

## 文件索引

| 文件 | 职责 |
|---|---|
| `weekly_review_cases.v1.json` | 格式 `weekly-review-fixtures.v1` 的 14 个固定合成案例。 |
| `loader.py` | 纯标准库严格 loader，提供 `--validate` 命令。 |

## Case 索引

| ID | 场景 |
|---|---|
| `case-01-sufficient-variety` | 覆盖足够的食物多样性。 |
| `case-02-sufficient-regularity` | 覆盖足够的规律进餐。 |
| `case-03-sufficient-balanced` | 覆盖足够的合理搭配。 |
| `case-04-current-week-coverage` | 截至今天的当前周覆盖。 |
| `case-05-low-coverage-meals` | 餐数不足。 |
| `case-06-low-coverage-days` | 天数不足。 |
| `case-07-backfilled-meal` | 按实际用餐日归属的补记。 |
| `case-08-facts-unsupported-output` | 事实不支持的模型输出。 |
| `case-09-medical-risk` | 医疗风险输出。 |
| `case-10-pregnancy-minor-risk` | 孕产或未成年人风险。 |
| `case-11-eating-disorder-self-harm` | 进食障碍、自伤或极端限制风险。 |
| `case-12-schema-invalid` | JSON/schema 无效。 |
| `case-13-privacy-contamination` | 隐私污染拒绝。 |
| `case-14-timeout-unknown-disabled-budget` | 超时、未知结果、停用与预算拒绝。 |

## 格式版本

catalog 的唯一格式标识是 `weekly-review-fixtures.v1`。不兼容变更必须新建版本文件与 loader 合同，不能重写本文件。
