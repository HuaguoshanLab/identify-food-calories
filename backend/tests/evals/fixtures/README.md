# Evaluation Fixture Catalogs

## 职责

`fixtures/` 保存只读、版本固定的合成评测输入。每份 catalog 必须由自己的严格 loader 验证后才能被测试消费。

## 允许依赖

- 允许同目录版本化 JSON、Python 标准库 loader 和 Fake Provider 测试。
- 不得读取生产数据、调用网络或记录真实请求/响应。
- 不得包含用户原文、邮箱、图片 locator、完整 Graph State、Provider body 或 reasoning。

## 文件索引

| 路径 | 职责 |
|---|---|
| `weekly_review/` | `weekly-review-fixtures.v1` 周复盘冻结数据集及其白名单 loader。 |
