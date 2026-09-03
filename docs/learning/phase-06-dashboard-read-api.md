# Phase 06：看板读 API 的投影边界

## 为什么看板不读取个人资料

今日摄入和历史记录是 `MealRecord` 的已确认营养快照；它们按保存时确认的 IANA 时区固化为 `consumed_local_date`。看板不能为了显示进度而查询 `PlanningProfile`，更不能从身高、体重或目标类型重新猜一个热量目标：资料更新、删除或旧规划失效后，这种猜测会把已经撤销的目标继续展示给用户。

目标资格只有一个来源：规划模块提供的 `PlanningCompletionTargetPort`。该 Port 只返回 `eligible`、固定目标区间和版本；没有活跃、已验证的完成计划投影时返回 `eligible=false`，DTO 会省略目标值。

## 请求与数据流

```text
GET /api/v1/dashboard/overview
  → dashboard/api.py：认证主体和查询参数
  → dashboard/service.py：本周七个本地日槽位 + 窄目标 Port
  → dashboard/repository.py：user_id + deleted_at + consumed_local_date SQL 聚合
  → MealRecord 已确认营养快照

GET /api/v1/dashboard/history
  → service 解码并校验签名 cursor
  → repository 以 local_date / consumed_at / id DESC keyset 查询
  → service 仅投影历史最小营养事实并签发下一页 opaque cursor
```

Repository 从一开始就在 SQL 加入 `user_id`、`deleted_at IS NULL` 与非空 `consumed_local_date`；不能先载入所有记录再在 Python 或浏览器过滤。`consumed_local_date` 是持久化事实，当前系统时间或前端时区不参与历史归属。

## 如何测试

服务层用 fake repository 和 fake completion Port 验证七天槽位、目标降级和 cursor 调用；HTTPX 合约验证公开路由只暴露 overview/history，并将篡改 cursor 与非法范围映射为 422。Repository 集成测试必须通过隔离 PostgreSQL wrapper：

```bash
cd backend
uv run python tests/run_pg.py --env-file .env.test.example -- \
  uv run pytest tests/dashboard/test_dashboard_service.py \
  tests/integration/test_dashboard_repository.py \
  tests/integration/test_dashboard_overview_projection.py \
  tests/unit/test_dashboard_api.py -q
```

这组测试覆盖软删和跨用户记录不进入聚合、同一时间戳下由 UUID 决定稳定次序，以及无有效 projection 时目标字段从响应中消失。

## 常见错误

- 用 `PlanningProfile` 推导目标：这绕过撤销投影，属于授权错误。
- 将 cursor 做成明文 JSON 或 offset：前者可被篡改，后者在插入记录时会漏项或重复。
- 重新按当前营养目录计算历史 totals：目录会演进，历史必须使用确认时快照。
- 把餐食原文、图片、邮箱、Agent run 或模型数据塞进 history DTO：看板只需要最小的日期、总量和记录 ID。

## 管理目录草稿：服务端预览不是前端回显

目录草稿的可读差异和影响范围必须在服务端形成。后台表单向 `POST /api/v1/admin/catalog-drafts/preview` 提交完整候选目录字段与可选 `draft_id`，但不提交 diff、revision 或影响类别。`admin/api.py` 只把 HTTP 请求交给 `AdminService`；Service 先通过 Repository 读取当前用户的 PostgreSQL 角色，再读取当前草稿，并以允许列表字段计算 `before → after`、`base_revision` 和影响类别。预览不写 draft、audit 或 revision，因此可安全重复请求。

```text
CatalogDraftPage
  → POST /api/v1/admin/catalog-drafts/preview
  → AdminService.require_role + Repository.get_catalog_draft
  → CatalogDraftPreviewResponse（安全字段差异、影响范围、当前 base_revision）
  → PATCH If-Match: base_revision
  → 409 时 GET /catalog-drafts/{id} 后重新 POST preview
```

这里的 `GET /catalog-drafts/{id}` 只返回 `CatalogDraftResponse` 安全投影，仍在每次请求重新做 DB-RBAC。409 后页面保留管理员输入，不直接覆盖表单；它以读取到的最新草稿作为服务端预览基线，再显示下一次确认对话框。这样 UI 不会把本地字段回显伪装成“服务器差异”。

测试分层保持不变：`tests/admin/test_catalog_draft_service.py` 用 fake repository 锁定当前基线、差异和影响类别；`tests/unit/test_admin_catalog_api.py` 锁定公开 HTTP 投影；`CatalogDraftPage.test.tsx` 用 MSW 验证 preview、If-Match 和 409 后的 read + re-preview。Repository 的 `get_catalog_draft` 使用真实 PostgreSQL 的 integration test 覆盖 flush 后按 ID 读取。

## 运行配置：版本是未来调用的并发基线

管理员页面不能把环境中的 provider 密钥或 endpoint 当成“可配置字段”。`GET /api/v1/admin/runtime-config` 只返回最后一个 append-only 策略版本的 allowlist 投影：provider、固定 model alias、启停、价格与上限。它每次先由 `AdminService.require_role` 重读 PostgreSQL 中的 active admin 角色；浏览器 guard 只是较早停止渲染的 UX，不能替代这一步。

```text
ConfigSummaryPage
  → GET /api/v1/admin/runtime-config → DB-RBAC → RuntimeConfigResponse
  → 管理员修改未来策略 + reason + confirm
  → POST /api/v1/admin/runtime-config
       If-Match: 当前 version
       Idempotency-Key: 单次命令 UUID
  → advisory lock 下比较 version → 新 append-only version + 最小审计 diff
  → 409：保留浏览器编辑，要求重新审阅；不静默覆盖
```

`If-Match` 防的是两个管理员都基于同一旧版本创建互相不知情的新策略；它在持有 runtime-config advisory lock 后对比服务端当前版本。Idempotency-Key 防的是网络重试重复创建同一版本。两者都只绑定命令完整性，既不存 token，也不把 frontend 变成 RBAC 真相。

可重复验证：`cd backend && UV_CACHE_DIR=/private/tmp/food-agent-uv uv run pytest tests/admin/test_runtime_config_service.py tests/unit/test_admin_rbac_api.py -q`。前端则用 MSW 验证 Zod 拒绝未允许字段、401/403 清空可见数据、409 保留理由和重复提交禁用；生产构建必须显式传入受限的 `VITE_ADMIN_API_BASE_URL=/api/v1/admin`。
