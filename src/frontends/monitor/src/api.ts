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
  /** Last levels this mic reported, in percent. Undefined until it has reported any — the
   *  steppers stay disabled rather than guessing a position. */
  speaker?: number | null
  mic?: number | null
  /** False when the device has no `pactl` and therefore no levels to move. */
  can_set?: boolean
}

export type AudioTarget = 'speaker' | 'mic'

export async function fetchDevices(): Promise<{ devices: VoiceDevice[] }> {
  const res = await fetch(`${API_URL}/voice/devices`)
  if (!res.ok) throw new Error(`GET /voice/devices → ${res.status}`)
  return res.json()
}

/** `status` is 'ok' when the command reached the mic, 'no_device' when that Jetson isn't connected. */
type Ack = { status: string }

/** `robotId` addresses the mic AND names the agent's conversation thread — one robot, one thread. */
export function startListening(robotId: string): Promise<Ack> {
  return post('/voice/listen', { robot_id: robotId })
}

export function cancelTurn(robotId: string): Promise<Ack> {
  return post('/voice/cancel', { robot_id: robotId })
}

export function newConversation(robotId: string): Promise<Ack> {
  return post('/voice/new-chat', { robot_id: robotId })
}

/** Move the Jetson's real PulseAudio level. The reply only says the command was delivered —
 *  the true value comes back as a `levels` telemetry frame once the device has applied it. */
export function setAudioLevel(robotId: string, target: AudioTarget, percent: number): Promise<Ack> {
  return post('/voice/audio-level', { robot_id: robotId, target, percent })
}
