# Phase 3 Plan 04 Summary

已在既有 `/app/analyze` 实现真实图片分析闭环：认证请求复用 `AuthProvider` 的刷新与重放机制，先创建图片线程，再以 multipart 上传；报告只由权威快照渲染，不从 SSE 拼接最终数值。

## 交付

- 首屏提供拍照、相册选择、格式/体积限制、临时处理说明，以及文字降级入口。
- 报告明确标记“估算重量”、partial 与非医疗说明；失败码只映射为安全恢复动作，不展示 Provider、图状态或模型原文。
- 新增图片线程 API、恢复码快照字段、测试环境确定性视觉 Provider 和对应 OpenAPI/生成客户端。
- E2E 使用真实注册登录、公共 Mailpit、隔离 PostgreSQL 和 file chooser；新增未晋升的 430px 视觉候选，不修改官方基线。

## 验证

- `npm run typecheck`
- `npm run test -- --run src/features/agent/components/AnalyzePage.test.tsx src/features/agent/stream/useAgentEventStream.test.ts`：10 通过。
- `npm run test:e2e -- --grep "multimodal image upload|phase 3 visual candidate" --reporter=list`：2 通过。
- 内置浏览器：`/register → /login → /app/analyze`，临时账号通过真实验证码激活；从相册选择无个人信息 PNG 后，页面显示米饭、估算重量 100g 和 130 kcal。相机权限未请求，原因是本次只验证相册路径。

## 说明

浏览器初验发现 4173 本地测试端口不在后端默认开发来源白名单中；仅为隔离验收进程设置了该来源后复验成功，未放宽任何提交的生产配置。构建仍有单文件超过 500 kB 的 Vite 警告，属于后续性能优化项，未影响本计划验收。
