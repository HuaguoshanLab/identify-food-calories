# Backend

## 职责

`backend/` 是 Python 3.11+ FastAPI 模块化单体，负责 HTTP API、应用服务、持久化、安全边界以及后续 Agent 编排。它不包含 React 页面，也不允许模型编排层绕过领域服务直接访问数据库。

## 允许依赖

- FastAPI、Pydantic Settings、SQLAlchemy 2、Alembic、Psycopg 3。
- PostgreSQL/pgvector 是权威持久化与后续语义检索基础；测试禁止回退到 SQLite。
- 邮件通过可替换 Provider 发送，本地只连接 Mailpit，不需要云凭据。
- 依赖方向固定为 API → Application/Service → Repository → Model。

## 本地运行

```bash
cp .env.example .env
python3.11 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/uvicorn app.main:app --reload
```

健康检查位于 `GET /api/v1/health`。从仓库根目录启动数据库和 Mailpit：

```bash
docker compose up -d --wait postgres postgres-test mailpit
```

测试必须显式使用 `APP_ENV=test` 和独立的 `TEST_DATABASE_URL`；配置保护会拒绝 SQLite、开发库以及不以 `_test` 结尾的测试库。

## 文件索引

| 路径 | 职责 |
|---|---|
| `AGENTS.md` | 后端局部实现与测试约束 |
| `.env.example` | 可提交的环境变量契约，不包含真实密钥 |
| `pyproject.toml` | Python 包、运行依赖与测试配置 |
| `app/` | FastAPI 应用代码 |
| `migrations/` | Alembic schema 变更脚本目录 |
| `tests/` | 单元、集成和 API 合约测试 |
