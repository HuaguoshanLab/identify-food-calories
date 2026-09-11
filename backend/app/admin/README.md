# Admin Authorization Package

## 职责

`app/admin/` 提供管理员 RBAC probe、数据库权威角色检查、账号/固定角色只读投影、受审计的管理员晋升/降权、显式首管理员 CLI、管理员审计、营养目录草稿命令、发布后的受控 embedding job 聚合/批量重试、不可变向量空间 build/backfill、版本化关系证据及成品菜候选管理。它不包含后台页面、用户 H5 路由或前端权限判断。

## 允许依赖

- API 层只能处理 Bearer HTTP 语义，并调用认证与 admin Service。
- Service 只能通过 `AdminRepository` 读取用户、加锁和写入审计；它不依赖 FastAPI 或直接操作 Session。
- Repository 可以依赖 SQLAlchemy ORM；角色值以 `app.auth.models.UserRole` 为唯一枚举来源。

## 文件索引

| 路径 | 职责 |
|---|---|
| `__init__.py` | Python 包标识 |
| `models.py` | 角色提升、通用 append-only 审计、草稿/review/immutable publication、active pointer 与 eligibility history ORM 映射 |
| `schemas.py` | probe、账号/角色/角色变更、最小审计 timeline、严格运行配置/草稿/生命周期命令、embedding job 与向量空间 build 的安全运行时契约、版本化关系证据 |
| `ports.py` | Service 所需 flush-only 草稿、review/publication、受控名称/job、候选目录引用、pointer 与最新 eligibility 持久化能力协议 |
| `repository.py` | SQLAlchemy 查询、advisory lock、flush-only 审计、草稿/publication 生命周期、embedding job、向量 build 快照与候选目录资格 adapter |
| `service.py` | 数据库权威 RBAC、账号/角色查询、原子角色提升/降权、运行配置 optimistic version、命令审计、目录/候选生命周期及向量 build、publication-scoped embedding job retry 与 append-only 关系证据；不信任客户端 diff。 |
| `api.py` | `/api/v1/admin/probe`、`/users`、`/roles`、`/runtime-config`、`/audit`、草稿生命周期及候选 CSV/批量操作 HTTP 翻译 |
| `cli.py` | 显式管理员 bootstrap/promote 命令 |
| `catalog_csv.py` | UTF-8 CSV 模板、500 条/1 MB 导入校验、错误行号与防公式执行导出；无 HTTP/数据库依赖 |
| `recipe_csv.py` | 管理成品菜候选的中文 CSV 模板、500 条/1 MB 行级校验和防公式导出；无 HTTP/数据库依赖 |

## 向量空间构建

`POST /vector-space-builds` 只接受数据库重新确认的 `admin`。命令固定模型、1024 维度、adapter 和 retrieval 版本，要求原因、确认与 `Idempotency-Key`。Service 在 advisory lock 保护的单事务中冻结所有当前 eligible publication 的 canonical/controlled alias ID、publication/content version 清单，计算稳定 hash，创建唯一的空间/任务并写审计。安全响应只给出 identity、hash 和任务计数，绝不返回受控名称、向量或 provider 内容；同键重放不会扩大快照或重复入队。若复用空间已具备该新清单的所有完成 job/ready embedding，只会补写该清单自己的 completion evidence，不会调用 Provider 或切换 active pointer。

`activate.py` 必须同时提交目标 `vector_space_id` 和不可变 `build_id`。Service 重新读取管理员角色，复算 release 文件及源码 hash，逐项验证 build manifest、completion evidence、completed job 与 ready embedding；approval、审计和 active pointer 在一个锁定事务中提交。空间可复用时绝不按“最新”猜测 snapshot；任何 hash、身份、完成度或幂等参数不一致都 fail closed。

## 目录列表与 CSV

## 系统管理

`GET /users` 只返回账号 ID、邮箱、验证/启用状态、固定角色和时间戳，支持邮箱、状态、角色筛选及有界分页。`GET /roles` 返回固定 `user/admin` 的说明、权限范围与账号数量。`PATCH /users/{id}/role` 要求原因、确认和幂等键；禁止自改角色和撤销最后一个有效管理员。降权立即使后台 DB-RBAC 失败，但不撤销普通用户会话。首管理员 bootstrap 仍只能通过 CLI 完成。

`GET /catalog-drafts` 接受 `search`（名称或别名）、`source`、`authorization_status`、`page`、`page_size`，返回总数及创建时间/UUID 稳定排序分页。SQL 转义 LIKE 元字符，更新草稿不会改变创建顺序。

`GET /catalog-drafts/export` 使用同一筛选忽略分页，最多 10000 条，超限明确拒绝；`GET /catalog-drafts/template` 下载中文表头空模板。CSV 是带 BOM 的 UTF-8，按每 100g 计，多个别名以 `|` 分隔。

`POST /catalog-drafts/import-preview` 校验 `csv_text`；`POST /catalog-drafts/import` 要求同一内容、原因、`confirm: true` 和 `Idempotency-Key`。所有行通过才可创建，事务内逐行写草稿/版本/审计，任一失败整批回滚。批次键绑定管理员，advisory lock 串行同批请求，既有 append-only 草稿命令账本承担重试，不新增 schema。重试同一键与内容不会新增重复记录；重新选择文件视为新导入，不覆盖现有记录。所有读取、导出、模板、预览、导入均检查数据库管理员角色。

## 菜谱候选

`/recipe-candidates` 提供列表、模板、导出、CSV 预览/确认导入，以及 enable/disable/delete 批量命令。每条候选精确引用一个系统目录项或一个当前已合格的后台发布目录项；任何缺失、歧义、失格或停用目录名都会拒绝导入，绝不自动创建营养数据。候选不保存营养数值，规划时由 nutrition 域按关联目录和单份克数重算。删除为软删除，全部批量操作要求原因、幂等键并写 append-only 审计。
