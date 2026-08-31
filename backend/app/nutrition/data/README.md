# FDC Seed Data

## 职责

`data/` 保存受版本控制、离线可验证的 USDA FoodData Central 小型目录；它不是网络同步缓存，也不含用户数据。

## 允许依赖

- 只允许 JSON manifest 与其明确的 CC0 来源元数据。
- 由 `app.nutrition.importer` 读取并先校验 canonical content hash，禁止运行时访问 FDC 网络或静默替换数据。

## 文件索引

| 文件 | 职责 |
|---|---|
| `fdc-seed-v1.json` | 初始 24 条版本化、可追溯的 USDA FDC 营养目录记录。 |
| `chili-fried-pork-reference-v1.json` | 单独版本化的辣椒炒肉公开参考配方；固定 250g 成品产量，并保留菜谱与 USDA 原料营养输入。 |
| `fdc-seed-v1-rice-fist-v1.json` | 继承初始目录，并新增专家确认的“熟米饭一拳＝120g”受控份量。 |
