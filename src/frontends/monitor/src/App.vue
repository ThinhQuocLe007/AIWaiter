<template>
  <div class="screen" :class="{ speaking: phase === 'speaking' }" :style="{ '--state': view.color }">
    <!-- The header carries everything that is true all the time and interesting to nobody:
         who this is, whether the hub is up, which mic we are driving. It gets one line. -->
    <header class="top">
      <div class="ident">
        <span class="logo" aria-hidden="true">
          <svg viewBox="0 0 32 32">
            <rect x="5" y="11" width="22" height="13" rx="3" fill="none" stroke="currentColor" stroke-width="2" />
            <path d="M5 19h22" stroke="currentColor" stroke-width="2" />
            <circle cx="11" cy="25" r="2.4" fill="currentColor" />
            <circle cx="21" cy="25" r="2.4" fill="currentColor" />
            <rect x="14.5" y="4" width="3" height="7" rx="1.5" fill="currentColor" />
            <circle cx="16" cy="3.2" r="2.4" fill="currentColor" />
          </svg>
        </span>
        <span class="brand">
          <span class="eyebrow">AI WAREHOUSE</span>
          <span class="name">TRỢ LÝ KHO ROBOT</span>
        </span>
      </div>

      <div class="link">
        <span class="pip" :class="{ on: connected && !!robotId }"></span>
        <template v-if="!connected">Đang kết nối…</template>
        <template v-else-if="!devices.length">Chưa có robot</template>
        <select v-else-if="devices.length > 1" v-model="robotId" class="pick">
          <option v-for="d in devices" :key="d.robot_id" :value="d.robot_id">{{ d.robot_id }}</option>
        </select>
        <template v-else>{{ robotId }}</template>
      </div>
    </header>

    <!-- The stage. One robot, one wave, one line of state, one answer. Nothing else is allowed
         on this screen — every panel the old monitor had (stage chain, live log, turn ledger)
         competed with the robot for the same glance. -->
    <main class="stage">
      <div class="bot-wrap">
        <RobotAvatar :phase="phase" />
      </div>

      <!-- Live fleet telemetry — pin/trạng thái/vị trí of the robot this screen is driving, so a
           demo audience sees the machine is real and where it is, not just a talking head. -->
      <div class="telemetry" v-if="robot">
        <span class="t-item">
          <svg viewBox="0 0 24 24" aria-hidden="true" class="t-ico"><rect x="2" y="7" width="17" height="10" rx="2.5" fill="none" stroke="currentColor" stroke-width="2"/><rect x="4" y="9.5" width="11" height="5" rx="1" :fill="batteryColor"/><rect x="20" y="10" width="2.5" height="4" rx="1" fill="currentColor"/></svg>
          Pin {{ battery }}%
        </span>
        <span class="t-item">{{ activityLabel }}</span>
        <span class="t-item" v-if="robot.x != null && robot.y != null">Vị trí ({{ robot.x.toFixed(1) }}, {{ robot.y.toFixed(1) }})</span>
      </div>

      <VoiceWave class="wave-box" :phase="phase" :color="view.color" />

      <!-- The big non-text action glyph: a navigate pin / lift arrow / stop sign appears over the
           robot the moment it is told a job, so a room that never reads the transcript still gets
           WHAT the robot is doing. -->
      <Transition name="pop">
        <ActionGlyph v-if="rawAction" :action="rawAction" class="action-glyph" />
      </Transition>

      <!-- One-shot success burst: the moment the robot's job is accepted (phase → result), a ring
           expands from it once. The "xong việc" is felt, not read. -->
      <div v-if="burstKey" :key="burstKey" class="burst" aria-hidden="true"></div>

      <div class="state">
        <p class="state-label">{{ view.label }}</p>
        <p class="state-hint">{{ note || view.hint }}</p>
      </div>

      <!-- The answer. Present only when there is one, so an empty stage never shows an empty
           box — and it holds until the next turn starts, which is what lets a guest read it. -->
      <Transition name="rise">
        <section v-if="resultText" class="result" :class="{ live: phase === 'speaking' }">
          <p v-if="heardText" class="heard">“{{ heardText }}”</p>
          <p class="answer">{{ resultText }}</p>
          <p v-if="action" class="chip">{{ action }}</p>
        </section>
      </Transition>
    </main>

    <!-- Recent commands: a glanceable strip of the last few turns so a demo can replay what the
         robot was told without scrolling a chat. Newest on the right; capped so it never grows
         off-screen. -->
    <div class="history" v-if="history.length">
      <div class="h-item" v-for="h in history" :key="h.id">
        <p class="h-heard" v-if="h.heard">“{{ h.heard }}”</p>
        <p class="h-answer">{{ h.answer }}</p>
        <p class="h-chip" v-if="h.action">{{ h.action }}</p>
      </div>
    </div>

    <!-- Everything a finger touches, in one rail across the bottom at demo scale. -->
    <footer class="controls">
      <button class="act go" :disabled="!robotId || running" @click="onListen">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3Z" />
          <path d="M5 11a7 7 0 0 0 14 0M12 18v3" fill="none" stroke-width="2" />
        </svg>
        Bắt đầu ra lệnh
      </button>

      <button class="act" :disabled="!robotId || !running" @click="onCancel">
        <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2" /></svg>
        Dừng
      </button>

      <button class="act" :disabled="!robotId" @click="onNewChat">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M20 12a8 8 0 1 1-2.6-5.9M20 4v5h-5" fill="none" stroke-width="2" />
        </svg>
        Hội thoại mới
      </button>

      <!-- Two steppers, not two sliders. A slider needs a precise drag; on a touchscreen mid-demo
           a ±10 button lands every time, and the number between them still shows the truth the
           Jetson reported back. -->
      <div class="dial" :class="{ off: !levelsKnown }">
        <span class="cap"><svg viewBox="0 0 24 24" aria-hidden="true" class="cap-ico"><path d="M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3Z" fill="none" stroke="currentColor" stroke-width="2"/><path d="M5 11a7 7 0 0 0 14 0" fill="none" stroke="currentColor" stroke-width="2"/></svg> Mic</span>
        <button class="step" :disabled="!levelsKnown" @click="bump('mic', -10)" aria-label="Giảm mic">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>
        </button>
        <span class="val">{{ levelsKnown ? `${micLevel}%` : '—' }}</span>
        <button class="step" :disabled="!levelsKnown" @click="bump('mic', 10)" aria-label="Tăng mic">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>
        </button>
      </div>

      <div class="dial" :class="{ off: !levelsKnown }">
        <span class="cap"><svg viewBox="0 0 24 24" aria-hidden="true" class="cap-ico"><path d="M4 9v6h4l5 4V5L8 9H4z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M16 9a4 4 0 0 1 0 6M18.5 7a7 7 0 0 1 0 10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg> Loa</span>
        <button class="step" :disabled="!levelsKnown" @click="bump('speaker', -10)" aria-label="Giảm loa">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>
        </button>
        <span class="val">{{ levelsKnown ? `${speaker}%` : '—' }}</span>
        <button class="step" :disabled="!levelsKnown" @click="bump('speaker', 10)" aria-label="Tăng loa">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>
        </button>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { connectEvents, type WsHandle } from '@shared/ws'
import { fetchRobots, type Robot } from '@shared/rest'
import RobotAvatar from './components/RobotAvatar.vue'
import VoiceWave from './components/VoiceWave.vue'
import ActionGlyph from './components/ActionGlyph.vue'
import { PHASES, actionLabel, isRunning, type Phase } from './phase'
import {
  cancelTurn,
  fetchDevices,
  newConversation,
  setAudioLevel,
  startListening,
  type AudioTarget,
  type VoiceDevice,
} from './api'

// Ceilings match audio_levels.py on the device: the speaker stops at 100 because past it
// PulseAudio adds digital gain and a hall hears clipping; the mic is allowed headroom because a
// quiet USB capsule in a noisy room genuinely needs it.
const MAX = { speaker: 100, mic: 150 }

const connected = ref(false)
const devices = ref<VoiceDevice[]>([])
const robotId = ref('')
const note = ref('') // transient line replacing the phase hint (command acks)

const phase = ref<Phase>('idle')
// Is a real microphone driving this turn? It decides who gets to END the turn. A spoken turn is
// only over when the DEVICE says so (`done`), because the agent's reply lands on the wire before
// the robot has said a word of it — closing on the reply would drop the screen back to "Đã xong"
// while the robot was still talking. A turn typed straight into the agent has no device to send
// `done`, so there the reply is the end.
const deviceTurn = ref(false)
const heardText = ref('')
const resultText = ref('')
const action = ref('')
// The raw structured action (navigate/lift/control) — drives the big non-text glyph so a room
// that never reads the transcript still sees WHAT the robot was told.
const rawAction = ref<Record<string, any> | null>(null)
// Bumped each time a turn completes, so the one-shot success burst replays on every "done" even
// if two turns both land on the 'result' phase back-to-back.
const burstKey = ref(0)

const speaker = ref(0)
const micLevel = ref(0)
const levelsKnown = ref(false)

// Live fleet telemetry for the robot this screen drives (pin / activity / pose).
const robot = ref<Robot | null>(null)

// The last few turns, newest last, so a demo audience can see what the robot was told.
interface HistoryItem {
  id: number
  heard: string
  answer: string
  action: string
}
const history = ref<HistoryItem[]>([])
let historyId = 0

const view = computed(() => PHASES[phase.value])
const running = computed(() => isRunning(phase.value))

const battery = computed(() => (robot.value?.battery != null ? Math.round(robot.value.battery) : 0))
const batteryColor = computed(() =>
  battery.value > 50 ? 'currentColor' : battery.value > 20 ? '#f59e0b' : '#f87171',
)
const activityLabel = computed(() => {
  const r = robot.value
  if (!r) return ''
  return r.activity || r.status || ''
})

let ws: WsHandle | null = null
let noteTimer: ReturnType<typeof setTimeout> | undefined
let robotTimer: ReturnType<typeof setInterval> | undefined

/** Start of a turn: the previous answer comes off the screen so nobody reads a stale one as
 *  the reply to what they just said. */
function beginTurn() {
  phase.value = 'listening'
  deviceTurn.value = false
  heardText.value = ''
  resultText.value = ''
  action.value = ''
  rawAction.value = null
  note.value = ''
}

function say(text: string) {
  note.value = text
  clearTimeout(noteTimer)
  noteTimer = setTimeout(() => (note.value = ''), 4000)
}

/** Mark the turn complete. Only fires the success burst when we actually enter 'result' (not when
 *  a device 'done' confirms a result already set by a typed reply), so the room feels one pop. */
function completeTurn() {
  if (phase.value !== 'result') burstKey.value++
  phase.value = 'result'
}

/** Device telemetry — the half of a turn only the Jetson can see (mic armed, speech ended,
 *  transcript ready, sentence playing). Everything here is a phase change; the millisecond
 *  fields the device also sends are deliberately ignored on this screen. */
function onDeviceFrame(ev: Record<string, any>) {
  // Two Jetsons on one hub: ignore the one we are not driving. Its turn would drag this screen
  // through phases the operator never triggered, and its levels would yank the two steppers to a
  // machine they don't control.
  if (ev.robot_id && robotId.value && ev.robot_id !== robotId.value) return

  switch (String(ev.stage ?? '')) {
    case 'levels':
      adoptLevels(ev)
      break
    case 'listening':
      beginTurn()
      deviceTurn.value = true
      break
    // Speech ended; Whisper is running. Same phase as the LLM step on purpose — "đang xử lý" is
    // one wait as far as the room is concerned, and splitting it would put a flicker mid-turn.
    case 'transcribing':
    case 'thinking':
      phase.value = 'thinking'
      break
    case 'heard':
      heardText.value = String(ev.text ?? '')
      phase.value = 'thinking'
      break
    case 'speaking':
      phase.value = 'speaking'
      break
    case 'done':
      completeTurn()
      break
    // The next three are the pipeline working correctly on an empty input, not failures — they
    // land on a grey phase, never the red one.
    case 'empty':
      phase.value = 'quiet'
      break
    case 'timeout':
      phase.value = 'quiet'
      say('Không nghe thấy ai nói — bấm ra lệnh lại giúp em.')
      break
    case 'cancelled':
      phase.value = 'idle'
      break
    case 'error':
      // The exception text stays in the console; an audience should not be reading a traceback.
      console.error('[monitor] agent error:', ev.detail)
      phase.value = 'error'
      break
  }
}

/** Agent events — the half only the server can see: the reply and its structured action. */
function onAgentEvent(ev: Record<string, any>) {
  switch (ev.type) {
    case 'voice.heard':
      // Normally the device already told us. This still matters for a turn typed straight into
      // the agent (scripts/text_chat_test.py), where no device is in the loop at all.
      if (!running.value) beginTurn()
      heardText.value = String(ev.text ?? '')
      phase.value = 'thinking'
      break
    case 'voice.progress':
      // Only meaningful inside a turn this screen started. The hub mirrors every voice event to
      // every monitor, so an unguarded progress frame could flip an idle screen to "đang xử lý".
      if (running.value) phase.value = 'thinking'
      break
    case 'voice.reply':
      resultText.value = String(ev.text ?? '')
      action.value = actionLabel(ev.action ?? null)
      // Keep the structured action too: the big glyph reads it so a non-reader sees the robot's
      // job (go to a slot / lift / stop) without a word of the transcript.
      rawAction.value = (ev.action as Record<string, any>) ?? null
      // The answer goes on screen now — the robot is about to say it — but the turn stays open
      // until the device reports it has finished speaking. See `deviceTurn`.
      if (!deviceTurn.value) completeTurn()
      // One line in the command-history strip, so the demo can replay what the robot was told.
      if (resultText.value.trim()) pushHistory(heardText.value, resultText.value, action.value)
      break
  }
}

// Switching mic invalidates the levels: they described the previous Jetson, and leaving them on
// screen would have the operator step a number belonging to a machine they no longer drive.
watch(robotId, () => (levelsKnown.value = false))

function adoptLevels(src: { speaker?: number | null; mic?: number | null; can_set?: boolean }) {
  if (src.can_set === false || src.speaker == null || src.mic == null) {
    levelsKnown.value = false
    return
  }
  speaker.value = src.speaker
  micLevel.value = src.mic
  levelsKnown.value = true
}

async function refreshDevices() {
  try {
    const res = await fetchDevices()
    devices.value = res.devices
    if (!robotId.value && res.devices.length) robotId.value = res.devices[0].robot_id
    if (robotId.value && !res.devices.some((d) => d.robot_id === robotId.value)) {
      robotId.value = res.devices.length ? res.devices[0].robot_id : ''
    }
    // Only until the first real value lands. After that the device's own `levels` frames are the
    // authority — this poll runs every 5 s and must not fight a level the operator just changed.
    if (!levelsKnown.value) {
      const d = res.devices.find((x) => x.robot_id === robotId.value)
      if (d) adoptLevels(d)
    }
  } catch {
    devices.value = []
  }
}

/** Pull the fleet so the telemetry row shows the real robot (pin/activity/pose). The monitor is a
 *  viewer, so it only reads; driving happens elsewhere. */
async function refreshRobot() {
  try {
    const list = await fetchRobots()
    const r = robotId.value ? list.find((x) => x.id === robotId.value) : list[0]
    robot.value = r ?? null
  } catch {
    /* telemetry just stays empty — the demo still runs without it */
  }
}

/** Deliberately understated, and never red: a command that didn't land is nearly always a Jetson
 *  that blinked, and it resolves itself. The operator sees this; the audience doesn't read it. */
function ack(res: { status: string }, okText: string) {
  say(res.status === 'ok' ? okText : 'Robot chưa sẵn sàng — thử lại sau vài giây.')
}

async function onListen() {
  // Show "đang nghe" on the press, not when the device's first frame comes back: the round trip
  // is short but visible, and a button that looks dead for 200ms gets pressed twice.
  beginTurn()
  const res = await startListening(robotId.value)
  if (res.status !== 'ok') {
    phase.value = 'idle'
    ack(res, '')
  }
}

async function onCancel() {
  phase.value = 'idle'
  ack(await cancelTurn(robotId.value), 'Đã dừng lượt này.')
}

async function onNewChat() {
  const res = await newConversation(robotId.value)
  phase.value = 'idle'
  heardText.value = ''
  resultText.value = ''
  action.value = ''
  rawAction.value = null
  ack(res, 'Đã bắt đầu hội thoại mới.')
}

/** Step a level and push it to the Jetson. Optimistic locally so the number moves under the
 *  finger, then corrected by the `levels` frame the device sends after pactl has applied it. */
function bump(target: AudioTarget, delta: number) {
  if (!robotId.value || !levelsKnown.value) return
  const cur = target === 'speaker' ? speaker.value : micLevel.value
  const next = Math.max(0, Math.min(cur + delta, MAX[target]))
  if (next === cur) return
  if (target === 'speaker') speaker.value = next
  else micLevel.value = next
  setAudioLevel(robotId.value, target, next).catch(() => {})
}

function pushHistory(heard: string, answer: string, act: string) {
  history.value.push({ id: historyId++, heard, answer, action: act })
  // Keep the strip bounded: a demo runs for minutes, and an unbounded list would run off-screen.
  if (history.value.length > 10) history.value.splice(0, history.value.length - 10)
}

onMounted(() => {
  refreshDevices()
  refreshRobot()
  // Devices come and go (a Jetson reboot, `make voice` restarted); re-reading keeps the picker
  // honest without needing a page reload mid-demo.
  const poll = setInterval(refreshDevices, 5000)
  robotTimer = setInterval(refreshRobot, 4000)
  ws = connectEvents(
    'monitor',
    (e: any) => {
      if (e?.type === 'voice.device') onDeviceFrame(e)
      else if (typeof e?.type === 'string' && e.type.startsWith('voice.')) onAgentEvent(e)
    },
    (up) => (connected.value = up),
  )
  onUnmounted(() => {
    clearInterval(poll)
    clearInterval(robotTimer)
    clearTimeout(noteTimer)
    ws?.close()
  })
})
</script>
