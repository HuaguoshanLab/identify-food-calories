import { createParser } from 'eventsource-parser'
import { useEffect, useRef } from 'react'

export type AgentProgressEvent = { id: string; type: string; summary: string }

type RequestWithSession = (path: string, init?: RequestInit) => Promise<Response>

type AgentEventStreamOptions = {
  threadId?: string
  request: RequestWithSession
  onEvent: (event: AgentProgressEvent) => void
}

/**
 * Replays server-owned progress events after an authoritative snapshot has been requested.
 * It never derives a report from events and aborting this fetch has no server-side run meaning.
 */
export function useAgentEventStream({ threadId, request, onEvent }: AgentEventStreamOptions) {
  const callbackRef = useRef(onEvent)

  useEffect(() => {
    callbackRef.current = onEvent
  }, [onEvent])

  useEffect(() => {
    if (!threadId) return
    const controller = new AbortController()
    const parser = createParser({
      maxBufferSize: 1024 * 1024,
      onEvent(event) {
        try {
          const payload = JSON.parse(event.data) as { type?: string; summary?: string }
          callbackRef.current({ id: event.id ?? '', type: payload.type ?? 'unknown', summary: payload.summary ?? '' })
        } catch {
          // Server payload errors must not become a client-side report or retry loop.
        }
      },
      onError: () => undefined,
    })
    void request(`/agent/threads/${encodeURIComponent(threadId)}/events`, {
      headers: { Accept: 'text/event-stream' }, signal: controller.signal,
    }).then(async (response) => {
      if (!response.ok || !response.body) return
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      while (!controller.signal.aborted) {
        const result = await reader.read()
        if (result.done) break
        parser.feed(decoder.decode(result.value, { stream: true }))
      }
    }).catch(() => undefined)
    return () => { controller.abort(); parser.reset() }
  }, [request, threadId])
}
