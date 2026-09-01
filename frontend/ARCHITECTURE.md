# Frontend Architecture

## 目标

`frontend/` 是用户 H5 的独立 React SPA。目录按**稳定的技术边界**分层，再按**业务能力**拆分；不要按某个页面、迭代名称或临时接口堆文件。后端只通过公开 `/api/v1` 合约访问。

当前路径如下：

```text
main.tsx → Router / QueryClient / AuthProvider → App.tsx（路由组合）
                                               ├─ layouts/（H5 页面壳）
                                               ├─ auth/（认证能力）
                                               ├─ app/（非业务领域的登录后页面内容）
                                               └─ features/<capability>/（业务能力）
                                                    ├─ api/（DTO、校验、请求）
                                                    ├─ components/（页面与业务组件）
                                                    └─ stream/ 或 format.ts（该能力专属边界）
```

共享的 UI 基础组件只放在 `src/components/ui/`；全局样式 token 只放在 `src/styles.css`。这是 H5 项目，不存在 `pages/`、`services/`、`hooks/`、`utils/` 这类无边界的全局垃圾桶目录。

## 现有模块

| 位置 | 当前责任 | 后续代码放置规则 |
|---|---|---|
| `src/main.tsx` | React、Router、QueryClient、AuthProvider 装配 | 仅调整应用级 Provider 或启动失败处理；不写页面、请求和业务状态。 |
| `src/App.tsx` | 路由、guard、layout 与页面的组合 | 新增路由只在这里登记；页面实现不放这里。 |
| `src/routePaths.ts` | 可复用的静态 H5 路径合同 | 需要被导航、重定向或 guard 复用的静态路径放这里；动态参数路由不进入 `protectedRoutePaths`。 |
| `src/styles.css` | Tailwind 入口、设计 token、全局无障碍样式 | 只放全局规则；单个组件样式留在组件 class 中。 |
| `src/layouts/` | Mobile frame、唯一滚动区、四 Tab、详情与公开页壳 | 只管结构和导航，不请求 API、不读认证业务状态、不放餐食逻辑。 |
| `src/components/ui/` | 官方 shadcn/Base UI 原语 | 只接收无业务含义的原语；不发请求、不读上下文。 |
| `src/components/` | 跨 feature 复用的业务无关组合组件 | 两个以上模块真正复用后才放入；否则留在所属 feature。 |
| `src/auth/` | 登录、注册、会话、认证 API 与 guard | 所有认证专属页面、Zod 表单、会话交互与 `AuthenticatedRequest` 放这里。 |
| `src/app/` | “我的”等非独立业务领域的登录后内容 | 只组合已有公开能力；不新增餐食/计划/记忆 API。 |
| `src/features/agent/` | 餐食分析、OpenAPI 生成物、SSE | Agent 页面、流、生成合约都留在此处；不得保存 Graph State 或计算营养数值。 |
| `src/features/records/` | 已确认餐食记录 | 记录 DTO、请求、展示和编辑都留在此处。 |
| `src/features/memory/` | 长期偏好管理 | 记忆 DTO、请求、列表和编辑都留在此处。 |
| `src/features/plans/` | 未来饮食计划能力 | 当前 `PlaceholderTabPage` 仅是占位；开始实现计划时创建此 feature，不把计划代码继续塞入 `app/`。 |
| `tests/e2e/` | Playwright 真实浏览器跨栈路径 | 仅放跨栈、真实用户路径；组件与模块行为测试紧贴源码。 |

## 依赖规则

允许的主方向：

```text
App → layouts / auth / app / features
app → auth / components / layouts 的公开接口
features/<name>/components → 自己的 api、stream、format + auth + components/ui
features/<name>/api → auth 的 AuthenticatedRequest + Zod + 自己的 schemas
layouts → routePaths + components/ui
components/ui → React / Base UI / 样式工具
```

以下规则是硬约束：

1. `App.tsx` 只组合，不承载数据加载、mutation 或业务状态机。
2. 一个 feature 不得导入另一个 feature 的 `components/`、内部状态或私有类型。跨 feature 的业务动作只允许调用对方 `api/` 的显式导出，并要在两个 feature 的 README 写明原因。现有 `agent → records/api` 是“分析完成后确认保存”的唯一已登记例外。
3. 通用认证请求能力使用 `auth/AuthContext.ts` 的 `AuthenticatedRequest`；禁止再从任一 feature 借用 `ApiRequest` 类型。此前 `memory → records/api` 的错误依赖已移除。
4. API 响应必须在所属 `features/<name>/api/` 中以 Zod 或生成校验器验证。页面不得直接 `fetch`、定义后端 DTO，或把响应当可信数据。
5. TanStack Query 只管理服务端状态；组件本地 `useState` 仅管理瞬时 UI 状态。表单校验使用 React Hook Form + Zod，不能散落手写校验分支。
6. 生成文件只允许放在其生成目录，且禁止手改。当前仅 `features/agent/api/*.generated.ts` 属于此类。
7. 不新建全局 `utils/`、`services/`、`hooks/`、`types/`。代码先归属某个 feature；只有跨两个以上模块、无业务语义并且有明确所有者时，才创建受限共享目录和 README。

## 新代码落点

| 需求 | 正确位置 | 同步动作 |
|---|---|---|
| 新增一个业务 Tab/详情页 | `features/<feature>/components/` | 在 `App.tsx` 注册路由；必要时在 `routePaths.ts` 加静态路径；补同目录测试。 |
| 新增“我的”设置入口/静态账号展示 | `src/app/` | 路由与页面壳仍由 `App.tsx`、`layouts/` 管。 |
| 调用新公开 API | `features/<feature>/api/` | 写运行时 schema、错误边界和请求函数；页面通过该函数调用。 |
| 新增认证流程 | `src/auth/` | 使用既有 Provider/guard，不把 token 存进浏览器持久化存储。 |
| 新增 SSE/WebSocket/上传传输逻辑 | 所属 feature 的 `stream/` 或 `transport/` | 传输层只处理协议和取消；业务快照仍由 API schema 校验。 |
| 新增纯展示格式化 | 所属 feature 的 `format.ts` | 必须无网络、无 React；紧贴单元测试。 |
| 新增可复用视觉原语 | `components/ui/` | 必须来自官方 shadcn/Base UI，并更新该目录 README。 |
| 新增跨 feature 组合组件 | `components/` | 先证明至少两个调用方；否则不准提前抽象。 |

## 变更门禁

新增目录必须在同一次提交创建 `README.md`，说明职责、允许依赖和文件索引；添加、移动或删除文件时更新该目录及父目录索引。每次改动至少执行与范围匹配的测试；页面、表单、路由、上传或图表改动还必须走一次真实浏览器路径验收。完整命令见 `README.md`，H5 视觉约束见 `../docs/ui/h5-foundation.md`。
