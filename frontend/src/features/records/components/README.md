# Record Components

## 职责

呈现记录列表、详情、用餐时间编辑和破坏性删除确认。

## 允许依赖

- React、Router、records API、认证请求与现有 UI primitives。

## 文件索引

| 文件 | 职责 |
|---|---|
| `RecordsPage.tsx` | 先确认浏览器 IANA zone、再消费 server-authoritative projection 的今日、七日趋势和 history 组合页；本地 Monday 仅用 `Intl.formatToParts()` calendar parts 序列化 |
| `RecordsPage.test.tsx` | Shanghai 周一凌晨、Los Angeles/DST、确认 200/409 gate 与失败关闭 dashboard 请求的回归测试 |
| `TodaySummaryCard.tsx` | overview totals/meal_count 与严格资格目标状态的首屏摘要 |
| `WeeklyTrend.tsx` | 固定七日 SVG 与同数据可访问表格 |
| `WeeklyReview.tsx` | 覆盖事实、闭合安全状态与受限一般饮食参考 |
| `HistoryMealList.tsx` | 服务端 local-date 分组和 opaque cursor 历史列表 |
| `MealRecordDetailPage.tsx` | 不会重算的营养快照详情 |
| `MealRecordEditPage.tsx` | 过去用餐时间修改与删除确认 |
