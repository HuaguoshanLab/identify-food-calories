# Phase 5：饮食规划子图、个人资料与安全边界

本阶段把“计划”从占位页变成受控的一日三餐参考。它的目标不是让模型给出看似专业的营养处方；模型不产生任何营养数值真相，也不能直接读数据库。用户先复核资料和已有偏好，确定性服务计算目标区间，再由受控菜谱组合、重算和校验三餐。

所有结果都是普通饮食参考，不替代医疗建议。涉及未成年人、孕期或哺乳期、疾病或用药、进食障碍或自伤、极端体重控制时，系统只给出固定的拒绝和求助建议，不会生成目标、餐卡或继续生成入口。

## 一、页面、API 与领域层如何串起来

计划页是 `frontend/src/features/plans/components/PlanPage.tsx`。它只调用公开的 `/api/v1` 接口：

1. `GET /planning/profile` 读取已明确保存的最小身体资料；404 就显示首次复核表单，绝不猜测资料。
2. `GET /memories` 只读出既有的忌口和口味摘要。编辑偏好仍只能去“我的 → 饮食偏好与记忆”，计划页没有第二个 preference writer。
3. `POST /agent/threads/diet-planning` 提交完整 `profile`、确认过的偏好和显式 `save_profile`。这个布尔值是用户意图，不是前端偷偷写资料的开关。
4. 在同一 owned thread 上，`POST /agent/threads/{thread_id}/input` 只提交调整描述或闭合三餐选择；随后读取安全 snapshot。浏览器从不接触 checkpoint、ledger、候选菜谱 ID 或工具返回值。

后端仍保持 `API → Service → Repository → Model`：`backend/app/planning/api.py` 只做 HTTP 映射；`PlanningService` 负责目标、recipe qualification 和验证；Repository 只按 `user_id` 读写 PostgreSQL；ORM 与 Pydantic DTO 不混用。`backend/app/agent/graph.py` 的 `DietPlanningGraph` 只经 `PlanningToolAdapter` 调用领域服务，不能导入 Repository、ORM 或 MemoryService。

## 二、确定性目标与受控三餐

`backend/app/planning/service.py` 使用 `Decimal` 执行版本化 `target-policy.v1`：Mifflin–St Jeor 公式、五档活动因子、保守速度预设、能量区间和 4/4/9 的宏量范围都在服务内计算。UI 显示“目标区间 + 计划值 + 偏低/适中/偏高”，而不是伪装成医疗精度的单点数字。

受控菜谱不是存好的热量总计。`controlled_recipes` 只保存项目自有、审核过、固定许可、固定克数和合格目录引用的最小材料；每次组合会通过营养目录重新计算。公开餐卡只得到标准菜名、受控份量、简短做法/口味标签、命中的用户约束和营养小计。来源、许可、候选排序、完整做法和购物清单不会越过 API。

## 三、图状态、恢复与幂等

规划图有独立、版本化的 `DietPlanningState` 和 checkpoint namespace，不能与餐食分析图互相反序列化。每个 run 受线程所有权、幂等 command key、工具调用预算、超时及最大三次重排约束。

- 首次生成必须有完整资料和已确认偏好；缺失数据只进入 `needs_input`。
- 明确的“午餐换清淡一些”只替换午餐，早餐和晚餐保持原安全 snapshot。
- 歧义反馈只返回 `breakfast`、`lunch`、`dinner` 三个选项；非法 resume 是 no-op。
- 显式反馈经 typed memory tool 写入 Phase 4 白名单 ledger。图 state 只留下重放标记，不保存原始反馈、ledger ID、provider 输出或思维链。
- 只能放宽能量或宏量目标；忌口、明确排除和健康安全规则绝不放宽。放宽时报告原范围、计划值、偏离与安全理由。
- 达到第三次自动调整后，第四次请求不会再组合餐单，而是返回 `LIMIT_REACHED`。

这也是为什么 resume 不能简单“重新跑一次图”：它必须从权威 checkpoint 接着执行，并用 command hash 和 replay marker 防止重复写 profile、重复记忆或重复计算。

## 四、个人资料删除与 Phase 4 记忆权威性

`planning_profiles` 只保存后续生成和调整所需的身体/目标字段及版本号。忌口、口味、原始反馈、模型数据和医疗叙述都不进这个表。`GET/PUT/PATCH/DELETE /planning/profile` 全部从认证 principal 取得 owner；不存在、他人或软删除资料统一为 404，避免资料存在性泄露。

“我的 → 个人资料”只查看、编辑和删除身体资料与目标。删除使用确认对话框，清空 planning 查询缓存；后续计划 prefill 不会重新读取已删除资料。空态提供“去计划页填写”，保证首次资料采集只有计划页这一条路径。Phase 4 的长期偏好仍由 memory ledger 权威管理：删除 profile 不删除偏好，删除 memory 后也不能被规划召回。

## 五、安全 SSE、拒绝与 UI 投影

SSE 和 terminal snapshot 只能传稳定业务阶段：读取上下文、计算目标、组合餐单、校验、完成、需要补充。前端将事件类型映射为固定中文文案，严格 Zod DTO 不接受未知或内部字段。

因此页面不会展示 provider/model 名称、prompt 片段、工具结果、原始反馈、thread/ledger ID、成本、token 或完整思维链。高风险拒绝使用获取焦点的 `role="alert"`，没有餐卡、调整框或“继续生成”绕过按钮；每份计划页头和页尾都持续显示非医疗免责声明。

## 六、测试证据与运行方式

服务和图的回归：

```bash
cd backend
uv run pytest tests/planning/test_planning_service.py \
  tests/unit/test_diet_planning_graph.py \
  tests/integration/test_planning_profile_api.py \
  tests/integration/test_diet_planning_agent_api.py -q
```

这些测试分别使用 fake repository/service、Fake PlanningToolAdapter、真实 PostgreSQL/HTTPX 和公开认证链，验证五档活动、速度拒绝、受控菜谱重算、三次终止、owner isolation、删除后零读取、显式反馈幂等和安全字段投影。

H5 组件与端到端回归：

```bash
cd frontend
npm run typecheck
npm run lint
npm test -- --run src/features/plans/components/PlanPage.test.tsx \
  src/features/plans/components/PersonalProfilePage.test.tsx
E2E_BACKEND_PORT=8001 E2E_FRONTEND_PORT=5179 \
  npm exec playwright test tests/e2e/plans.spec.ts tests/e2e/profile.spec.ts
```

最后一条命令让 Playwright 自己拥有 8001/5179，避免复用未知的 8000/5178 进程；它仍经注册页面、Mailpit 公共测试 HTTP、验证、登录 cookie 和公开 API 创建合成测试用户。E2E 覆盖三餐生成、局部替换、资料保存/删除、320/375/430/768 宽度无横向溢出和删除后回到计划入口。

## 七、常见错误

- 在 graph 里直接查询 ORM 或把模型文本当营养真相：这会绕过确定性校验和架构边界。
- 将“调整”实现成整日重组：这会破坏未受影响餐次不变的合同。
- 把 raw feedback、provider/tool 数据或 ID 放进 SSE、snapshot、截图或教学文档：这是敏感健康数据与内部信息泄露。
- 把 profile 删除当作 memory 删除，或反过来：两个权威存储的删除链不同，不能互相代替。
- 为了跑 E2E 复用、停止未知本地服务，或伪造 token/direct SQL：这会破坏隔离与真实用户路径证据。
- 将拒绝态当普通字段错误继续渲染餐卡：这等于给高风险请求留绕过路径。

## 八、校验链修复：为什么 recipe 版本也必须是安全边界

最初的受控菜谱虽逐食材重算营养，但校验入口没有收到三餐结果。这是空心检查：图调用了 `validate`，却无法证明一天的总量、宏量比例或 recipe 去重。修复后的链路是 `DietPlanningGraph → PlanningToolAdapter → PlanningService.validate_plan()`；Service 仅用 Decimal 汇总实际 `PlannedMeal` 后才决定 `PASS`、`REPLAN` 或可解释的 `RELAX`。

`RELAX` 不是绕过。总能量低于 1200 kcal、已确认忌口、重复 recipe、缺少任一餐次或宏量比例越界绝不放宽。只有达到安全地板却未达到当前能量/宏量目标时，图才在预算内结束，并公开 `original_range`、`plan_value` 和 `deviation`。

菜谱数据同样不能原地覆盖：`controlled-recipes.v1` 保留为不可变审计历史，`controlled-recipes.v2` 是当前唯一运行时选中版本。0012 停用 v1；离线 importer 只激活 v2，并在同一事务中停用旧版本。repository 按 `recipe_version` 查询，因此遗留 v1 也不会再次进入用户餐单。bootstrap 先幂等导入 v1，再导入 v2；不会访问或改写 `planning_profiles`。
