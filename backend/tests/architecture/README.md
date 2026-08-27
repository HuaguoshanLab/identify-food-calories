# Architecture Tests

## 职责

`tests/architecture/` 把仓库目录、README 索引和依赖边界变成自动化合同，防止新增模块后文档与代码悄悄分叉。

## 允许依赖

- pytest、`pathlib`、`subprocess` 和 Git 已跟踪文件清单。
- 仅检查提交的源文件与文档；忽略 `node_modules`、虚拟环境、缓存、构建输出和 Playwright 产物。
- 禁止扫描或输出环境文件、密钥、邮件内容、令牌和数据库数据。

## 文件索引

| 文件 | 职责 |
|---|---|
| `test_directory_contract.py` | README 三节与父级索引的仓库级合同 |
