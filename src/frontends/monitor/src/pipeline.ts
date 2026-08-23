// The monitor's model of one voice turn.
//
// Two independent sources describe the same turn and neither one sees all of it:
//
//   * the DEVICE (Jetson) reports what only it can know — mic armed, how long the guest spoke,
//     how long Whisper took, which sentence is coming out of the speaker. These arrive as
//     `voice.device` frames (relayed from its telemetry, see src/edge_voice/main.py).
//   * the AGENT reports what only it can know — the reply, the dialogue stage, the cart, the
//     LLM timings. These are the ordinary `voice.*` bridge events every tablet also gets.
//
// This module folds both streams into one state so the UI never has to care which side spoke.

export type StageId = 'mic' | 'vad' | 'stt' | 'agent' | 'tts'

/** What a rack module is doing right now. `fault` covers every way a turn can end badly. */
export type StageState = 'idle' | 'active' | 'done' | 'fault'

export interface StageView {
  id: StageId
  label: string
  /** What this module IS, in the guest's terms — shown under the label, not a tooltip. */
  caption: string
  state: StageState
  /** The one number or word worth reading from across the room. */
  readout: string
  /** Secondary detail line; empty hides it. */
  detail: string
}

/** One finished (or abandoned) turn, as recorded in the ledger. */
export interface TurnRecord {
  n: number
  at: Date
  heard: string
  reply: string
  stage: string | null
  /** Per-phase milliseconds. Missing phases stay undefined rather than 0 — an unknown
   *  duration and an instant one must not draw the same bar. */
  speechMs?: number
  sttMs?: number
  firstSentenceMs?: number
  llmTotalMs?: number
  turnMs?: number
  sentences: number
  outcome: 'ok' | 'cancelled' | 'timeout' | 'empty' | 'error'
  note?: string
}

export interface LogLine {
  id: number
  at: Date
  source: 'device' | 'agent'
  text: string
  tone: 'plain' | 'signal' | 'fault'
}

export const STAGE_ORDER: StageId[] = ['mic', 'vad', 'stt', 'agent', 'tts']

const STAGE_META: Record<StageId, { label: string; caption: string }> = {
  mic: { label: 'MIC', caption: 'micro trên robot' },
  vad: { label: 'VAD', caption: 'tách tiếng nói' },
  stt: { label: 'STT', caption: 'Whisper chép lời' },
  agent: { label: 'AGENT', caption: 'LLM trên server' },
  tts: { label: 'TTS', caption: 'robot nói ra' },
}

export function blankStages(): Record<StageId, StageView> {
  return Object.fromEntries(
    STAGE_ORDER.map((id) => [
      id,
      { id, ...STAGE_META[id], state: 'idle' as StageState, readout: '—', detail: '' },
    ]),
  ) as Record<StageId, StageView>
}

export function fmtMs(ms: number | undefined | null): string {
  if (ms == null) return '—'
  return ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(1)}s`
}
