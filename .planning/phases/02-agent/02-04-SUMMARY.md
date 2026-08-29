---
phase: 02-agent
plan: 04
subsystem: frontend-agent-ui
tags: [react, typescript, vite, vitest, testing-library, eventsource-parser, accessibility]
requires:
  - phase: 01-engineering-auth-foundation
    provides: "受保护 AppShell、内存 access token、公开认证 API 与 H5 页面壳"
  - phase: 02-agent
    provides: "已批准的 eventsource-parser 3.1.0 供应链证据"
provides:
  - "受保护分析 Tab 的可访问文字输入与诚实未接通状态"
  - "feature-first 的 agent/components、agent/api、agent/stream 目录合同"
  - "精确锁定的 eventsource-parser 与 abort-only 流传输骨架"
affects: [agent-api, agent-stream, openapi-generation, sse, user-h5]
tech-stack:
  added: [eventsource-parser 3.1.0]
  patterns: ["feature-first Agent UI", "honest unavailable state", "authenticated-fetch SSE boundary", "generated OpenAPI-only client boundary"]
key-files:
  created:
    - frontend/src/features/agent/components/AnalyzePage.tsx
    - frontend/src/features/agent/components/AnalyzePage.test.tsx
    - frontend/src/features/agent/stream/useAgentEventStream.ts
    - frontend/src/features/agent/api/README.md
    - frontend/src/features/agent/stream/README.md
  modified:
    - frontend/src/App.tsx
    - frontend/src/App.test.tsx
    - frontend/package.json
    - frontend/package-lock.json
    - frontend/src/README.md
key-decisions:
  - "分析页在 API 未交付前显示明确未接通状态，绝不渲染虚构报告或营养数值。"
  - "/app 的 replace 入口指向 /app/analyze，分析页仍完全位于既有 RequireAuthentication 与 AppShell 内。"
  - "事件流只允许认证 fetch 加 eventsource-parser 的后续接线；当前 transport 只提供取消能力。"
patterns-established:
  - "Agent UI 只消费运行时生成的 OpenAPI 合约，不能持有 Graph State、后端 DTO 或营养计算。"
  - "SSE 原始 chunk 必须交给 eventsource-parser，传输层不手写换行切分或拼装报告。"
requirements-completed: [ARC-05, QLT-02]
duration: 16min
completed: 2026-08-29
---

# Phase 02 Plan 04: Agent H5 分析入口与传输边界 Summary

**受保护的分析页提供可访问餐食文字输入和真实“接线中”状态，并为后续生成 API 与 SSE 建立可审查边界。**

## Performance

- **Duration:** 16 min
- **Started:** 2026-08-29T03:59:00Z
- **Completed:** 2026-08-29T04:15:10Z
- **Tasks:** 2/2
- **Files modified:** 13

## Accomplishments

- 以 `AnalyzePage` 替换分析 Tab 占位页，并将 `/app` 的 replace 路由改为 `/app/analyze`；用户仍必须先经过既有认证守卫。
- 页面有可见 label、字段级空值/超长校验、44px 主按钮、焦点管理和 `aria-live` 状态；后端未接通时只说明不可提交，不展示报告、数值、图片、保存或规划入口。
- 建立 `features/agent/{components,api,stream}` 的目录 README 与逐级索引，精确锁定 `eventsource-parser@3.1.0`，并保留无网络的取消式 stream 骨架。
- 验证前端全量 90 个测试、类型检查、Lint、生产构建，以及后端目录合同测试。

## Task Commits

1. **Task 1: 创建可访问的诚实分析页（RED）** — `a4e2b38` (`test`)
2. **Task 1: 创建可访问的诚实分析页（GREEN）** — `a68ecef` (`feat`)
3. **Task 2: 同提交建立 feature 目录合同** — `293eeb8` (`feat`)

## Files Created/Modified

- `frontend/src/features/agent/components/AnalyzePage.tsx` — 文字输入、校验、提交中/未接通/错误状态与焦点管理。
- `frontend/src/features/agent/components/AnalyzePage.test.tsx` — 空值、超长、提交中和诚实未接通状态测试。
- `frontend/src/App.tsx`、`frontend/src/App.test.tsx` — 受保护分析页路由及历史行为合同。
- `frontend/src/features/agent/{README.md,api/README.md,stream/README.md}`、`frontend/src/features/README.md`、`frontend/src/README.md` — feature 职责、允许依赖和文件索引。
- `frontend/src/features/agent/stream/useAgentEventStream.ts` — 不发起网络请求的 parser/abort 接线位。
- `frontend/package.json`、`frontend/package-lock.json` — 精确锁定已批准的 `eventsource-parser@3.1.0`。

## Decisions Made

- 在真实 controller/结果合约尚未存在时，页面主动暴露“分析能力正在接线中”，避免把可输入 UI 误导成可用分析。
- 选择 native textarea 配合现有语义 token 和 UI Button；没有添加额外样式系统或未交付功能入口。
- stream skeleton 不包含 endpoint、fetch、EventSource、手写 parser 或报告拼装；其唯一职责是保留受控取消和 parser 边界。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] 新建 feature 层级在 RED 提交中同步补齐父目录文档**
- **Found during:** Task 1
- **Issue:** Task 1 创建 `features/agent/components` 时，计划文件未在该 TDD 提交的 files 清单中列出 `features/README.md` 与 `agent/README.md`；这会违反项目“新目录与每级直接父 README 同次提交”的硬约束。
- **Fix:** 在 RED 提交中一并创建三级 README 与父 `src` 索引；Task 2 再补充 api/stream 实际索引。
- **Files modified:** `frontend/src/features/README.md`, `frontend/src/features/agent/README.md`, `frontend/src/features/agent/components/README.md`, `frontend/src/README.md`
- **Verification:** 后端 `test_directory_contract.py` 2 passed，所有目录均有职责、允许依赖和索引。
- **Committed in:** `a4e2b38`, `293eeb8`

**2. [Rule 1 - Bug] 让既有路由测试断言真实分析页标题**
- **Found during:** Task 1 GREEN 验证
- **Issue:** 既有 `App.test.tsx` 仍断言分析 Tab 的占位标题“分析”，导致路由替换后回归失败。
- **Fix:** 将 index、深链和浏览器返回路径的断言改为新页面唯一 `h1`“描述这餐吃了什么”。
- **Files modified:** `frontend/src/App.test.tsx`
- **Verification:** 目标测试 7 passed，前端全量 90 passed。
- **Committed in:** `a68ecef`

---

**Total deviations:** 2 auto-fixed（1 个 Rule 2，1 个 Rule 1）。
**Impact on plan:** 两项修复均为目录合同和既有路由回归的正确性所必需；没有扩展产品能力。

## Browser Verification

- 启动本机 FastAPI 与 Vite 后，内置浏览器访问 `http://127.0.0.1:5173/app/analyze`，实际 `/api/v1/auth/refresh` 返回 401，并被既有 `RequireAuthentication` 正确送回登录页；未绕过认证、未伪造登录或分析结果。
- 未完成已登录页面的浏览器验收：继续需要在浏览器向本机 `/api/v1/auth/*` 提交账号凭据。该操作涉及输入密码，未在没有即时人工确认的情况下执行。

## Issues Encountered

- 默认沙箱不能绑定本机端口；以受控权限启动本机服务后完成实际路由验收。浏览器直接打开 JSON health URL 被客户端拦截，但 FastAPI 日志确认该公开接口返回 200，且同一浏览器路径的 refresh 请求返回预期 401。

## Known Stubs

| Stub | File | Reason |
|---|---|---|
| abort-only stream transport | `frontend/src/features/agent/stream/useAgentEventStream.ts` | API、事件版本与快照合约由后续计划交付；当前不允许发起未定义的网络请求。 |
| unavailable analysis submission | `frontend/src/features/agent/components/AnalyzePage.tsx` | controller 尚未接通；页面明确告知不可提交，不阻碍本计划的“诚实入口”目标。 |

## User Setup Required

None - eventsource-parser 的精确版本已由用户批准并锁定；本计划未要求模型密钥或第三方账号。

## Next Phase Readiness

- 后续计划可以将运行时 OpenAPI 生成客户端接到 `agent/api/`，再将认证 fetch 的 chunk 接入现有 `eventsource-parser` 边界。
- 已登录页面的真实浏览器验收需要用户在浏览器内自行登录，或明确授权向本机公开认证 API 提交测试凭据。

## Self-Check: PASSED

- `AnalyzePage.tsx` 与 `useAgentEventStream.ts` 已确认存在。
- TDD RED `a4e2b38`、GREEN `a68ecef` 和目录/依赖提交 `293eeb8` 均已确认存在。
- `npm test`（90 passed）、`npm run typecheck`、`npm run lint`、`npm run build` 与后端目录合同测试均通过。

*Phase: 02-agent*
*Completed: 2026-08-29*
