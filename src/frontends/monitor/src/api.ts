// REST calls the monitor makes. Separate from @shared/rest because every one of these addresses a
// mic by `robot_id` — the monitor drives a device directly, with no table binding in the way.
const API_URL = import.meta.env.VITE_API_URL ?? '/api'

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`POST ${path} → ${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export interface VoiceDevice {
  robot_id: string
  busy: boolean
}

export async function fetchDevices(): Promise<{ devices: VoiceDevice[]; default_table_id: number }> {
  const res = await fetch(`${API_URL}/voice/devices`)
  if (!res.ok) throw new Error(`GET /voice/devices → ${res.status}`)
  return res.json()
}

/** `status` is 'ok' when the command reached the mic, 'no_device' when that Jetson isn't connected. */
type Ack = { status: string }

export function startListening(robotId: string, tableId: number): Promise<Ack> {
  return post('/voice/listen', { robot_id: robotId, table_id: tableId })
}

export function cancelTurn(robotId: string, tableId: number): Promise<Ack> {
  return post('/voice/cancel', { robot_id: robotId, table_id: tableId })
}

export function setMuted(robotId: string, tableId: number, muted: boolean): Promise<Ack> {
  return post('/voice/mute', { robot_id: robotId, table_id: tableId, muted })
}

export function newConversation(robotId: string, tableId: number): Promise<Ack> {
  return post('/voice/new-chat', { robot_id: robotId, table_id: tableId })
}
