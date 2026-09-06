# Frontend

## 职责

`frontend/` 是独立的 React + TypeScript + Vite 用户端 SPA。当前提供认证、餐食分析、显式保存的餐食记录、records dashboard、周复盘和长期偏好管理。后台是 Phase 6 的独立 `admin-frontend/` 项目，本用户 H5 不创建后台目录、路由或调用。

## 允许依赖

- React、React Router 与 TanStack Query 负责页面、路由和服务端状态。
- React Hook Form、Zod 与 `@hookform/resolvers` 负责客户端表单体验；FastAPI 始终是输入校验权威。
- Tailwind CSS、shadcn、Base UI 与 Lucide 是批准的 UI 工具。
- Vitest、Testing Library、MSW 与 Playwright 负责前端和跨栈测试。
- `promptfoo==0.122.0` 仅作为 Phase 2 已批准、lockfile 固定的发布评测 CLI；不得用于用户端运行时，也不得用临时 `npx` 下载替代。
- 禁止导入 backend 源码、数据库客户端、服务端密钥或 Next.js 运行时。

## 本地运行

```bash
npm ci
npm run dev
```

生产构建使用 `npm run build`。默认通过同源 `/api/v1` 反向代理访问 FastAPI；如部署在独立 API 域名，设置构建时 `VITE_API_BASE_URL=https://api.example.com/api/v1`。生产环境拒绝非 HTTPS 的绝对 API 地址，`VITE_API_BASE_URL` 留空时明确采用同源契约。本地 Vite dev/preview 的 `/api` 代理目标可由 `VITE_DEV_API_PROXY_TARGET` 覆盖，默认仅用于本机 `127.0.0.1:8000` 开发服务，不会进入浏览器 bundle。提交前执行完整前端门禁：

```bash
npm run lint
npm run typecheck
npm test
npm run build
npm run verify:production-bundle
```

records 页面位于 `/app/records`：overview、趋势、history 与周复盘仅使用后端确认的餐食快照和闭合安全状态。页面请求、严格 Zod DTO 与 tests 都归于 [`src/features/records/`](src/features/records/README.md)；它不计算营养、伪造目标，也不把模型/Provider 原文渲染到页面。

Vite 同时运行 React 与 Tailwind CSS v4 插件；Vitest 使用 jsdom 和 Testing Library 验证用户可见行为。

健康与认证 E2E 不要求手工启动服务：

```bash
npm run test:e2e
```

该命令覆盖认证与 Records 的隔离真实 E2E；Records 当前窗口、跨 IANA 冲突与零 dashboard-read 合约由 `frontend/tests/e2e/records-dashboard.spec.ts` 守护。已实测的公开页面路径、结果及浏览器与 Playwright 的分层证据见 [`../docs/verification/phase-06-browser-acceptance.md`](../docs/verification/phase-06-browser-acceptance.md)。

### Phase 6 前端调试

```bash
# records DTO、保存 IANA 时区、history cursor 与组件行为
npm test -- --run \
  src/features/records/api/client.test.ts \
  src/features/records/api/dashboard.test.ts \
  src/features/records/components/TodaySummaryCard.test.tsx \
  src/features/records/components/WeeklyTrend.test.tsx \
  src/features/records/components/WeeklyReview.test.tsx

# SSE 只映射本地 allowlist 安全文案
npm test -- --run src/features/agent/components/SafeProgressStages.test.tsx src/features/agent/stream/useAgentEventStream.test.ts
```

Promptfoo 的真实 Provider 评测需要 Phase 02-17 单独的人类费用授权；授权后只允许使用已有 lockfile 的 CLI：`npx --no-install promptfoo`。不能运行 `npx promptfoo` 或 `npx -y`，因为它们会绕过锁定版本并下载未知依赖。

Playwright 先从仓库根启动并等待隔离的 `postgres-test` 与 Mailpit，再从 `backend/` 通过 `.env.test.example` 和 `tests/run_pg.py` 启动唯一初始化器。初始化器只使用 guard 返回的测试 URL，固定执行安全 reset、迁移、Checkpointer setup、seed apply，再启动 FastAPI；`DATABASE_URL` 始终保留开发哨兵，`TEST_DATABASE_URL` 始终保留隔离库。认证用例从 Mailpit HTTP test API 读取刚发送的验证码，绝不伪造验证码、令牌或调用内部服务；应用进程由 Playwright 进程组清理，Docker 测试服务可被后续用例安全复用。

图片 E2E 使用真实登录、文件选择和公开 multipart API；页面只显示“估算重量”、partial 或安全恢复动作，不展示 Provider 原文、图片字节或内部图状态。冻结评测与一次真实浏览器验证的证据边界见 [`../docs/learning/phase-03-multimodal-meal-analysis.md`](../docs/learning/phase-03-multimodal-meal-analysis.md)。

## 文件索引

| 路径 | 职责 |
|---|---|
| `AGENTS.md` | 前端架构、安全、测试和文档细则 |
| `ARCHITECTURE.md` | 前端目录、依赖方向、新代码落点与跨 feature 例外的稳定性合同 |
| `package.json` | 固定命令与受审核依赖清单 |
| `package-lock.json` | npm 完整依赖锁与完整性摘要 |
| `eslint.config.js` | TypeScript、React Hooks 与 Vite 刷新边界静态检查 |
| `tsconfig.json` | 浏览器源码与测试共用的严格 TypeScript 配置 |
| `vite.config.ts` | React、Tailwind CSS 与 Vitest 的统一构建配置 |
| `index.html` | Vite HTML 入口 |
| `components.json` | shadcn 官方 Base UI registry、样式入口与路径 aliases |
| `playwright.config.ts` | 确定性的基础设施、FastAPI 与 Vite E2E 生命周期 |
| `playwright.config.test.ts` | Playwright provisioning 的真实 wrapper child 与配置安全合同 |
| `src/` | React 运行时代码与目录契约 |
| `tests/` | 前端测试边界与 Playwright E2E 用例 |

### 计划存档页面

计划 Tab 自动读取今日存档；历史与只读版本详情位于 `/app/plans/history`、`/app/plans/detail?id=…`。新用户先确认统计时区，生成成功后自动保存餐单；删除需要确认。存档读取使用 TanStack Query，不把健康数据持久化到浏览器存储。
