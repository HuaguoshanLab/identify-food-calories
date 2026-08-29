import { render, waitFor } from '@testing-library/react'
import { createElement, useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { useAgentEventStream } from './useAgentEventStream'

function streamResponse(chunks: string[]) {
  const encoder = new TextEncoder()
  return new Response(new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  }), { status: 200 })
}

function Probe({ request }: { request: (path: string, init?: RequestInit) => Promise<Response> }) {
  const [events, setEvents] = useState<string[]>([])
  useAgentEventStream({
    threadId: 'thread-1',
    request,
    onSnapshot: async () => undefined,
    onEvent: (event) => setEvents((current) => [...current, `${event.id}:${event.type}:${event.summary}`]),
  })
  return createElement('output', undefined, events.join('|'))
}

describe('useAgentEventStream', () => {
  it('fetches the authority snapshot before parsing fragmented CRLF SSE and replays from Last-Event-ID', async () => {
    const request = vi.fn(async (path: string, _init?: RequestInit) => {
      void _init
      if (path.endsWith('/events')) {
        return streamResponse([
          'id: 1\r\nevent: agent\r\ndata: {"type":"running",',
          '\r\ndata: "summary":"正在运行。"}\r\n\r\n',
        ])
      }
      return new Response('{"thread_id":"thread-1"}', { status: 200 })
    })

    const view = render(createElement(Probe, { request }))

    await waitFor(() => expect(view.getByText('1:running:正在运行。')).toBeInTheDocument())
    expect(request.mock.calls[0]?.[0]).toBe('/agent/threads/thread-1')
    expect(request.mock.calls[1]?.[0]).toBe('/agent/threads/thread-1/events')
    expect(new Headers(request.mock.calls[1]?.[1]?.headers).get('Last-Event-ID')).toBe('0')
  })

  it('drops duplicates and heals one sequence gap from a fresh snapshot without inventing events', async () => {
    let streamAttempt = 0
    const request = vi.fn(async (path: string, _init?: RequestInit) => {
      void _init
      if (!path.endsWith('/events')) return new Response('{"thread_id":"thread-1"}', { status: 200 })
      streamAttempt += 1
      return streamResponse(streamAttempt === 1
        ? ['id: 1\ndata: {"type":"running","summary":"one"}\n\nid: 1\ndata: {"type":"running","summary":"duplicate"}\n\nid: 3\ndata: {"type":"completed","summary":"three"}\n\n']
        : ['id: 2\ndata: {"type":"catalog","summary":"two"}\n\nid: 3\ndata: {"type":"completed","summary":"three"}\n\n'])
    })

    const view = render(createElement(Probe, { request }))

    await waitFor(() => expect(view.getByText('1:running:one|2:catalog:two|3:completed:three')).toBeInTheDocument())
    const eventCalls = request.mock.calls.filter(([path]) => path.endsWith('/events'))
    expect(new Headers(eventCalls[1]?.[1]?.headers).get('Last-Event-ID')).toBe('1')
  })
})
