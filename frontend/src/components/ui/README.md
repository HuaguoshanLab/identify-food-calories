# shadcn UI Components

## 职责

`src/components/ui/` 是 shadcn 官方 Base UI 组件的唯一落点。生成的原子组件和共享 `cn` utility 位于此处，业务组合组件应放在父目录而不是污染 UI 原语层。

## 允许依赖

- 仅允许 React、`@base-ui/react`、Lucide、Tailwind CSS class、`clsx` 与 `tailwind-merge`。
- 新增组件只能来自 shadcn 官方 registry；不得复制第三方 registry、远程 block 或项目外动态代码。
- 不允许发起网络请求、读取认证状态或拥有业务规则。

## 文件索引

| 文件 | 职责 |
|---|---|
| `README.md` | UI 原语目录安全边界与索引 |
| `utils.ts` | 官方 `clsx` + `tailwind-merge` class 合并函数 |
| `utils.test.ts` | `cn` 条件 class 与 Tailwind 冲突合并行为测试 |
