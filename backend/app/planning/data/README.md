# Controlled Recipe Seed Data

## 职责

`data/` 保存项目自有、版本固定且可审计的受控菜谱短数据。它只提供标准菜名、受控份量、槽位与短标签，绝不保存第三方正文、图片、长步骤或购物清单。

## 允许依赖

- 只允许 JSON seed 与仓库内的 `source_reference`；每条记录固定为 `project_authored` 和 `LicenseRef-Project-Authored-v1`。
- 食材只以同一 `catalog_version` 的受控营养目录 stable ID 引用；运行时必须先解析为合格 catalog item，再由 `NutritionService` 按克数重算。
- 不允许网络抓取、Provider 输出、用户数据或任何可还原的第三方菜谱内容。

## 文件索引

| 文件 | 职责 |
|---|---|
| `controlled-recipes.v1.json` | R-03 项目自有的早餐、午餐、晚餐受控菜谱 metadata 与固定食材引用。 |
