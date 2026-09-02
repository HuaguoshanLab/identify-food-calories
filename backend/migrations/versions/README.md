# Migration Versions

## 职责

`migrations/versions/` 保存按 revision 排序、可审查且可往返的 PostgreSQL schema 变更。这里的脚本是生产 schema 的唯一创建入口。

## 允许依赖

- Alembic operations 与 SQLAlchemy schema primitives。
- PostgreSQL 支持的约束、外键和索引；禁止运行 ORM `create_all()`。
- downgrade 只能反向本 revision 的对象，不得删除无关数据结构。

## 文件索引

| 文件 | 职责 |
|---|---|
| `0001_auth_foundation.py` | 用户、验证码、会话与 refresh token 权威 schema |
| `0002_login_attempts.py` | HMAC-only 登录失败 bucket、窗口与封禁 schema |
| `0003_admin_audit.py` | 管理员角色提升与不可省略审计证据 schema |
| `0004_agent_core.py` | 无业务 seed 的 Agent ledger、删除意图与版本化 nutrition catalog schema |
| `0005_nutrition_catalog_content_hash.py` | 为 immutable nutrition catalog version 持久化 content hash，拒绝同版本覆盖 |
| `0006_multimodal_images.py` | 图片最小生命周期与视觉调用 metadata；只存私有 handle 和安全计量，不存原图或模型原文。 |
| `0007_meal_records_memory_ledger.py` | 用户确认的餐食营养快照、偏好记忆本地授权账本与外部删除 outbox schema。 |
| `0008_retrieval_vectors.py` | pgvector 历史餐食与受控营养知识 embedding metadata；个人查询先以关系型 tenant/status 过滤。 |
| `0009_direct_memory_provisioning.py` | 直接偏好写入的可审计 provisioning 状态与幂等 request key。 |
| `0010_planning_profiles.py` | 最小化的用户身体资料/目标、active-row partial unique index 与软删除 schema。 |
| `0011_controlled_recipes.py` | 受审核 project-authored 菜谱、固定克数食材引用与 catalog FK schema。 |
| `0012_activate_controlled_recipes_v2.py` | 停用未达标的 v1 受控菜谱候选，保留不可变审计历史。 |
| `0013_dashboard_time_attribution.py` | 用户确认统计时区、餐食本地日冻结与历史回填审计 schema。 |
| `0014_planning_completion_projection.py` | 可撤销的 validated planning completion 投影、跨用户复合外键与 profile revision schema。 |
