import { createParser } from 'eventsource-parser'
import { useCallback, useEffect, useMemo, useRef } from 'react'

export type DisabledAgentEventStream = {
  availability: 'disabled'
  abort: () => void
}

/**
 * This is intentionally abort-only. Keeping the parser here now reserves one audited boundary
 * for fragmented SSE parsing without pretending that an endpoint or event contract exists.
 */
export function useAgentEventStream(): DisabledAgentEventStream {
  const abortControllerRef = useRef(new AbortController())
  const parser = useMemo(() => createParser({
    maxBufferSize: 1024 * 1024,
    onEvent: () => undefined,
    onError: () => undefined,
  }), [])

  const abort = useCallback(() => {
    abortControllerRef.current.abort()
    parser.reset()
  }, [parser])

  useEffect(() => abort, [abort])

  return { availability: 'disabled', abort }
}
