# Record Components

## 职责

呈现记录列表、详情、用餐时间编辑和破坏性删除确认。

## 允许依赖

- React、Router、records API、认证请求与现有 UI primitives。

## 文件索引

| 文件 | 职责 |
|---|---|
| `RecordsPage.tsx` | 按日期分组的记录列表与真实空态 |
| `MealRecordDetailPage.tsx` | 不会重算的营养快照详情 |
| `MealRecordEditPage.tsx` | 过去用餐时间修改与删除确认 |
