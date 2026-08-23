<template>
  <div class="rack">
    <header class="masthead">
      <div class="ident">
        <span class="eyebrow">AI WAITER · GIÁM SÁT</span>
        <h1>Đường tín hiệu</h1>
        <p class="sub">Tiếng nói vào ở đầu này, câu trả lời của agent ra ở đầu kia.</p>
      </div>

      <div class="console">
        <!-- Calm on purpose. This used to go alarm-red the moment the socket blinked, which an
             audience reads as a crash — the client reconnects on its own within seconds. The
             technical wording lives in the tooltip, for whoever is actually operating it. -->
        <div class="link" :class="{ on: connected }" :title="linkDetail">
          <span class="pip"></span>{{ connected ? 'Hub realtime' : 'Đang kết nối…' }}
        </div>

        <label class="pick">
          <span>Thiết bị</span>
          <select v-model="robotId" :disabled="!devices.length" :title="deviceHint">
            <option v-if="!devices.length" value="">chưa có mic</option>
            <option v-for="d in devices" :key="d.robot_id" :value="d.robot_id">
              {{ d.robot_id }}
            </option>
          </select>
        </label>

        <label class="pick">
          <span>Bàn</span>
          <input v-model.number="tableId" type="number" min="1" max="6" />
        </label>
      </div>
    </header>

    <SignalChain :stages="stages" :active="activeStage" />

    <div class="floor">
      <Timeline :turns="turns" :live="liveTurn" :live-log="liveLog" :ready="devices.length > 0" />

      <!-- The operator's side. Everything a finger touches during the demo lives in this rail,
           at touch-target scale; the reading panels paid for it with their width. -->
      <aside class="rail">
        <div class="status">
          <span v-if="commandNote" class="note">{{ commandNote }}</span>
          <span v-else class="live" :class="{ on: turnRunning }">
            <template v-if="turnRunning">Lượt đang chạy · {{ fmtMs(elapsed) }}</template>
            <template v-else>Chờ lệnh</template>
          </span>
        </div>

        <div class="pad">
          <button class="act primary wide" :disabled="!robotId || turnRunning" @click="onListen">
            Bắt đầu nghe
          </button>
          <button class="act" :disabled="!robotId || !turnRunning" @click="onCancel">Dừng</button>
          <button class="act" :disabled="!robotId" :class="{ armed: muted }" @click="onToggleMute">
            {{ muted ? 'Bật loa' : 'Tắt loa' }}
          </button>
          <button class="act wide" :disabled="!robotId" @click="onNewChat">Hội thoại mới</button>
        </div>

        <!-- The two sliders drive pactl on the Jetson, not a gain in this page. `levelsKnown` is
             false until the device has reported real values; a slider that looks live but moves
             nothing is worse than one that is visibly out of service. -->
        <div class="dials">
          <label class="dial" :class="{ off: !levelsKnown }">
            <span class="cap">Loa</span>
            <input
              type="range" min="0" max="100" step="5"
              :disabled="!levelsKnown"
              :value="speaker"
              @input="onLevel('speaker', $event)"
            />
            <span class="val">{{ levelsKnown ? `${speaker}%` : '—' }}</span>
          </label>

          <label class="dial" :class="{ off: !levelsKnown }">
            <span class="cap">Mic</span>
            <input
              type="range" min="0" max="150" step="5"
              :disabled="!levelsKnown"
              :value="micLevel"
              @input="onLevel('mic', $event)"
            />
            <span class="val">{{ levelsKnown ? `${micLevel}%` : '—' }}</span>
          </label>
        </div>

        <TurnLedger :turns="turns" />
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { connectEvents, type WsHandle } from '@shared/ws'
import SignalChain from './components/SignalChain.vue'
import Timeline from './components/Timeline.vue'
import TurnLedger from './components/TurnLedger.vue'
import {
  cancelTurn,
  fetchDevices,
  newConversation,
  setAudioLevel,
  setMuted,
  startListening,
  type AudioTarget,
  type VoiceDevice,
} from './api'
import {
  blankStages,
  fmtMs,
  type LogLine,
  type StageId,
  type StageState,
  type TurnRecord,
} from './pipeline'

const connected = ref(false)
const devices = ref<VoiceDevice[]>([])
const robotId = ref('')
const tableId = ref(1)
const muted = ref(false)
const commandNote = ref('')

// Speaker / mic levels as pactl on the Jetson reports them. `levelsKnown` gates the sliders:
// until a device has actually told us where they sit, there is nothing honest to render.
const speaker = ref(0)
const micLevel = ref(0)
const levelsKnown = ref(false)

const stages = reactive(blankStages())
const activeStage = ref<StageId | null>(null)
const turns = ref<TurnRecord[]>([])
// Frames of the turn in flight. They move into that turn's record when it closes, so the feed
// can show each turn's own evidence under it instead of a separate log running alongside.
const liveLog = ref<LogLine[]>([])

// The turn being assembled right now. Null between turns — which is also what tells the UI
// whether "Dừng" can do anything.
const liveTurn = ref<Partial<TurnRecord> & { replyParts: string[] } | null>(null)
const turnRunning = computed(() => liveTurn.value !== null)
const elapsed = ref(0)

const linkDetail = computed(() =>
  connected.value
    ? 'Đã nối tới hub realtime của server.'
    : 'Chưa nối được hub. Kiểm tra make backend trên server và mạng Netbird — trang tự thử lại.',
)
const deviceHint = computed(() =>
  devices.value.length
    ? 'Mic đang kết nối tới hub.'
    : 'Chưa mic nào kết nối. Trên Jetson chạy make voice, và kiểm tra ORCHESTRATOR_URL trong .env của Jetson.',
)

let logSeq = 0
let turnSeq = 0
let turnStartedAt = 0
let ticker: ReturnType<typeof setInterval> | undefined
let ws: WsHandle | null = null

function addLog(source: LogLine['source'], text: string, tone: LogLine['tone'] = 'plain') {
  liveLog.value.push({ id: ++logSeq, at: new Date(), source, text, tone })
  // A turn's own frame list, not a running log: it is bounded by the turn, and a runaway stream
  // of frames between turns must not be able to grow without limit.
  if (liveLog.value.length > 40) liveLog.value.splice(0, liveLog.value.length - 40)
}

function setStage(id: StageId, state: StageState, readout?: string, detail?: string) {
  stages[id].state = state
  if (readout !== undefined) stages[id].readout = readout
  if (detail !== undefined) stages[id].detail = detail
  if (state === 'active') activeStage.value = id
}

function resetStages() {
  const fresh = blankStages()
  for (const id of Object.keys(stages) as StageId[]) Object.assign(stages[id], fresh[id])
  activeStage.value = null
}

function beginTurn() {
  resetStages()
  liveTurn.value = { replyParts: [], sentences: 0 }
  liveLog.value = []
  turnStartedAt = Date.now()
  elapsed.value = 0
  clearInterval(ticker)
  ticker = setInterval(() => {
    elapsed.value = Date.now() - turnStartedAt
  }, 100)
}

function endTurn(outcome: TurnRecord['outcome'], note?: string) {
  clearInterval(ticker)
  const t = liveTurn.value
  const frames = liveLog.value
  liveTurn.value = null
  liveLog.value = []
  activeStage.value = null
  if (!t) return
  // A turn that never got as far as a transcript has nothing to compare against the others, so
  // it is kept out of the ledger's bars — but it still earns a feed entry now that the feed is
  // the only place the frames live. Dropping it would silently swallow "nobody spoke".
  turns.value.unshift({
    n: ++turnSeq,
    at: new Date(),
    heard: t.heard ?? '',
    reply: t.reply ?? t.replyParts.join(' '),
    stage: t.stage ?? null,
    speechMs: t.speechMs,
    sttMs: t.sttMs,
    firstSentenceMs: t.firstSentenceMs,
    llmTotalMs: t.llmTotalMs,
    turnMs: t.turnMs,
    sentences: t.sentences ?? 0,
    outcome,
    note,
    log: frames,
  })
  if (turns.value.length > 30) turns.value.length = 30
}

/** Device telemetry — the half of the turn only the Jetson can see. */
function onDeviceFrame(ev: Record<string, any>) {
  const stage = String(ev.stage ?? '')
  switch (stage) {
    case 'levels':
      // State, not an event: where this mic's mixer actually sits. Only adopt it for the device
      // the operator is driving, or a second Jetson would yank the sliders under their finger.
      if (ev.robot_id && robotId.value && ev.robot_id !== robotId.value) break
      adoptLevels(ev)
      break

    case 'listening':
      beginTurn()
      setStage('mic', 'active', 'đang thu', 'mic mở')
      setStage('vad', 'active', 'chờ tiếng nói')
      addLog('device', 'mic mở — chờ khách nói', 'signal')
      break

    case 'transcribing':
      setStage('mic', 'done', 'xong')
      setStage('vad', 'done', fmtMs(ev.speech_ms), 'độ dài câu nói')
      // Detail deliberately blank. It used to name the speech model; the readout above already
      // says what is happening, and the audience has no business knowing what is under it.
      setStage('stt', 'active', 'đang chép', '')
      if (liveTurn.value) liveTurn.value.speechMs = ev.speech_ms
      addLog('device', `hết tiếng nói sau ${fmtMs(ev.speech_ms)} — đưa sang bộ chép lời`)
      break

    case 'heard':
      setStage('stt', 'done', fmtMs(ev.stt_ms), `${ev.audio_s}s tiếng → ${ev.text?.length ?? 0} ký tự`)
      setStage('agent', 'active', 'đang nghĩ')
      if (liveTurn.value) {
        liveTurn.value.sttMs = ev.stt_ms
        liveTurn.value.heard = ev.text
      }
      addLog('device', `chép được: “${ev.text}” (${fmtMs(ev.stt_ms)})`, 'signal')
      break

    // The next three are the pipeline working correctly on an empty input, not failures — they
    // land on `quiet`, which is grey. Only the agent error below is allowed to go red.
    case 'empty':
      setStage('stt', 'quiet', 'không nghe rõ', 'im lặng, hoặc câu bịa đã bị lọc')
      addLog('device', 'không chép được câu nào dùng được')
      endTurn('empty')
      break

    case 'timeout':
      setStage('mic', 'quiet', 'không có ai nói', `chờ ${fmtMs(ev.waited_ms)}`)
      setStage('vad', 'idle')
      addLog('device', 'hết giờ chờ — không có ai nói')
      endTurn('timeout')
      break

    case 'cancelled':
      addLog('device', 'đã dừng lượt theo lệnh')
      for (const id of Object.keys(stages) as StageId[]) {
        if (stages[id].state === 'active') setStage(id, 'quiet', 'đã dừng')
      }
      endTurn('cancelled')
      break

    case 'thinking':
      setStage('agent', 'active', 'đang nghĩ', 'LLM đang chạy')
      break

    case 'speaking':
      setStage('agent', 'done')
      setStage('tts', 'active', `câu ${Number(ev.index ?? 0) + 1}`, ev.muted ? 'loa đang tắt' : ev.text)
      if (ev.muted !== undefined && ev.muted !== null) muted.value = Boolean(ev.muted)
      addLog('device', `phát tiếng: “${ev.text}”`, 'signal')
      break

    case 'done':
      setStage('tts', 'done', fmtMs(ev.turn_ms), `${ev.sentences} câu · ${ev.dialog_stage ?? ''}`)
      if (liveTurn.value) {
        liveTurn.value.turnMs = ev.turn_ms
        liveTurn.value.sentences = ev.sentences
        liveTurn.value.stage = ev.dialog_stage
      }
      addLog('device', `xong lượt trong ${fmtMs(ev.turn_ms)}`, 'signal')
      endTurn('ok')
      break

    case 'muted':
      muted.value = Boolean(ev.muted)
      addLog('device', ev.muted ? 'tắt loa' : 'bật loa')
      break

    case 'error':
      // The one real failure. Even here the exception text stays out of the readout and goes in
      // the tooltip + the console — an audience should not be reading a Python traceback.
      setStage('agent', 'fault', 'chưa trả lời được', 'thử lại lượt này')
      console.error('[monitor] agent error:', ev.detail)
      addLog('agent', 'agent không trả lời được lượt này', 'fault')
      endTurn('error', String(ev.detail ?? ''))
      break

    default:
      addLog('device', `${stage}`)
  }
}

/** Agent bridge events — the half only the server can see. */
function onAgentEvent(ev: Record<string, any>) {
  switch (ev.type) {
    case 'voice.heard':
      // Normally the device already told us. This still matters for a turn typed straight into
      // the agent (scripts/text_chat_test.py), where there is no device in the loop at all.
      if (!liveTurn.value) {
        beginTurn()
        setStage('agent', 'active', 'đang nghĩ', 'lượt gõ tay, không qua mic')
      }
      if (liveTurn.value && !liveTurn.value.heard) liveTurn.value.heard = ev.text
      break

    case 'voice.progress':
      setStage('agent', 'active', 'đang nghĩ', String(ev.status ?? ''))
      break

    case 'voice.sentence':
      if (liveTurn.value) {
        liveTurn.value.replyParts.push(ev.text)
        if (liveTurn.value.firstSentenceMs == null) {
          liveTurn.value.firstSentenceMs = ev.timings?.at_ms
        }
      }
      setStage('agent', 'active', fmtMs(ev.timings?.at_ms), `câu ${Number(ev.index ?? 0) + 1} đã xong`)
      addLog('agent', `câu ${Number(ev.index ?? 0) + 1}: “${ev.text}”`, 'signal')
      break

    case 'voice.reply':
      if (liveTurn.value) {
        liveTurn.value.reply = ev.text
        liveTurn.value.stage = ev.stage
        liveTurn.value.firstSentenceMs ??= ev.timings?.first_sentence
        liveTurn.value.llmTotalMs = ev.timings?.llm_total
      }
      setStage('agent', 'done', fmtMs(ev.timings?.llm_total), `giai đoạn ${ev.stage}`)
      addLog(
        'agent',
        `trả lời xong · ${fmtMs(ev.timings?.llm_total)} · ${ev.stage}` +
          (ev.action ? ` · hành động: ${ev.action.type ?? JSON.stringify(ev.action)}` : ''),
        'signal',
      )
      // A typed turn has no device to send `done`, so close it here if one is still open by the
      // time the reply lands. A spoken turn is still open on purpose — the robot is talking.
      if (liveTurn.value && stages.tts.state === 'idle') endTurn('ok')
      break
  }
}

// Switching to another mic invalidates the sliders: they were showing the previous Jetson's
// levels, and silently leaving them there would have the operator drag a number that belongs to
// a machine they are no longer driving. Dropping the flag makes the next poll re-adopt.
watch(robotId, () => (levelsKnown.value = false))

/** Take mixer levels from a device frame or a /devices row. */
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
    if (!tableId.value) tableId.value = res.default_table_id
    // Only until the first real value lands. After that the device's own `levels` frames are the
    // authority — this poll runs every 5 s and would otherwise fight a slider mid-drag.
    if (!levelsKnown.value) {
      const d = res.devices.find((x) => x.robot_id === robotId.value)
      if (d) adoptLevels(d)
    }
  } catch {
    devices.value = []
  }
}

function ack(res: { status: string }, okText: string) {
  // Deliberately understated, and never red: a command that didn't land is nearly always a
  // Jetson that blinked, and it resolves itself. The operator sees it; the audience doesn't read it.
  commandNote.value = res.status === 'ok' ? okText : 'Robot chưa sẵn sàng.'
  setTimeout(() => (commandNote.value = ''), 4000)
}

async function onListen() {
  ack(await startListening(robotId.value, tableId.value), 'Đã bảo robot nghe.')
}
async function onCancel() {
  ack(await cancelTurn(robotId.value, tableId.value), 'Đã dừng lượt.')
}
async function onNewChat() {
  const res = await newConversation(robotId.value, tableId.value)
  turns.value = []
  liveLog.value = []
  resetStages()
  ack(res, 'Đã xoá trí nhớ hội thoại của bàn này.')
}
async function onToggleMute() {
  const next = !muted.value
  const res = await setMuted(robotId.value, tableId.value, next)
  if (res.status === 'ok') muted.value = next
  ack(res, next ? 'Đã tắt loa robot.' : 'Đã bật loa robot.')
}

// Slider moves are optimistic locally so the handle tracks the finger, then corrected by the
// `levels` frame the device sends back after pactl has actually clamped and applied it.
function onLevel(target: AudioTarget, e: Event) {
  const pct = Number((e.target as HTMLInputElement).value)
  if (target === 'speaker') speaker.value = pct
  else micLevel.value = pct
  if (!robotId.value) return
  setAudioLevel(robotId.value, target, pct).catch(() => {})
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
    clearInterval(ticker)
    ws?.close()
  })
})
</script>
