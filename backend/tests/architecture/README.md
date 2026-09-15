# Architecture Tests

## 职责

`tests/architecture/` 把稳定的应用/业务模块 README 边界和代码依赖规则变成自动化合同。它不再要求每个机械子目录创建 README，也不校验易漂移的逐目录父级索引。

## 允许依赖

- pytest、`pathlib`、`subprocess` 和 Git 已跟踪文件清单。
- 仅检查提交的源文件与文档；忽略 `node_modules`、虚拟环境、缓存、构建输出和 Playwright 产物。
- 禁止扫描或输出环境文件、密钥、邮件内容、令牌和数据库数据。

## 文件索引

| 文件 | 职责 |
|---|---|
| `test_directory_contract.py` | 顶级应用和业务模块根目录的 README 边界合同 |
