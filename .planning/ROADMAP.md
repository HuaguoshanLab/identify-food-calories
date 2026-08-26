# Roadmap: 中式外卖热量识别

## Overview

路线图以垂直 MVP 推进：先交付一个由 React/Vite 前端、FastAPI REST API 和 PostgreSQL 受控目录共同工作的可运行薄切片，再接入安全图片处理与多菜识别，随后完成用户修正和匿名可追溯闭环，最后用冻结评测集与生产门禁决定是否发布。FastAPI、SQLAlchemy 2、Alembic 和 PostgreSQL 的学习目标直接服务于真实 API、关系建模、迁移与结果持久化；首版保持一个前端、一个后端和一个数据库，不引入微服务、消息队列或长期原图存储。

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: 受控数据与可运行薄切片** - 用正式前后端和 PostgreSQL 打通受控菜品热量计算的最小端到端路径。
- [ ] **Phase 2: 安全图片识别闭环** - 用户可安全上传一张外卖图并得到多菜、克数及热量区间结果。
- [ ] **Phase 3: 可修正与可复现分析** - 用户可即时修正结果，系统保存匿名结构化分析与完整版本身份。
- [ ] **Phase 4: 识别与区间质量校准** - 冻结评测证明菜名、候选、估重和热量区间达到量化门槛。
- [ ] **Phase 5: 生产保护与发布门禁** - 在真实移动条件、攻击与费用约束下完成发布候选验收。

## Phase Details

### Phase 1: 受控数据与可运行薄切片
**Goal**: 开发者可以运行正式技术栈，用户请求可穿过 React/Vite、FastAPI 和 PostgreSQL，由合法受控数据确定性计算热量。
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: ARCH-01, ARCH-02, ARCH-03, ARCH-04, ARCH-05, ARCH-06, DATA-01, DATA-04, CAL-01
**Success Criteria** (what must be TRUE):
  1. 开发者可用 Docker Compose 启动 PostgreSQL，并分别启动 `frontend/` React + TypeScript + Vite 与 `backend/` FastAPI 项目；前端能通过版本化 REST/OpenAPI 契约完成一次真实请求。
  2. 开发者可用 SQLAlchemy 2 模型和 Alembic 迁移从空库重建菜品、别名、标准配方、营养数据及版本关系，并能查询约 100 道菜的稳定 `dishId`。
  3. 系统只使用带来源、授权记录和可追溯推导链的受控营养数据；缺少明确商用权的数据会阻止公开发布。
  4. 给定受支持菜品和克数时，后端从数据库中的受控营养数据确定性计算热量，并拒绝采用视觉模型自由生成的热量值。
**Plans**: TBD
**UI hint**: yes

### Phase 2: 安全图片识别闭环
**Goal**: 免登录用户可以在移动端安全提交一张中式外卖图，并在清晰的状态反馈后得到可解释的多菜热量估算。
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: IMG-01, IMG-02, IMG-03, REC-01, REC-02, REC-03, REC-04, REC-05, CAL-02, CAL-03, CAL-04, FLOW-01, FLOW-02, FLOW-03, SAFE-01, SAFE-02, SAFE-03
**Success Criteria** (what must be TRUE):
  1. 用户无需登录即可拍照或上传图片，并在提交前看到第三方处理、留存和删除说明；格式、大小、像素、解码、画质或非食物检查失败时会得到可操作的重拍提示。
  2. 一张有效套餐图会返回多个可见菜品；每项归一化为约 100 道目录中的具体菜名并显示克数，低置信度项提供 2–3 个候选，目录外项目明确标为不支持或无法确认。
  3. 用户能同时看到每项与整餐的中心热量和合理范围，并能看懂配方、用油、糖、酱汁和实际份量为何会造成误差。
  4. 用户能辨认图片准备、上传、分析和完成状态；超时、限流、服务错误或模型输出异常均提供明确恢复操作，重复点击、重试或网络抖动不会重复分析或重复计费。
  5. 系统会拒绝伪造格式、解码炸弹、超大像素等危险图片，剥离图片元数据，并在当次分析结束后删除原图而不长期保存。
**Plans**: TBD
**UI hint**: yes

### Phase 3: 可修正与可复现分析
**Goal**: 用户可以不重新调用视觉模型就修正餐食结果，系统能用匿名结构化数据复现分析并记录修正信号。
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: EDIT-01, EDIT-02, EDIT-03, EDIT-04, DATA-02, DATA-03
**Success Criteria** (what must be TRUE):
  1. 用户可以精确修改任一菜品克数，单项和整餐热量会立即重算且不再次调用视觉模型。
  2. 用户可以从候选中切换菜名、搜索替换为受支持菜品或删除误识别项，所有受影响的中心值和范围会立即更新。
  3. 系统为每次匿名分析保存结构化结果、模型运行元数据和用户修正，但不保存原图；运维人员可按模型、提示词、预处理、目录、营养和计算规则版本复现当时结果。
**Plans**: TBD
**UI hint**: yes

### Phase 4: 识别与区间质量校准
**Goal**: 系统在独立冻结数据上证明菜名识别、候选召回、估重和整餐区间均达到公开发布所需质量。
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: QLT-01, QLT-02, QLT-03, QLT-04
**Success Criteria** (what must be TRUE):
  1. 冻结测试集报告显示目标菜品 Top-1 识别准确率不低于 85%，正确菜名进入前三候选的比例不低于 95%。
  2. 冻结测试集报告显示单项克数估算的中位相对误差不高于 25%。
  3. 冻结测试集报告显示真实整餐热量落入合理区间的比例不低于 80%，且区间宽度同时满足预先冻结的护栏，不能靠无限放宽区间达标。
  4. 同一冻结数据、版本快照和评测命令可重复得到一致指标，未达任一门槛时系统明确阻止发布。
**Plans**: TBD

### Phase 5: 生产保护与发布门禁
**Goal**: 发布候选在目标移动网络、真实交互、恶意输入和匿名费用风险下仍然快速、安全且可控。
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: SAFE-04, QLT-05, QLT-06, QLT-07
**Success Criteria** (what must be TRUE):
  1. 在目标移动网络环境和发布并发下，90% 的有效识别请求可在 10 秒内返回结果。
  2. 真机验收确认用户从上传图片到理解结果的主流程不超过 3 次操作。
  3. 匿名分析端点的限流、并发限制、费用硬上限和紧急熔断均可触发且有效，刷量或供应商异常不会产生无上限费用。
  4. 发布候选通过冻结测试集、移动端端到端、恶意图片、费用上限、原图删除链和隐私告知验证；任何失败都会给出明确的 no-go 结果。
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. 受控数据与可运行薄切片 | 0/TBD | Not started | - |
| 2. 安全图片识别闭环 | 0/TBD | Not started | - |
| 3. 可修正与可复现分析 | 0/TBD | Not started | - |
| 4. 识别与区间质量校准 | 0/TBD | Not started | - |
| 5. 生产保护与发布门禁 | 0/TBD | Not started | - |
