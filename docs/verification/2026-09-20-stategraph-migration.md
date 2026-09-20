# StateGraph 全量迁移验收记录

## 基线与外部协作

- 源码基线：`270b96a1b3f38f07bddd7b2bbde481429c80998e`
- 交付状态：仅本地隔离工作树修改；未提交、未推送、未创建 PR、未部署、未迁移任何非测试数据库。
- 提供给 ChatGPT Pro 的源码包：`identify-food-calories-stategraph-270b96a.zip`
  - 大小：`2,182,796` bytes
  - SHA-256：`948de82f4a00fa556ea6c4afb3b40b76cd0c8f11db9ccbab17f91b9c87416045`
  - 690 个 Git 跟踪文件；排除 `.git`、依赖、缓存、构建产物、数据库、运行状态、浏览器状态和全部 `.env*`。
  - 上传前凭据正则扫描通过；本机没有安装 gitleaks，因此没有声称执行 gitleaks。
- ChatGPT Pro 对话：<https://chatgpt.com/c/6aaf946b-8954-83ec-aca4-2ebb2e3f67cf>
- ChatGPT Pro 两次生成均因服务端连接中断，没有返回可下载补丁或源码包，因此不存在外部交付物 SHA-256。其方案不能作为代码交付使用。
- Codex 本地实现补丁：`/private/tmp/stategraph-migration.patch`
  - 大小：`84,391` bytes
  - SHA-256：`5809f9bf20f146ba2707995f6f5b46bb1b14bfc0eebac00813f1072e8dffbf33`

## 实际修改

- 餐食分析改为真实多节点 `StateGraph`：输入准备、显式偏好、个人上下文、视觉识别、文本解析、目录与营养计算、确定性校验、原生 interrupt、报告与终止。
- 饮食规划改为真实多节点 `StateGraph`：资料准入、目标计算、资料保存、候选组合、确定性校验、候选 interrupt、调整与完成。
- 周总结改为非持久化 `StateGraph`：事实校验、准入、Provider、语义校验、一次受控重试、完成或 abstain。
- 删除两套旧 `_advance()` 手写状态机以及 Service 的 `aget_tuple()`、`aput()`、`empty_checkpoint()` 手工 checkpoint 路径。
- FastAPI lifespan 打开一个 `AsyncPostgresSaver` 后分别编译餐食与规划图；Service 只通过图的 `ainvoke()` 和 `aget_state()` 工作。
- 等待态使用 `interrupt()`，恢复使用 `Command(resume=..., update={"state": ...})`；完成后的修正/调整使用同线程新运行记录。
- Checkpoint channel 只持久化 JSON-safe 字典，并在节点边界通过 Pydantic `model_validate()` 恢复类型。
- graph version 升级为 v2。没有使用非空顶层 `checkpoint_ns`，因为锁定的 LangGraph 1.2.11 会把它解释为子图路径，导致顶层 `aget_state()` 失败。
- 前端规划调整增加有限的权威快照轮询，修复异步 `202` 返回快于 StateGraph 完成时页面停留在旧版本的竞态。
- 餐食 E2E 对齐当前图片优先页面，需要先点击“改为文字描述这餐”。

## 拒收与返修

1. 第一版餐食和规划图虽然声明了多个节点，但所有阶段节点仍调用同一个旧 `_advance()`；第一次调用就完成整条流程。这是伪迁移，已拒收。
2. 返修后每个节点只执行自己的阶段，并删除旧 `_advance()` 死代码；新增结构测试防止退化为单节点或多节点空壳。
3. 真实 PostgreSQL 首轮发现 5 个失败：严格 serializer 重启后返回 dict、恢复路径、规划调整幂等、租户 checkpoint 数量假设。修复 JSON-safe channel、恢复命令更新和测试语义后，专项 30 项全部通过。
4. Playwright 发现规划调整后页面不刷新。原因是原计划的 SSE 已关闭，而调整沿用同一 thread id，不会重新挂载 stream；增加有限快照轮询后真实 E2E 通过。

## 验证结果

- 后端 Ruff 全量：通过。
- 后端 MyPy：基线 124 个既有错误；迁移后 120 个，迁移图和周总结文件无新增错误。项目全量 MyPy 仍未清零。
- 核心 StateGraph/餐食/规划/周总结单元与合同测试：134 passed，真实 PG 项在该轮按设计跳过。
- 真实 PostgreSQL 专项（checkpoint 重开、进程恢复、图片、规划、幂等、删除、租户隔离）：30 passed。
- 全量后端：首轮 968 passed、1 failed；唯一失败是隔离目录缺失本地 `promptfoo` 依赖源码。连接同一锁定依赖后该文件 15 passed，因此测试逻辑总计 983 项无失败；没有第二次完整单进程全量重跑。
- 用户前端：lint 0 errors、1 个既有 React Hook Form 编译器 warning；typecheck 通过；Vitest 191 passed；production build 通过。
- 管理端：typecheck 通过；Vitest 77 passed；production build 通过。管理端没有 lint script。
- 规划 Playwright：生成计划通过；调整、同线程新版本、刷新读取、历史版本与删除路径在修复后通过。
- 餐食 Playwright：页面入口问题已修正，但真实请求被现有运行时配置 admission 门禁在创建运行前以 503 拒绝；图未执行，因此不能表述为浏览器验收通过。餐食文字、追问恢复、图片调用与重启恢复已由真实 PostgreSQL 集成测试覆盖。
- 所有 Provider 验证均使用 Fake Provider；没有调用真实付费模型，不能推断真实模型质量、费用或生产效果。

## 残余风险

- 全量 MyPy 仍有 120 个既有错误。
- 餐食浏览器 E2E 需要测试初始化器提供有效的运行时 Provider 配置版本；本次未扩大范围去创建管理员运行时配置。
- 未执行真实模型、生产数据库、生产部署或旧运行中会话兼容验证。
- 没有执行整个 Playwright 套件；执行了与本次迁移直接相关的餐食和规划用例，其中餐食被上述 admission 门禁阻塞。
