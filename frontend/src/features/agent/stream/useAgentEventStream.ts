import { createParser } from 'eventsource-parser'
import { useEffect, useRef } from 'react'

export type AgentProgressEvent = { id: string; type: string; summary: string }

type RequestWithSession = (path: string, init?: RequestInit) => Promise<Response>

type AgentEventStreamOptions = {
  threadId?: string
  request: RequestWithSession
  onEvent: (event: AgentProgressEvent) => void
  onSnapshot?: (response: Response) => void | Promise<void>
}

/**
 * Replays safe events only after reading the ledger-owned snapshot. `request` comes from
 * AuthProvider, whose one-refresh/one-replay rule is the sole 401 recovery authority.
 */
export function useAgentEventStream({ threadId, request, onEvent, onSnapshot }: AgentEventStreamOptions) {
  const eventCallbackRef = useRef(onEvent)
  const snapshotCallbackRef = useRef(onSnapshot)
  const lastSequenceRef = useRef(0)

  useEffect(() => {
    eventCallbackRef.current = onEvent
  }, [onEvent])

  useEffect(() => {
    snapshotCallbackRef.current = onSnapshot
  }, [onSnapshot])

  useEffect(() => {
    if (!threadId) return
    lastSequenceRef.current = 0
    const controller = new AbortController()
    const snapshotPath = `/agent/threads/${encodeURIComponent(threadId)}`
    const eventsPath = `${snapshotPath}/events`

    async function fetchSnapshot(): Promise<boolean> {
      const response = await request(snapshotPath, { signal: controller.signal })
      if (!response.ok) return false
      await snapshotCallbackRef.current?.(response)
      return true
    }

    async function connect(): Promise<void> {
      let reconnects = 0
      while (!controller.signal.aborted) {
        try {
          if (!await fetchSnapshot()) return
          let observedGap = false
          const parser = createParser({
            maxBufferSize: 1024 * 1024,
            onEvent(event) {
              const sequence = Number.parseInt(event.id ?? '', 10)
              if (!Number.isSafeInteger(sequence) || sequence <= 0 || sequence <= lastSequenceRef.current) return
              if (sequence !== lastSequenceRef.current + 1) {
                observedGap = true
                return
              }
              try {
                const payload = JSON.parse(event.data) as { type?: string; summary?: string }
                if (typeof payload.type !== 'string' || typeof payload.summary !== 'string') return
                lastSequenceRef.current = sequence
                eventCallbackRef.current({ id: String(sequence), type: payload.type, summary: payload.summary })
              } catch {
                // Malformed server text is not a report and is not eligible for reconnect/retry.
              }
            },
            onError: () => undefined,
          })
          const response = await request(eventsPath, {
            headers: { Accept: 'text/event-stream', 'Last-Event-ID': String(lastSequenceRef.current) },
            signal: controller.signal,
          })
          if (!response.ok || !response.body) return
          const reader = response.body.getReader()
          const decoder = new TextDecoder()
          while (!controller.signal.aborted) {
            const chunk = await reader.read()
            if (chunk.done) break
            parser.feed(decoder.decode(chunk.value, { stream: true }))
          }
          parser.feed(decoder.decode())
          parser.reset()
          if (!observedGap || reconnects >= 1) return
          reconnects += 1
        } catch {
          // AuthProvider already performs one refresh/replay for 401. Do not make client loops.
          return
        }
      }
    }

    void connect()
    return () => controller.abort()
  }, [request, threadId])
}
