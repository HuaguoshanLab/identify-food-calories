# Phase 1: 受控数据与可运行薄切片 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-26
**Phase:** 1-受控数据与可运行薄切片
**Areas discussed:** 首个可运行流程、首批菜品数据、后端学习深度、本地启动体验

---

## 首个可运行流程

| Decision | Options considered | Selected |
|----------|--------------------|----------|
| 首条用户路径 | 单菜计算；手动组合多道菜 | 单菜计算 |
| 菜品选择 | 可搜索下拉框；普通下拉框 | 可搜索下拉框 |
| 克数初始值 | 默认常见份量；保持为空 | 默认常见份量并允许修改 |
| 来源展示 | 前端展示；仅 API/数据库保留 | 仅 API/数据库保留 |
| 触发计算 | 点击按钮；停止输入后自动请求 | 点击“计算热量”按钮 |

**User's choice:** 选择一道菜、输入或修改克数，点击按钮后查看热量。
**Notes:** 第一阶段不显示误差区间；数据来源不进入前端主界面。

---

## 首批菜品数据

| Decision | Options considered | Selected |
|----------|--------------------|----------|
| 数据扩充顺序 | 15 道代表菜起步；直接导入约 100 道 | 两步扩充 |
| 首批内容 | 建议的 15 道代表菜；用户替换 | 接受建议清单 |
| 配方数量 | 单一标准配方；多商家/少油配方 | 单一标准配方 |
| 未授权数据 | `demo_only` + 生产阻断；等待授权后再开发 | `demo_only` + 生产阻断 |

**User's choice:** 先验证 15 道，再在阶段结束前扩充到约 100 道。
**Notes:** 数据库预留未来多配方能力，但本阶段不实现；生产数据必须为 `production_approved`。

---

## 后端学习深度

| Decision | Options considered | Selected |
|----------|--------------------|----------|
| API 版本 | 从第一阶段使用 `/api/v1`；暂不版本化 | `/api/v1` |
| 后端边界 | 严格分层；允许简单接口跨层 | 严格分层 |
| 测试范围 | Service/Repository/API 三层；仅 API；SQLite 替代 | 三层测试，Repository 使用 PostgreSQL |
| 文档范围 | 实用 README、docs、curl、数据流图；仅自动文档；理论教程 | 实用文档范围 |

**User's choice:** 明确拆分 API、Service、Repository、Schema、Model，并配套测试和文档。
**Notes:** Pydantic Schema 与 SQLAlchemy Model 分离；API 不直接访问数据库。

---

## 本地启动体验

| Decision | Options considered | Selected |
|----------|--------------------|----------|
| Compose 内容 | 仅 PostgreSQL；同时包含 pgAdmin | 仅 PostgreSQL |
| 环境变量 | 前后端分离；根目录共享 | 前后端分离 |
| migration/seed | 独立命令；启动时自动执行 | 独立命令 |
| 端口和 CORS | 固定端口并限制来源；动态端口或 `*` | 5173/8000/5432，CORS 仅 5173 |

**User's choice:** 数据库使用 Docker，前端和后端分别启动。
**Notes:** DBeaver Community 只作为文档示例；前后端日志分开查看。

---

## the agent's Discretion

- 具体包路径、命名、依赖注入写法、字段与索引。
- UI 样式、热量取整和符合批准技术栈的开发工具细节。

## Deferred Ideas

None.
