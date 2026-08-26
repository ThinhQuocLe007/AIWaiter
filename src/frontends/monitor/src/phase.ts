// The five things this screen ever says, and the one colour each of them owns.
//
// The old monitor showed a five-module signal chain (MIC · VAD · STT · AGENT · TTS) with a
// millisecond readout under each. That is the right instrument for debugging the pipeline and the
// wrong one for a demo: an audience does not know what VAD is, and five numbers changing at once
// reads as noise. So the whole pipeline is folded into ONE phase the room can follow — the robot
// is listening, it is thinking, it is answering, here is the answer — and the phase is rendered as
// a waveform rather than as text, because a wave moving is what makes a machine look alive.
export type Phase = 'idle' | 'listening' | 'thinking' | 'speaking' | 'result' | 'quiet' | 'error'

export interface PhaseView {
  /** What the screen says out loud, big, under the robot. */
  label: string
  /** Second line — one short sentence, never jargon. */
  hint: string
  /** The colour the halo, the wave and the state pill all take. */
  color: string
}

export const PHASES: Record<Phase, PhaseView> = {
  idle: {
    label: 'Sẵn sàng',
    hint: 'Bấm “Bắt đầu ra lệnh” rồi nói với robot.',
    color: '#64748b',
  },
  listening: {
    label: 'Đang nghe',
    hint: 'Mời anh/chị ra lệnh…',
    color: '#38bdf8',
  },
  thinking: {
    label: 'Đang xử lý',
    hint: 'Robot đang hiểu câu lệnh và tra cứu kho.',
    color: '#f59e0b',
  },
  speaking: {
    label: 'Đang trả lời',
    hint: 'Robot đang nói câu trả lời.',
    color: '#34d399',
  },
  result: {
    label: 'Đã xong',
    hint: 'Robot đã nhận lệnh và bắt đầu thực hiện.',
    color: '#34d399',
  },
  quiet: {
    label: 'Chưa nghe rõ',
    hint: 'Không bắt được câu nói — bấm ra lệnh lại giúp em.',
    color: '#64748b',
  },
  error: {
    label: 'Chưa trả lời được',
    hint: 'Có trục trặc ở lượt này — thử lại một lần nữa.',
    color: '#f87171',
  },
}

/** A turn is "running" in every phase where the robot still owes an answer. */
export function isRunning(p: Phase): boolean {
  return p === 'listening' || p === 'thinking' || p === 'speaking'
}

/** Vietnamese name for a box colour. Mirrors `agent_brain/warehouse/colors.py`; the wire carries
 *  the English word because that is what the Gazebo mission takes on its `--color` flag. */
const COLOR_VI: Record<string, string> = { blue: 'xanh dương', red: 'đỏ', green: 'xanh lá' }

/** Vietnamese name for the named places the brain can emit as a bare token (no rack section). */
const PLACE_VI: Record<string, string> = { PACK: 'Trạm đóng gói', DOCK: 'Trạm sạc' }

/** Vietnamese label for a control verb, matching what the robot was actually told to do. */
const VERB_VI: Record<string, string> = {
  stop: 'Dừng tại chỗ',
  resume: 'Chạy tiếp',
  cancel: 'Hủy chuyến',
}

/** The scissor lift. */
const LIFT_VI: Record<string, string> = { up: 'Nâng càng lên', down: 'Hạ càng xuống' }

/** What the robot does on arrival. `fetch` is the default and needs no label — saying "đi lấy"
 *  on every single navigate chip would drown out the three cases that actually differ. */
const TASK_VI: Record<string, string> = {
  fetch_hold: 'giữ trên khay',
  goto: 'chỉ chạy tới, không gắp',
  deliver: 'mang về đóng gói',
}

/** Human label for the agent's structured action, e.g. a navigate token →
 *  "Di chuyển đến Khu A · ô A01 · hộp xanh dương", a non-default task appended as
 *  "— chỉ chạy tới, không gắp", or an immediate command → "Dừng tại chỗ" / "Nâng càng lên".
 *  Returns '' when the turn produced no action, which is most answer/chat turns. */
export function actionLabel(action: Record<string, any> | null): string {
  if (!action) return ''
  if (action.type === 'control') {
    return VERB_VI[action.verb] ?? String(action.verb ?? 'Điều khiển')
  }
  if (action.type === 'lift') {
    return LIFT_VI[action.direction] ?? String(action.direction ?? 'Càng nâng')
  }
  if (action.type === 'navigate') {
    const p = action.position ?? {}
    // A named place has a token but no section — "Khu PACK" would be wrong, so name it directly.
    const place = p.section ? `Khu ${p.section}` : PLACE_VI[p.token] ?? (p.token ? `Khu ${p.token}` : '')
    const parts = [
      place,
      p.slot ? `ô ${p.slot}` : '',
      p.color ? `hộp ${COLOR_VI[p.color] ?? p.color}` : '',
    ].filter(Boolean)
    const task = TASK_VI[action.task]
    const where = parts.length ? `Di chuyển đến ${parts.join(' · ')}` : 'Di chuyển'
    return task ? `${where} — ${task}` : where
  }
  return String(action.type ?? '')
}
