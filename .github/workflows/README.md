# GitHub Workflows

## 职责

本目录保存可复现的 CI 门禁。工作流不得绕过 `tests/run_pg.py` 的测试库保护，也不得将冻结评测 release 上传、提交或写入长期存储。

## 文件索引

| 文件 | 职责 |
|---|---|
| `phase-063-frozen-retrieval.yml` | 在真实 pgvector PostgreSQL 上初始化、生成并校验 Phase 06.3 冻结 release，随后运行相关真实 PostgreSQL 集成测试。 |
