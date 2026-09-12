---
status: resolved
trigger: 后台管理一直在请求
created: 2026-09-12
updated: 2026-09-12
---

## Symptoms

- Expected: 构建完成或失败后不再自动请求；管理员仍可手动刷新。
- Actual: 向量检索管理页始终请求 `vector-space-builds`。
- Evidence: 页面为 `refetchInterval: 5_000`，没有任何停止条件；截图中的构建已经 `1289 / 1289` 完成。
- Reproduction: 打开后台的“向量检索管理”，等待 5 秒并观察网络请求。

## Current Focus

- hypothesis: 固定轮询间隔没有根据构建是否仍在处理而停用。
- test: 为“存在进行中构建才轮询”增加回归测试。
- expecting: 所有构建均为 ready 或 partial_failure 时，轮询间隔为 false。
- next_action: complete

## Evidence

- timestamp: 2026-09-12
  finding: `VectorRetrievalPage.tsx` 使用固定 `refetchInterval: 5_000`。

## Resolution

- root_cause: React Query 的 `refetchInterval` 被写死为 5 秒，未读取构建状态。
- fix: 仅当存在 pending、processing 或 pending_count 大于 0 的构建时返回 5 秒轮询；其他状态返回 false。
- verification: `VectorRetrievalPage.test.tsx` 3 passed；`tsc --noEmit` passed。
- files_changed: `admin-frontend/src/features/vector-retrieval/VectorRetrievalPage.tsx`, `admin-frontend/src/features/vector-retrieval/VectorRetrievalPage.test.tsx`。
