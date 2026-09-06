import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/auth/useAuth'
import { Card, CardContent } from '@/components/ui/card'
import { listMemories, type Memory } from '../api/client'

const label = { goal: '目标', avoidance: '忌口', stable_preference: '稳定偏好' }
const source = { user_statement: '用户直接表达', model_inference: '已确认推测', user_maintained: '用户手动维护' }
export function MemoryManagementPage() { const { request } = useAuth(); const [memories, setMemories] = useState<Memory[]>(); const [error, setError] = useState(''); useEffect(() => { void listMemories(request).then(setMemories).catch(() => setError('暂时无法加载记忆。')) }, [request]); return <section className="space-y-4"><div><p className="text-[15px] text-muted-foreground">查看和管理会影响后续建议的偏好。</p></div>{error ? <p className="text-sm text-destructive">{error}</p> : null}{memories === undefined && !error ? <p className="text-sm text-muted-foreground">正在加载…</p> : null}{memories?.length === 0 ? <Card><CardContent className="py-8 text-center text-sm text-muted-foreground">还没有长期偏好。你在分析时明确说明的饮食目标和忌口会保存在这里。</CardContent></Card> : null}{memories?.map((memory) => <Link className="block" key={memory.id} to={`/app/me/memories/${memory.id}/edit`}><Card><CardContent className="space-y-1 py-3"><p className="font-medium">{label[memory.category]} · {memory.canonical_text}</p><p className="text-[13px] text-muted-foreground">{source[memory.source_kind]} · 更新于 {new Date(memory.updated_at).toLocaleString('zh-CN')}</p></CardContent></Card></Link>)}</section> }
