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
