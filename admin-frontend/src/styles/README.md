# 后台全局样式

## 职责

此目录只保存 Tailwind 入口、后台语义 token、全局键盘焦点和减弱动画规则。功能局部样式必须留在所属组件或 feature，不能在此建立全局业务样式。

## 允许依赖

- 允许依赖 Tailwind CSS 与 `admin-frontend/` 已冻结的 Base UI 语义约定。
- 不得引入远程字体、第二套设计系统、用户 H5 样式文件或业务数据。

## 文件索引

| 文件 | 职责 |
| --- | --- |
| `index.css` | Tailwind 入口、后台浅色内容区与绿色操作色 token、页面壳覆盖、焦点和 `prefers-reduced-motion` 基线。 |
