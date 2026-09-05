# 后台刷新保持会话

1. 后台启动通过 HttpOnly Cookie 调用 refresh，再验证 users/me，仅把令牌保存在内存。页面内合并恢复请求，同源 Web Locks 串行轮换，失败不自动重试。
2. Guard 等待恢复并对恢复后的 token 执行 probe，保持原路由；登录页面等待恢复。epoch 防止过时结果覆盖显式登录/清空。保留已有 Shell 服务端 logout。
3. 覆盖刷新成功、无凭据、403、慢响应/StrictMode、会话清空竞态。运行全量后台测试、构建、隔离 E2E 刷新及退出回归、真实内置浏览器刷新。
