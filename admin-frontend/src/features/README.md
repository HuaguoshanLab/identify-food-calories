# 管理后台功能模块

## 职责

`features/` 按后台业务能力隔离 API 合约、TanStack Query、页面、表单、格式化和局部组件。每个能力拥有自己的 `api/` 边界；响应必须在 API 层经过 Zod 运行时校验，组件不能直接 `fetch` 或把服务端响应当作可信数据。

## 允许依赖

- `features/<capability>/components` 可依赖本能力的 `api/`、格式化代码、`auth/` 的公开接口和 `components/ui/`。
- `features/<capability>/api` 可依赖认证请求接口、Zod 及公开 `/api/v1/admin/*` HTTP 合约。
- feature 默认相互隔离；禁止导入其他 feature 的组件、内部状态或私有类型，除非先建立明确所有者的公开边界并更新双方 README。
- 禁止导入用户 H5、后端源码、数据库、Provider SDK、密钥，或在 feature 外建立全局 `services/`、`hooks/`、`utils/`、`types/`、`pages/` 目录。

## 文件索引

| 路径 | 职责 |
| --- | --- |
| `README.md` | 功能模块职责、允许依赖与文件索引。 |
| `catalog/` | 目录草稿的严格 API、表单、确认与受限字段展示；目录索引见 `catalog/README.md`。 |
| `audit/` | 后端白名单审计证据的只读语义时间线；目录索引见 `audit/README.md`。 |
| `config/` | 未来 Agent 调用的非密钥运行配置审阅与确认；目录索引见 `config/README.md`。 |

后续每个 capability 目录首次创建时，必须同次加入本级 README，并在此表登记其职责和公开依赖边界。
