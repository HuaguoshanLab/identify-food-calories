import type { CatalogAuditEvent } from '@/features/catalog/api'

const safeFieldLabels = {
  canonical_name: '菜品名称',
  aliases: '别名',
  energy_kcal_per_100g: '每 100g 能量',
  protein_g_per_100g: '每 100g 蛋白质',
  fat_g_per_100g: '每 100g 脂肪',
  carbohydrate_g_per_100g: '每 100g 碳水',
  source_name: '来源名称',
  source_url: '来源链接',
  authorization_status: '授权状态',
  eligibility: '可用状态',
} as const

type SafeField = keyof typeof safeFieldLabels
type AuditValue = string | number | boolean | null

function isSafeField(value: string): value is SafeField {
  return value in safeFieldLabels
}

function safeRows(event: CatalogAuditEvent) {
  const keys = new Set([...Object.keys(event.before), ...Object.keys(event.after)])
  return [...keys].filter(isSafeField).map((field) => ({
    field,
    before: event.before[field] as AuditValue | undefined,
    after: event.after[field] as AuditValue | undefined,
  }))
}

function renderValue(value: AuditValue | undefined) {
  return value === undefined || value === null ? '—' : String(value)
}

export function AuditTimeline({ events }: Readonly<{ events: readonly CatalogAuditEvent[] }>) {
  return <section aria-labelledby="audit-timeline-title" className="rounded-lg border bg-card p-4">
    <h2 className="text-xl font-semibold" id="audit-timeline-title">操作审计</h2>
    <p className="mt-1 text-sm text-muted-foreground">只显示后端允许的操作者、时间、理由和字段级证据。</p>
    {events.length === 0 ? <p className="mt-4 text-sm">尚无可显示的目录操作审计。</p> : <ol className="mt-4 space-y-4 border-l pl-4">
      {events.map((event) => <li className="space-y-2" key={event.id}>
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-sm">
          <span className="font-semibold">{event.action}</span>
          <span>操作者 {event.actor_identifier}</span>
          <time dateTime={event.occurred_at}>{new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(new Date(event.occurred_at))} UTC</time>
        </div>
        <p className="text-sm">理由：{event.reason}</p>
        {event.related_version ? <p className="text-sm text-muted-foreground">关联版本：{event.related_version}</p> : null}
        {safeRows(event).length ? <table className="w-full text-left text-sm"><caption className="sr-only">{event.action} 的安全字段差异</caption><thead><tr><th scope="col">字段</th><th scope="col">操作前</th><th scope="col">操作后</th></tr></thead><tbody>{safeRows(event).map((row) => <tr className="border-t" key={row.field}><th className="py-2 font-normal" scope="row">{safeFieldLabels[row.field]}</th><td>{renderValue(row.before)}</td><td>{renderValue(row.after)}</td></tr>)}</tbody></table> : null}
      </li>)}
    </ol>}
  </section>
}
