# Phase 1: 工程、身份与权限基座 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-27
**Phase:** 01-工程、身份与权限基座
**Areas discussed:** 产品重构、模型分工、身份认证、后台管理、后端教学

---

## 产品重构

| Option | Description | Selected |
|---|---|---|
| 保留单步热量计算器 | 图片或表单一次请求返回热量 | |
| LangGraph 饮食健康 Agent | 规划、工具、循环、校验、追问和记忆 | ✓ |

**User's choice:** 放弃旧版，重做为可写进简历的多模态饮食健康 Agent。  
**Notes:** 要求项目可上线并能经受面试深挖。

## 模型分工

| Option | Description | Selected |
|---|---|---|
| 单模型处理全部任务 | 接入简单，但视觉与文本能力、成本和测试边界混乱 | |
| DeepSeek + Qwen-VL Provider | 文本推理与视觉感知分离，可替换、可测试 | ✓ |
| 万相识别食物 | 万相主要用于图像生成/编辑，不匹配识别任务 | |

**User's choice:** 希望使用 DeepSeek 或阿里模型。  
**Notes:** 采用 DeepSeek 文本推理、Qwen-VL 视觉理解；万相不进入识别链路。

## 身份认证

| Option | Description | Selected |
|---|---|---|
| 匿名设备 ID | 实现快，但无法可靠支撑跨设备长期记忆与后台权限 | |
| 邮箱注册登录 + RBAC | 支撑用户历史、长期记忆和管理员能力 | ✓ |

**User's choice:** 加入登录注册。  
**Notes:** 采用短期 access token、HttpOnly refresh token 轮换和 user/admin 角色。

## 后台管理

| Option | Description | Selected |
|---|---|---|
| 当前阶段实现完整后台 | 会挤占 Agent 主链路，阶段过大 | |
| 当前建立 RBAC，后续阶段完成后台 | 先把安全边界做实，再实现目录和审计 UI | ✓ |

**User's choice:** 后面实现后台管理系统。  
**Notes:** Phase 1 建权限基础，Phase 6 交付完整后台。

## 后端教学

| Option | Description | Selected |
|---|---|---|
| 只靠代码注释 | 容易变成逐行翻译，不能解释完整架构 | |
| 教学文档 + 测试 + 必要注释 | 可追踪请求链、设计理由和失败模式 | ✓ |

**User's choice:** 写代码时带教学。  
**Notes:** 每阶段在 `docs/learning/` 交付中文后端教学文档。

## the agent's Discretion

- 认证库、哈希库、表结构与依赖注入的具体实现。
- UI 视觉细节与工程工具选择。

## Deferred Ideas

- Agent 图、多模态、长期记忆、规划子图、看板与完整后台按新路线图后续阶段交付。
