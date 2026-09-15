# Backend Architecture

## 目标

`backend/` 是一个 FastAPI 模块化单体。代码按**业务能力**组织，而不是按 HTTP、数据库或“临时工具”建立全局垃圾桶。每个业务模块在自己的目录内保持 API、应用服务、持久化 Port/Adapter、ORM 和运行时 Schema 的物理边界。

```text
HTTP request
  → app/<domain>/api.py
  → app/<domain>/service.py
  → app/<domain>/ports.py
  → app/<domain>/repository.py
  → app/<domain>/models.py → PostgreSQL

Agent graph → agent/tools.py 的窄 Tool Port → Nutrition / Retrieval / Memory Service
Provider SDK → app/providers/<kind>/（DTO + Port + Factory + Adapter）
```

`app/main.py` 只负责应用工厂、路由注册、生命周期和运行时资源装配；它不是业务模块。`app/core/` 只放跨模块基础设施，绝不吸收业务规则。

## 当前模块与责任

| 位置 | 责任 | 新代码落点 |
|---|---|---|
| `app/main.py` | FastAPI 工厂、router 注册、Agent 生命周期装配 | 新模块 router 只在这里注册；不写业务逻辑。 |
| `app/core/` | Settings、数据库 Session/Engine、tracing | 无业务语义的运行基础设施；不放领域 DTO、Service 或模型。 |
| `app/auth/` | 注册、登录、会话、JWT、认证 Principal | 认证协议、Cookie、密码/Token 安全原语，以及所有受保护资源路由共用的 `AuthenticatedPrincipal`。 |
| `app/accounts/` | 密码恢复 | 账户恢复用例；邮件经 `notifications` Port，不复制 auth 登录代码。 |
| `app/admin/` | 后端 RBAC、审计、CLI 提升 | 管理员授权与审计；不放管理前端。 |
| `app/agent/` | 餐食分析 ledger、Graph State、工具、SSE、保留 worker | Graph、线程/运行账本和 Agent HTTP 合同；不把营养计算或 Provider SDK 写入这里。 |
| `app/nutrition/` | 受控目录、确定性查询/计算/校验 | 所有营养数值真相、目录版本与离线导入。 |
| `app/images/` | 图片安全解码和私有临时引用 | 唯一可接触原始图片 bytes 的模块。 |
| `app/providers/` | DeepSeek/Qwen 等外部模型 Port、DTO、Factory、Fake | 新模型或供应商适配器；不得导入业务 Service、ORM 或 FastAPI 路由。 |
| `app/records/` | 用户确认后的餐食快照 | 记录确认、读取、修改与删除；不是 Agent State。 |
| `app/memory/` | 长期偏好授权账本、outbox 与 Mem0 adapter | 偏好 CRUD、direct write 和删除/写入重试；外部 ID 不进入 HTTP DTO。 |
| `app/retrieval/` | 用户上下文检索 | tenant-filtered 的安全摘要与来源标签；不返回 embedding 或 score。 |
| `app/notifications/` | 邮件传输 Port 与 SMTP adapter | 新的通知通道适配器；不放认证或恢复业务规则。 |
| `migrations/` | Alembic schema 演进 | 每次持久化 schema 变更都在此新增 revision，禁止 `create_all()`。 |
| `scripts/` | 受保护的初始化和运维入口 | 只编排已有公开接口，不承载领域逻辑。 |
| `evals/` | 无真实用户数据的冻结 Agent 评测与发布证据 | 新评测数据、离线验证和授权 runner。 |
| `tests/` | 分层测试证据 | unit/service、integration/PostgreSQL、HTTP 合约分别归位。 |

## 依赖规则

默认允许方向：

```text
api.py → service.py → ports.py
repository.py → ports.py + models.py + SQLAlchemy
service.py → ports.py + schemas.py + security.py
models.py → SQLAlchemy + 共享 Base
graph.py → state.py + tools.py + Provider Port/DTO
tools.py → 已批准的领域 Service（不接触 Repository）
providers/* → core/config.py、自己的 DTO/Port、已验证图片引用
```

硬规则：

1. 业务 API 不得导入其他业务模块的 `api.py`。受保护资源路由统一使用 `auth.api.AuthenticatedPrincipal`；禁止再从 `agent.api` 借认证类型。
2. API 只翻译 HTTP、装配依赖和映射错误；禁止在路由中写 SQLAlchemy 查询、事务、领域判断或 LangGraph 调度。
3. Service 只能通过自己的 Port 访问持久化；Repository 只能 `flush`，事务提交/回滚由 Service 或 API 装配的边界拥有。
4. 跨模块协作必须使用窄 Service/Port/安全 DTO。仅共享 `Base`、角色枚举和已声明的外键/投影 ORM 类型时，才能直接导入其他模块的模型；原因必须写入双方 README。
5. Schema、ORM Model、Provider DTO 和 Graph State 禁止复用或互相导入。HTTP 输入输出在 `schemas.py`，供应商负载在 `providers/*/dto.py`，短期图状态在 `agent/state.py`。
6. Agent 图只经 `agent/tools.py` 调用确定性营养和安全上下文能力；不得访问 SQLAlchemy、Repository 或 Provider SDK。图片 bytes 只可在 `images/` 出现。
7. 不新建全局 `services/`、`repositories/`、`models/`、`utils/` 或 `schemas/` 目录。代码先归属一个业务模块；真正跨业务且无领域语义的能力才进入 `core/`，并须有明确所有者。

## 新代码落点

| 需求 | 应写位置 | 必须同步完成 |
|---|---|---|
| 新增某领域 HTTP endpoint | `app/<domain>/api.py` + `schemas.py` | 调用 Service；若为新 router，在 `main.py` 注册；写 HTTPX 合约测试。 |
| 新增业务用例或事务 | `app/<domain>/service.py` | 定义/扩展 Port，使用 fake repository 写 Service 单测。 |
| 新增表、列、索引、约束 | `<domain>/models.py` + `migrations/versions/` | 新增并审查 Alembic migration，补真实 PostgreSQL 集成测试。 |
| 新增 SQL 查询或持久化操作 | `app/<domain>/repository.py` | 先扩展 `ports.py`，必须 tenant-filter，Repository 不提交事务。 |
| 新增 API 输入/输出 | `app/<domain>/schemas.py` | Pydantic 运行时校验，禁止泄露摘要、Token、外部 ID、embedding 或 Provider 原文。 |
| 新增模型供应商 | `app/providers/<kind>/` | 分开 DTO、Port、Fake、Factory、Adapter；测试不能调用真实网络。 |
| 新增确定性营养能力 | `app/nutrition/service.py` + `schemas.py` | 通过 `agent/tools.py` 暴露给图，模型不能替代数值真相。 |
| 新增图节点或 State | `app/agent/graph.py` / `state.py` | 强制运行时校验、循环/工具/超时/成本终止条件和 Fake Provider 测试。 |
| 新增脚本或评测 | `scripts/` 或 `evals/` | 不能绕过数据库 guard，不能读取或写出密钥、原始用户数据。 |

## 变更门禁

新建业务模块根目录时增加说明职责和非显然边界的 README；常规子目录和普通文件增删不连锁维护索引。新增业务能力遵守 `API → Application/Service → Repository → Model`，并补范围匹配的单测、PostgreSQL 集成测试与公开 API 合约测试。完整命令和测试数据库隔离规则见 `README.md`。
