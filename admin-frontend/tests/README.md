# 管理后台测试

## 职责

`tests/` 保存独立后台的浏览器级跨栈验收。它补充 `src/test/` 的 Vitest、Testing Library 和 MSW 组件测试，不替代后端的 RBAC、审计或数据库集成测试。

## 允许依赖

- 可依赖 Playwright、独立后台运行命令、公开 FastAPI `/api/v1/admin/*` API 与隔离测试基础设施。
- 测试必须从真实产品页面发起，使用公开认证和 API 路径验证可观察行为。
- 禁止直写数据库、伪造 token、调用内部函数、访问开发数据库、真实模型/云服务、后端私有模块或密钥。

## 文件索引

| 路径 | 职责 |
| --- | --- |
| `README.md` | 浏览器测试职责、允许依赖与文件索引。 |
| `e2e/` | Playwright 真实页面与公开 API 的跨栈路径；`admin-management.spec.ts` 在受保护空库中验证 bootstrap→probe→RuntimeConfig→目录治理及普通用户 403，目录索引见 `e2e/README.md`。 |

新增浏览器测试目录或共享 fixture 时，必须在此登记，并同步更新根 `admin-frontend/README.md`。
