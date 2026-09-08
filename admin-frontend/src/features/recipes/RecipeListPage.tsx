import { useQuery } from '@tanstack/react-query'
import { useAdminAuth } from '@/auth/AdminAuthProvider'
import { listRecipeCandidates } from './api'

const labels = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐', snack: '加餐', pending: '待审核', enabled: '已启用', disabled: '已停用' } as const

export function RecipeListPage() {
  const { accessToken, clearSession } = useAdminAuth()
  const query = useQuery({ queryKey: ['recipe-candidates'], queryFn: () => listRecipeCandidates(accessToken!), enabled: Boolean(accessToken), retry: false })
  if (!accessToken) return <p className="p-6">登录已失效，请重新登录。</p>
  if (query.isError) return <section className="p-6"><p role="alert">暂时无法加载菜谱候选。</p><button className="mt-3 rounded border px-3 py-2" onClick={() => { clearSession() }} type="button">重新登录</button></section>
  return <section className="space-y-5 p-4 lg:p-6"><div><h2 className="text-base font-semibold">菜谱管理</h2><p className="mt-1 text-sm text-muted-foreground">候选菜必须关联当前合格的营养目录；只有已启用的菜可进入餐单。</p></div><div className="overflow-x-auto rounded-lg border bg-card"><table className="w-full whitespace-nowrap text-left text-sm"><thead className="border-b bg-muted/40 text-xs text-muted-foreground"><tr>{['目录菜品', '餐次', '单份克数', '份量说明', '做法', '口味', '状态'].map((label) => <th className="px-4 py-3" key={label}>{label}</th>)}</tr></thead><tbody>{query.isPending ? <tr><td className="p-10 text-center" colSpan={7}>正在加载菜谱候选…</td></tr> : query.data?.items.map((item) => <tr className="border-b" key={item.id}><td className="px-4 py-3 font-medium">{item.catalog_food_name}</td><td className="px-4 py-3">{labels[item.meal_slot]}</td><td className="px-4 py-3">{item.portion_grams}g</td><td className="px-4 py-3">{item.portion_description}</td><td className="px-4 py-3">{item.method_tags.join('、')}</td><td className="px-4 py-3">{item.flavour_tags.join('、')}</td><td className="px-4 py-3">{labels[item.status]}</td></tr>)}</tbody></table></div></section>
}
