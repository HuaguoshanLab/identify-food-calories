# 模型服务后台功能

## 职责

`config/` 展示文字理解、图片识别和相似菜品检索三类模型服务的安全摘要，并只允许变更后续 DeepSeek Agent 调用使用的非密钥运行策略。它经严格 Zod DTO 访问公开后台接口，令牌只作为一次请求参数存在；浏览器不保存、展示或推导密钥、端点、Provider body。

## 允许依赖

- 页面可依赖 React、React Hook Form、Zod、`auth/` 的公开内存会话接口和 `components/ui/` 官方原语。
- `api/` 只可依赖 Zod、浏览器 `fetch` 与构建期验证的后台 API base。
- 禁止导入用户 H5、后端源码、数据库、Provider SDK、密钥或其他 feature 私有状态。

## 文件索引

| 文件 | 职责 |
| --- | --- |
| `README.md` | 配置能力、依赖边界和索引。 |
| `api/` | 严格配置 DTO、读取/写入请求和安全错误分类；目录索引见 `api/README.md`。 |
| `ConfigSummaryPage.tsx` | 三类模型服务摘要、文字模型策略修改、理由确认与 401/403/409 安全体验。 |
| `ConfigSummaryPage.test.tsx` | probe、键盘、敏感字段、并发和重复提交契约。 |
