# Memory Components

## 职责

呈现长期偏好的类别、来源、时间，以及安全编辑/删除交互。

列表与编辑页主标题由 DetailLayout 的固定页头提供；内容区保留说明和操作，不再重复h1。

## 允许依赖

- React、Router、memory API、认证请求与现有 UI primitives。

## 文件索引

| 文件 | 职责 |
|---|---|
| `MemoryManagementPage.tsx` | 偏好列表与真实空态 |
| `MemoryEditPage.tsx` | 内容编辑与删除确认 |

H5第5项：列表保留类别、完整偏好、来源与时间，统一卡片密度和长文换行；编辑字段使用白卡，保存及删除语义不变。
