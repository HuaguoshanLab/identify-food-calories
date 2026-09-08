# Unit Tests

## 职责

`tests/unit/` 验证纯配置与业务行为，不启动 PostgreSQL、网络服务或 Docker。

## 允许依赖

- pytest、标准库和待测模块的公开接口。
- 可以使用 fake repository/provider；禁止连接真实数据库或外部 API。

## 文件索引

- `test_admin_catalog_api.py`：目录草稿/预览/生命周期、筛选分页及 CSV 下载/预览/提交的公开 HTTP 契约和权限失败映射。
- `test_admin_user_management_api.py`：账号/角色最小投影、角色变更输入门和冲突映射的公开 HTTP 契约。

| 文件 | 职责 |
|---|---|
| `test_supply_chain.py` | 验证 Phase 2 新增依赖的版本化、fail-closed 供应链证据门 |
| `test_test_database_guards.py` | 证明测试数据库配置拒绝危险回退 |
| `test_runtime_foundation.py` | 验证版本化健康端点、Agent ledger/State、Graph→tool 边界、集中追问与 dirty-item 局部重算 |
| `test_weight_input.py` | 独立重量解析、受支持单位/精度/范围，以及纯文本与 JSON 补充输入使用同一换算合同 |
| `test_nutrition.py` | 用内存 fake repository 锁定受控营养查询、Decimal 计算和确定性校验动作 |
| `test_eval_dataset.py` | 验证 24 个 Phase 2 冻结语义案例、分类门与 append-only hash 链 |
| `test_phase2_eval_contract.py` | 验证机器评测证据拒绝静态期望冒充，以及发布失败夹具覆盖 |
| `test_nutrition_importer.py` | 验证离线 FDC manifest hash、资格边界与幂等 import 语义 |
| `test_agent_api_contract.py` | 锁定六个公开 Agent operation 的认证与统一 501 sentinel 合同 |
| `test_image_safety.py` | 锁定图片真实解码、metadata 剥离、私有临时存储与到期删除边界。 |
| `test_vision_provider.py` | 锁定 Vision DTO、Fake trace、失败类别与 test/production Provider 选择。 |
| `test_meal_record_api.py` | 餐食记录认证、三条写命令的安全 IANA 400、统计时区确认、OpenAPI 与安全 DTO 的 HTTP 契约。 |
| `test_dashboard_api.py` | Dashboard overview/history 的 HTTP 边界、服务端 current-window 与安全 precondition 契约。 |
| `test_weekly_review_api.py` | 周复盘公开 HTTP 的已结束周边界、闭合安全 outcome 与无技术字段契约。 |
| `test_memory_api.py` | 长期记忆认证、DTO 脱敏与跨用户访问 HTTP 契约。 |
| `test_agent_memory_context.py` | 安全上下文提示进入 Graph 但不改变确定性营养总计的契约。 |
| `test_safe_stream_stage_api.py` | 锁定版本化 SSE 阶段 DTO 的 allowlist 与敏感字段排除。 |
