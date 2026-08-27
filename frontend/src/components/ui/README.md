# shadcn UI Components

## 职责

`src/components/ui/` 是 shadcn 官方 Base UI 组件的唯一落点。生成的原子组件和共享 `cn` utility 位于此处，业务组合组件应放在父目录而不是污染 UI 原语层。

## 允许依赖

- 仅允许 React、`@base-ui/react`、Lucide、Tailwind CSS class、`class-variance-authority`、`clsx` 与 `tailwind-merge`。
- 新增组件只能来自 shadcn 官方 registry；不得复制第三方 registry、远程 block 或项目外动态代码。
- 不允许发起网络请求、读取认证状态或拥有业务规则。

## 文件索引

| 文件 | 职责 |
|---|---|
| `README.md` | UI 原语目录安全边界与索引 |
| `utils.ts` | 官方 `clsx` + `tailwind-merge` class 合并函数 |
| `utils.test.ts` | `cn` 条件 class 与 Tailwind 冲突合并行为测试 |
| `button.tsx` | 官方 Base UI Button 与 shadcn variants/尺寸 class |
| `input.tsx` | 官方 Base UI Input，保留浏览器原生表单语义 |
| `label.tsx` | 可关联表单控件的原生 Label 封装 |
| `card.tsx` | 使用共享 token 和 `cn` 的 Card 布局原语 |
| `separator.tsx` | 官方 Base UI 水平/垂直分隔线 |
| `alert.tsx` | 具备 `role="alert"` 的状态与错误提示原语 |
| `alert-dialog.tsx` | 官方 Base UI 模态确认对话框，支持焦点管理与 Escape 关闭 |
| `badge.tsx` | 可渲染为语义元素的状态标签与官方 variants |
| `skeleton.tsx` | 固定尺寸的加载占位原语，遵守全局 reduced-motion 样式 |
| `components.test.tsx` | Alert、AlertDialog 焦点/Escape、focus ring 与 Skeleton 渲染行为测试 |
