# 菜谱管理

## 职责

显示并维护已关联营养目录的成品菜候选；页面只消费后台严格 DTO，不计算营养或决定资格。

## 文件索引

| 文件 | 职责 |
|---|---|
| `RecipeListPage.tsx` | 菜谱候选列表、导入导出和当前页批量操作。 |
| `RecipeImportDialog.tsx` | CSV 预校验、错误展示和审计原因确认。 |
| `RecipeDialog.tsx` | 仅供本 feature 使用的无业务通用弹窗。 |
| `RecipeListPage.test.tsx` | 公开 API 的批量与导入页面行为测试。 |
| `api/index.ts` | 候选列表、导入、导出和批量操作的严格 HTTP/Zod 客户端。 |
