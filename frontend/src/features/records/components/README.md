# Record Components

## 职责

呈现记录列表、详情、用餐时间编辑和破坏性删除确认。

根页、详情与编辑页的唯一h1由外层固定页头提供；页面只保留业务说明、状态及操作。

## 允许依赖

- React、Router、TanStack Query、React Hook Form、Zod、records API、认证请求与现有 UI primitives。

## 文件索引

| 文件 | 职责 |
|---|---|
| `RecordsPage.tsx` | 仅将浏览器 IANA zone 用作 confirmation 输入；strict same-zone 200 后才读取服务端 current 的今日、七日趋势、history 与周复盘，409 冲突关闭所有 dashboard reads |
| `RecordsPage.test.tsx` | strict 200/409 gate、Shanghai/Los Angeles server projection 与失败关闭 dashboard 请求的确定性回归测试；不依赖 host TZ |
| `TodaySummaryCard.tsx` | overview totals/meal_count 与严格资格目标状态的首屏摘要 |
| `WeeklyTrend.tsx` | 固定七日 SVG 与同数据可访问表格 |
| `WeeklyReview.tsx` | 覆盖事实、闭合安全状态与受限一般饮食参考 |
| `HistoryMealList.tsx` | 服务端 local-date 分组和 opaque cursor 历史列表 |
| `MealRecordDetailPage.tsx` | 不会重算的营养快照详情 |
| `MealRecordEditPage.tsx` | RHF/Zod 餐次与过去用餐时间修改、时区提交、dashboard 缓存刷新与删除确认 |
| `MealRecordEditPage.test.tsx` | 旧记录补选餐次、时间独立编辑、未来时间拒绝及保存失败保留输入。 |
