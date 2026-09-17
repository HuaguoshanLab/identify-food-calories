# 后端运行日志与请求关联

日志是程序执行时留下的排错记录，不是餐食业务存储，也不是管理员审计。本功能统一记录安全指标，让接口、Agent、工具与模型调用可以按编号查找。

## 核心能力

每次请求生成 UUID，通过 `X-Request-ID` 返回。Agent 每次执行另生成随机 `execution_id`；请求内的同步函数、异步函数和线程调用共享上下文。日志支持易读文本和 JSON，记录时间、事件、状态、耗时与受控指标。

## 业务背景

例如一次图片分析失败，先从浏览器网络面板取得请求编号，再在后端终端搜索同一编号。这样能区分接口异常、工具失败和模型失败，不必打印原图或用户原文。模型负责理解，营养工具负责计算，Checkpoint 管短期状态，PostgreSQL 保存权威业务数据；日志不会替代这些职责。

## 整体执行流程

```text
实际页面发起请求 → 中间件生成 request_id → API → Agent 执行编号
  → 图/工具/Provider → 安全日志格式化 → 标准输出
  → 响应头与已有错误响应返回同一 request_id
```

SSE 是持续发送事件的连接，中间件直接转发每块数据，不攒成完整响应。连接结束时记录总耗时并清理上下文。

## 关键代码

- [统一日志与中间件](../../backend/app/core/logging.py)：`configure_logging` 管理输出，`SafeFormatter` 丢弃非结构化消息和异常原文，`RequestLoggingMiddleware` 管理请求编号与耗时。
- [启动入口](../../backend/app/core/run.py)：`main` 关闭原始访问日志，避免实际 URL 和异常原文绕过安全格式化。
- [Agent API](../../backend/app/agent/api.py)：`_execute` 的 `observed` 装饰器建立本次执行编号；[工具适配器](../../backend/app/agent/tools.py) 用相同装饰器记录调用边界，不输出参数。

简短主逻辑（删减了日志与异常处理）：

```python
token = request_id.set(identifier)
try:
    await self.app(scope, receive, forward)
finally:
    request_id.reset(token)
```

## 难懂语法

`ContextVar` 是并发上下文变量，不是全局共享字典；不同请求各有值。`set` 返回旧上下文的 token，`reset` 恢复它，避免后续请求继承编号。`asyncio.to_thread` 会复制当前上下文；普通自行创建的线程不保证这一点。

`@observed` 是装饰器：给函数外面加开始、结束和失败记录，不改变业务参数或返回值。`finally` 保证正常返回、报错或取消时都能清理编号。纯 ASGI 中间件直接操作响应消息，因此不需要读取或缓冲正文。

## 验证方法与边界

在 `backend/` 执行 `uv run pytest tests/unit/test_operational_logging.py tests/planning/test_search_diagnostics.py -q`，检查配置、编号、并发线程、响应头、错误、SSE 顺序及敏感异常不输出；Provider 与 Agent 的既有 Fake 测试用于业务回归。实际执行结果见本次交付，不把测试方法写成已通过证据。

常见错误：直接启动原始 Uvicorn 配置、把请求正文放进日志、用运行日志替代数据库审计、把 SSE 连接耗时当成单次模型耗时。当前不自动留存文件，不具备集中搜索或跨重启关联；输出失败可能丢日志。查询和配置完整说明见[后端 README](../../backend/README.md#运行日志与查询)。
