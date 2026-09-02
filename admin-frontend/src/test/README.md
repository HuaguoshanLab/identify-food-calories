# 后台测试运行时

## 职责

此目录保存 Vitest、Testing Library 与 MSW 的共享测试初始化。功能测试必须留在各自 feature 附近；端到端测试属于根级 `tests/e2e/`。

## 允许依赖

- 允许依赖 Vitest、Testing Library、MSW 和已锁定的浏览器运行时依赖。
- 允许建立公开后台 HTTP 合约的 mock；不得伪造数据库状态、可读刷新凭据或后端授权结论。

## 文件索引

| 文件 | 职责 |
| --- | --- |
| `setup.ts` | DOM matcher、每例 DOM/MSW/mock 清理和网络 mock 生命周期。 |
