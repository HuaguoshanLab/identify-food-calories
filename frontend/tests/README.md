# Frontend Tests

## 职责

`tests/` 保存前端行为与跨栈验证。测试必须验证用户可观察行为，并自行建立所需运行环境，不能依赖开发者手工启动的后台进程。

## 允许依赖

- 可依赖 Playwright、Vitest、Testing Library 与 MSW。
- E2E 只能访问隔离测试数据库、本地 Mailpit 和公开 FastAPI API。
- 禁止真实模型、云服务、开发数据库和未受控时间等待。

## 文件索引

| 路径 | 职责 |
|---|---|
| `e2e/` | 浏览器级全栈生命周期测试 |
