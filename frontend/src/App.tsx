import { useQuery } from '@tanstack/react-query'

type HealthResponse = {
  status: 'ok'
  version: string
}

const apiBaseUrl = 'http://127.0.0.1:8000'

async function loadHealth(): Promise<HealthResponse> {
  const response = await fetch(`${apiBaseUrl}/api/v1/health`)

  if (!response.ok) {
    throw new Error(`Health request failed with status ${response.status}`)
  }

  return (await response.json()) as HealthResponse
}

export function App() {
  const health = useQuery({
    queryKey: ['system', 'health'],
    queryFn: loadHealth,
    refetchInterval: (query) => (query.state.data?.status === 'ok' ? false : 1_000),
  })

  const healthLabel =
    health.data?.status === 'ok' ? `正常（API ${health.data.version}）` : '连接中'

  return (
    <main>
      <h1>饮食健康 Agent</h1>
      <p>前端运行壳已启动，业务功能将在后续计划接入。</p>
      <p role="status" aria-live="polite">
        后端状态：{healthLabel}
      </p>
    </main>
  )
}
