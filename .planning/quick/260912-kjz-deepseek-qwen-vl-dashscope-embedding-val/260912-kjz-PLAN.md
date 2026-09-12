---
quick_id: 260912-kjz
status: planned
description: 将后台模型配置改为完整、可理解的模型服务配置
must_haves:
  truths:
    - 管理员能区分文字理解、图片识别和菜品相似检索三类模型服务
    - 页面不把只读环境配置伪装成可编辑配置
    - 页面与接口不暴露密钥、端点或 Provider 原始内容
  artifacts:
    - backend/app/admin/schemas.py
    - backend/app/admin/api.py
    - admin-frontend/src/features/config/ConfigSummaryPage.tsx
    - admin-frontend/src/features/config/api/index.ts
  key_links:
    - 后台页面通过受 RBAC 保护的公开 API 读取服务端安全配置摘要
---

# Quick Task 260912-kjz

## Task 1：提供安全的模型服务概览接口

- **files:** `backend/app/admin/schemas.py`, `backend/app/admin/api.py`、对应测试
- **action:** 增加只读模型服务摘要，展示文字、视觉、向量服务的用途、状态、模型和限制；仅 DeepSeek 运行策略保持可编辑。
- **verify:** 后端单元/API 测试覆盖 RBAC、字段和值，不出现密钥和端点。
- **done:** 前端无需硬编码 Qwen/Embedding 的运行状态。

## Task 2：重构后台模型配置页面

- **files:** `admin-frontend/src/features/config/ConfigSummaryPage.tsx`, `admin-frontend/src/features/config/api/index.ts`, 导航与测试
- **action:** 将页面改成三张中文业务卡片，明确每类模型作用、配置来源和限制；修正文案与按钮命名。
- **verify:** Vitest、TypeScript 和 lint 通过相关范围。
- **done:** 普通管理员无需理解 Provider、alias、token 等内部术语也能判断各模型的用途和状态。

## Task 3：真实页面验证

- **files:** 无
- **action:** 启动现有应用，通过内置浏览器检查模型服务页面布局、内容和编辑弹窗。
- **verify:** 三类服务可见，DeepSeek 可编辑，Qwen/Embedding 明确只读，页面无敏感配置。
- **done:** 记录已验证路径和残余风险。
