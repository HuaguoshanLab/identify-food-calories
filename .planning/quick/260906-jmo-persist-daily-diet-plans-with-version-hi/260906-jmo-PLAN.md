---
quick_id: 260906-jmo
status: complete
---
# 今日计划存档与历史

用户已批准：自动保存成功餐单、日期与时区归属、调整/重新生成保留版本、今日自动恢复、历史查看和删除。使用 GSD quick 默认流程，由主代理内联执行。

## 1. 后端业务存档
- files: backend/app/planning/*, backend/app/agent/{api,service}.py, backend/migrations/versions/0021_diet_plans.py
- action: PostgreSQL 两张表保存按用户日期归属的计划与不可变完整版本快照；通过领域 Port 在完成边界保存，和 completed 状态同事务。生成日期按线程开始时间及已确认统计时区固定；重放幂等、并发串行、删除与旧线程防复活。公开 API 提供今日、分页历史、详情、版本和删除，严格 tenant-filter。
- verify: fake repository 单测、真实 PostgreSQL 集成/API 测试、ruff/mypy。
- done: 生成失败不覆盖旧版；不保存个人身体资料也可保存餐单；会话清理不影响正式存档。

## 2. H5 页面闭环
- files: frontend/src/features/plans/*, frontend/src/{App,routePaths}.tsx/ts
- action: 抽取 API report schema，TanStack Query 读取今日计划；时区未确认时复用 records 公开确认 API；显示已保存及日期、重新生成、历史详情/版本和删除确认。历史只读；当前且会话可恢复才允许调整。保留四 Tab 和详情页壳。
- verify: Vitest 组件测试、类型/静态检查、构建、Playwright 实际注册生成刷新调整历史删除路径。
- done: 页面往返/刷新不丢计划，加载与失败可重试，保存与个人资料授权文案明确。

## 3. 验证与文档
- files: docs/learning/*, README 索引, .planning/STATE.md, 本目录 SUMMARY
- action: 内置浏览器走真实页面与公开 API；补中文教学和索引，记录实际测试结果与边界，原子提交。
- verify: 真实浏览器路径、响应式与错误态，git diff 检查。
- done: 交付可复核证据，未验证部分明确记录。
