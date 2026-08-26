# 中式外卖热量识别

## What This Is

一个移动端优先、免登录的网站，面向只想快速了解一餐热量的普通用户。用户拍照或上传一张中式外卖套餐图片后，系统分别识别其中的多种菜品，估算每项克数与热量，并展示整餐中心估值和合理区间；用户可以修正菜名、克数或删除误识别项。

首版聚焦约 100 道高频中式外卖菜，目标不是覆盖所有食物，而是把有限范围内的识别、估重和热量计算做得可信、可解释、可修正。

## Core Value

让普通用户在约 10 秒内得到一份可信且可修正的中式外卖整餐热量估算。

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] 用户无需登录即可拍照或上传一张外卖套餐图片。
- [ ] 系统可以分别识别一张图片中的多种菜品，并返回具体菜名。
- [ ] 首版重点支持约 100 道高频中式外卖菜。
- [ ] 系统为每项菜品估算克数、热量和合理误差范围。
- [ ] 系统展示整餐中心热量估值和合理区间。
- [ ] 用户可以切换候选菜名、修改克数或删除误识别项，并立即看到重算结果。
- [ ] 营养值来自受控菜品目录和营养数据库，而不是模型自由生成。
- [ ] 90% 的有效识别请求在 10 秒内返回。
- [ ] 产品达到已确认的菜名识别、估重和区间覆盖率验收指标。

### Out of Scope

- 用户账号、登录和跨设备同步 — 快速估算不需要身份体系。
- 历史饮食记录 — 首版只验证单次识别价值。
- 减脂计划和个性化营养建议 — 不属于快速了解一餐热量的核心目标。
- 社交、排行榜和内容社区 — 与核心识别能力无关。
- 全球食物或全部中餐覆盖 — 首版必须控制识别范围并保证质量。
- 医疗级或称重级精度承诺 — 单张照片无法可靠还原隐藏油脂、糖、酱汁和真实重量。

## Context

- 产品定位来自前期探索：目标用户不是专业健身或营养管理人群，而是临时想了解一餐热量的普通用户。
- 目标场景是中式外卖套餐。一张图片可能同时包含米饭、肉菜、蔬菜和配菜。
- 用户更希望看到具体菜名，如“鱼香肉丝”，而不是默认拆成原料列表。
- 同名菜的配方和用油量差异很大，因此结果必须注明“按常见做法估算”，并展示区间而非虚假的精确数字。
- 推荐链路为：图片 → 多模态模型结构化识别与估重 → 菜名归一化 → 标准菜谱/营养数据库 → 热量及区间计算。
- 通用多模态模型适合作为首版识别方案；是否采用垂直食品识别服务，应由真实测试集评测决定。
- 中国食物成分数据可作为主要候选数据源，USDA FoodData Central 可补充基础食材；商业使用前必须核实授权。
- 上线前需要自建包含真实菜名、称重结果和参考热量的中式外卖评测集。
- 项目同时承担后端学习目标，因此采用前后端分离，而不是以最少服务数量为唯一优化方向。
- 前端使用 React、TypeScript 和 Vite；后端使用 FastAPI、Python、SQLAlchemy 2、Alembic 和 PostgreSQL。
- 数据库保存匿名的结构化分析结果、模型运行元数据和用户修正，以支持评测与改进；原始图片不长期保存。

## Constraints

- **范围**：首版只重点支持约 100 道高频中式外卖菜 — 避免“什么都能识别但什么都不准”。
- **性能**：90% 的有效识别请求应在 10 秒内返回 — 核心价值是快速了解。
- **菜名准确率**：Top-1 ≥ 85%，Top-3 ≥ 95% — 低置信度时必须提供候选项。
- **估重准确率**：单项克数估算中位相对误差 ≤ 25% — 用户必须能手动改克数。
- **区间可信度**：真实总热量落入系统合理区间的比例 ≥ 80% — 区间需经过测试集校准。
- **交互**：用户从上传图片到理解结果不超过 3 次操作 — 移动端流程必须极轻。
- **数据可信度**：模型不得直接充当最终营养数据库 — 热量必须由受控数据计算。
- **隐私**：食物图片的存储期限和删除策略必须在上线前明确 — 默认倾向分析后尽快删除。
- **架构**：`frontend/` 与 `backend/` 为独立项目 — 用户希望通过项目学习 FastAPI、数据库建模、迁移和 API 设计。
- **持久化**：PostgreSQL 只保存必要的结构化结果和修正记录，不长期保存原图 — 在改进模型和保护隐私之间取平衡。

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 移动端优先且免登录 | 目标用户只需要快速完成一次估算 | — Pending |
| 聚焦中式外卖套餐 | 场景具体，常见菜和餐盒相对标准化 | — Pending |
| 首版覆盖约 100 道高频菜 | 有限范围更容易建立可靠数据和评测集 | — Pending |
| 输出具体菜名 | 比原料拆分更符合普通用户的理解方式 | — Pending |
| 展示中心估值和合理区间 | 单张图片无法支持称重级精度 | — Pending |
| 克数采用精确数值并允许编辑 | 用户需要可控、可实时重算的修正方式 | — Pending |
| 视觉模型与营养计算解耦 | 防止模型臆造热量，便于校准和审计 | — Pending |
| React + TypeScript + Vite 前端 | 核心流程是客户端交互；独立 FastAPI 已承担服务端职责，无需额外 SSR 层 | — Pending |
| FastAPI + Python 独立后端 | 适合 AI、图片处理、数据分析，也满足后端学习目标 | — Pending |
| PostgreSQL + SQLAlchemy 2 + Alembic | 学习关系建模和迁移，并持久化菜品、营养、匿名分析及修正数据 | — Pending |
| 保存匿名结构化结果但不长期保存原图 | 为评测和改进保留信号，同时降低隐私风险 | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `$gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `$gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-08-26 after initialization*
