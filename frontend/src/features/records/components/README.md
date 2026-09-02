# Record Components

## 职责

呈现记录列表、详情、用餐时间编辑和破坏性删除确认。

## 允许依赖

- React、Router、records API、认证请求与现有 UI primitives。

## 文件索引

| 文件 | 职责 |
|---|---|
| `RecordsPage.tsx` | projection-only dashboard 的今日、七日趋势和 history 组合页 |
| `TodaySummaryCard.tsx` | overview totals/meal_count 与严格资格目标状态的首屏摘要 |
| `WeeklyTrend.tsx` | 固定七日 SVG 与同数据可访问表格 |
| `HistoryMealList.tsx` | 服务端 local-date 分组和 opaque cursor 历史列表 |
| `MealRecordDetailPage.tsx` | 不会重算的营养快照详情 |
| `MealRecordEditPage.tsx` | 过去用餐时间修改与删除确认 |
