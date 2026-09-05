---
status: complete
verification: local-browser-passed-after-origin-config-fix
commit: 2dd5b69
---

# 后台刷新会话恢复

- 原因：AdminAuthProvider 初始 session 为空、没有 refresh，Guard 立即跳登录。
- 修复：启动进行 refresh → users/me，成功后只将 token/ID 放入内存；Guard 等待恢复并独立 probe 当前管理员权限。登录页面也等待恢复并跳回安全 returnTo。
- 请求 single-flight 兼容 StrictMode，同源 Web Locks 串行 Cookie 轮换；每个 HTTP 请求15秒超时、不自动重试。epoch 丢弃清空/显式登录之前发出的迟到恢复结果。
- 核实已有 AdminShell 服务端 logout 并保留，没有重复实现退出或削弱后端规则。
- 45项后台测试、TypeScript检查、生产构建通过；构建使用规定的 VITE_ADMIN_API_BASE_URL，约523KB chunk既有告警保留。
- 隔离 PostgreSQL Playwright 完整流程1项通过：真实登录后完整reload，refresh200 → users/me200 → probe200 → catalog200，仍停留目录；普通用户403；管理员logout204后reload的refresh401，仍停留登录页。
- 内置浏览器5179实际完整加载目录后返回登录页，当前未恢复出有效会话。已请用户重新登录，以便验证其本机有效会话的刷新；没有伪造token、读取Cookie内容或替用户登录，不能声称本机成功路径已通过。
- 仅修复初始化恢复；不增加业务API 401自动重试、不修改后端Cookie策略。不同端口共用Cookie、但不共用Web Locks是既有本地跨应用限制。
- gsd-quick 内联记录与提交；Phase7仍暂停。原debug未提交修改保持不动。

## 后续：本机来源配置遗漏已修复

- 用户反馈仍失败后，实际对5179代理的refresh发送无凭据诊断请求，得到 CSRF_ORIGIN_INVALID。检查本地配置及公开 .env.example，均仅包含5173/5178，没有5179。
- 前一轮认为需重新登录只是未证实的推测。真正阻断本机恢复的是来源检查；隔离E2E显式注入了测试后台来源，因此此前未发现此配置缺陷。
- 修改未提交的 backend/.env 和公开 backend/.env.example，追加 localhost/127.0.0.1 的5179来源；原来源保持，默认安全策略不放宽。增加配置字段说明，运行中的 uvicorn --reload 已重新加载。
- 同一诊断请求随后变为 REFRESH_TOKEN_INVALID（未携带Cookie的预期结果），证明来源检查已通过。
- 内置浏览器无需重新输入密码，从登录页完整加载目录成功；随后再次完整加载，仍是 /admin/catalog、真实表格存在、无登录表单。有效会话本机路径现已验证。
- 新增示例配置回归：5178/5179的localhost与127.0.0.1均可通过refresh来源校验，伪造相似域名仍403。refresh API测试7项通过；保留现有TestClient cookies弃用警告。
