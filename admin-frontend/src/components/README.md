# 管理后台共享组件

## 职责

`components/` 只保存已证明被两个或以上后台 feature 复用的展示组合组件，以及官方 shadcn/Base UI 原语目录。尚未证明复用的组件必须留在所属 `features/<capability>/components/`，不得创建无所有者的通用组件垃圾桶。

## 允许依赖

- 可依赖 React、已锁定的 Base UI、样式工具和同级纯展示组件。
- 共享组合组件可依赖 `ui/` 中的官方原语。
- 禁止直接请求 `/api/v1/admin/*`、读取认证上下文作为授权真相、导入 feature 私有类型/状态、用户 H5、后端源码、数据库或密钥。

## 文件索引

| 路径 | 职责 |
| --- | --- |
| `README.md` | 共享组件职责、允许依赖与文件索引。 |
| `ui/` | 仅官方 shadcn/Base UI registry 原语；目录索引见 `ui/README.md`。 |

新的跨 feature 组件必须在这里登记；若依赖边界变化，同时更新本 README、`ui/README.md`（如适用）和 `src/README.md`。
