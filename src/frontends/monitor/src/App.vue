<template>
  <div class="screen" :style="{ '--state': view.color }">
    <!-- The header carries everything that is true all the time and interesting to nobody:
         who this is, whether the hub is up, which mic we are driving. It gets one line. -->
    <header class="top">
      <div class="ident">
        <span class="mark" aria-hidden="true"></span>
        <span class="name">TRỢ LÝ ROBOT KHO</span>
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

      <VoiceWave class="wave-box" :phase="phase" :color="view.color" />

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
        <span class="cap">Mic</span>
        <button class="step" :disabled="!levelsKnown" @click="bump('mic', -10)">−</button>
        <span class="val">{{ levelsKnown ? `${micLevel}%` : '—' }}</span>
        <button class="step" :disabled="!levelsKnown" @click="bump('mic', 10)">+</button>
      </div>

      <div class="dial" :class="{ off: !levelsKnown }">
        <span class="cap">Loa</span>
        <button class="step" :disabled="!levelsKnown" @click="bump('speaker', -10)">−</button>
        <span class="val">{{ levelsKnown ? `${speaker}%` : '—' }}</span>
        <button class="step" :disabled="!levelsKnown" @click="bump('speaker', 10)">+</button>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { connectEvents, type WsHandle } from '@shared/ws'
import RobotAvatar from './components/RobotAvatar.vue'
import VoiceWave from './components/VoiceWave.vue'
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
const tableId = ref<number | null>(null) // which conversation thread the agent files turns under
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

const speaker = ref(0)
const micLevel = ref(0)
const levelsKnown = ref(false)

const view = computed(() => PHASES[phase.value])
const running = computed(() => isRunning(phase.value))

let ws: WsHandle | null = null
let noteTimer: ReturnType<typeof setTimeout> | undefined

/** Start of a turn: the previous answer comes off the screen so nobody reads a stale one as
 *  the reply to what they just said. */
function beginTurn() {
  phase.value = 'listening'
  deviceTurn.value = false
  heardText.value = ''
  resultText.value = ''
  action.value = ''
  note.value = ''
}

function say(text: string) {
  note.value = text
  clearTimeout(noteTimer)
  noteTimer = setTimeout(() => (note.value = ''), 4000)
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
      phase.value = 'result'
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
      // The answer goes on screen now — the robot is about to say it — but the turn stays open
      // until the device reports it has finished speaking. See `deviceTurn`.
      if (!deviceTurn.value) phase.value = 'result'
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
    if (tableId.value == null) tableId.value = res.default_table_id
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

/** Deliberately understated, and never red: a command that didn't land is nearly always a Jetson
 *  that blinked, and it resolves itself. The operator sees this; the audience doesn't read it. */
function ack(res: { status: string }, okText: string) {
  say(res.status === 'ok' ? okText : 'Robot chưa sẵn sàng — thử lại sau vài giây.')
}

async function onListen() {
  // Show "đang nghe" on the press, not when the device's first frame comes back: the round trip
  // is short but visible, and a button that looks dead for 200ms gets pressed twice.
  beginTurn()
  const res = await startListening(robotId.value, tableId.value ?? undefined)
  if (res.status !== 'ok') {
    phase.value = 'idle'
    ack(res, '')
  }
}

async function onCancel() {
  phase.value = 'idle'
  ack(await cancelTurn(robotId.value, tableId.value ?? undefined), 'Đã dừng lượt này.')
}

async function onNewChat() {
  const res = await newConversation(robotId.value, tableId.value ?? undefined)
  phase.value = 'idle'
  heardText.value = ''
  resultText.value = ''
  action.value = ''
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

onMounted(() => {
  refreshDevices()
  // Devices come and go (a Jetson reboot, `make voice` restarted); re-reading keeps the picker
  // honest without needing a page reload mid-demo.
  const poll = setInterval(refreshDevices, 5000)
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
    clearTimeout(noteTimer)
    ws?.close()
  })
})
</script>
