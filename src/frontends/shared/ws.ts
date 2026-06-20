// Shared WebSocket client for the Orchestrator hub (src/backend/app/ws.py).
// Connects to /ws?role=<role>, parses JSON events, and auto-reconnects with backoff.
import type { WsEvent } from './types'

const WS_BASE = import.meta.env.VITE_WS_URL ?? '/ws'

// Build an absolute ws:// URL from a possibly-relative VITE_WS_URL (e.g. '/ws').
function resolveWsUrl(role: string): string {
  const sep = WS_BASE.includes('?') ? '&' : '?'
  const withRole = `${WS_BASE}${sep}role=${encodeURIComponent(role)}`
  if (/^wss?:\/\//.test(withRole)) return withRole
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${location.host}${withRole}`
}

export interface WsHandle {
  close: () => void
}

// Subscribe to backend events for a role. Returns a handle to close the connection.
// Reconnects automatically (capped backoff) so the panel survives a backend restart.
// onStatus (optional) reports the live connection state for a UI indicator.
export function connectEvents(
  role: string,
  onEvent: (e: WsEvent) => void,
  onStatus?: (connected: boolean) => void,
): WsHandle {
  let ws: WebSocket | null = null
  let closed = false
  let retry = 0
  let timer: ReturnType<typeof setTimeout> | undefined

  function open() {
    if (closed) return
    ws = new WebSocket(resolveWsUrl(role))
    ws.onopen = () => {
      retry = 0
      onStatus?.(true)
    }
    ws.onmessage = (ev) => {
      try {
        onEvent(JSON.parse(ev.data) as WsEvent)
      } catch (err) {
        console.error('[ws] bad message', err)
      }
    }
    ws.onclose = () => {
      onStatus?.(false)
      if (closed) return
      const delay = Math.min(1000 * 2 ** retry, 10000) // 1s,2s,4s… cap 10s
      retry++
      timer = setTimeout(open, delay)
    }
    ws.onerror = () => ws?.close()
  }

  open()

  return {
    close() {
      closed = true
      if (timer) clearTimeout(timer)
      ws?.close()
    },
  }
}
