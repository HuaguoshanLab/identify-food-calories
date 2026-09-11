# GitHub Automation

## 职责

`.github/` 保存仓库在 GitHub 上执行的自动化定义；它不保存环境文件、连接串、密钥或任何运行产物。

## 允许依赖

- GitHub Actions 公开 action、仓库内已提交的 Docker Compose、测试 wrapper 与 Python 项目定义。
- 工作流只能使用隔离的 `postgres-test` 和由 CI 临时目录保存的评测 release。

## 文件索引

| 路径 | 职责 |
|---|---|
| `workflows/` | GitHub Actions 工作流定义。 |
