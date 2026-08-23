<template>
  <div class="rack">
    <header class="masthead">
      <div class="ident">
        <span class="eyebrow">AI WAITER · GIÁM SÁT</span>
        <h1>Đường tín hiệu</h1>
        <p class="sub">Tiếng nói vào ở đầu này, câu trả lời của agent ra ở đầu kia.</p>
      </div>

      <div class="console">
        <div class="link" :class="{ on: connected }">
          <span class="pip"></span>{{ connected ? 'Hub realtime' : 'Mất kết nối hub' }}
        </div>

        <label class="pick">
          <span>Thiết bị</span>
          <select v-model="robotId" :disabled="!devices.length">
            <option v-if="!devices.length" value="">chưa có mic nào</option>
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

    <div class="controls">
      <button class="act primary" :disabled="!robotId || turnRunning" @click="onListen">
        Bắt đầu nghe
      </button>
      <button class="act" :disabled="!robotId || !turnRunning" @click="onCancel">Dừng</button>
      <button class="act" :disabled="!robotId" @click="onNewChat">Hội thoại mới</button>
      <button class="act" :disabled="!robotId" :class="{ armed: muted }" @click="onToggleMute">
        {{ muted ? 'Bật loa' : 'Tắt loa' }}
      </button>
      <span v-if="commandNote" class="note" :class="{ bad: commandBad }">{{ commandNote }}</span>
      <span class="spacer"></span>
      <span class="live" :class="{ on: turnRunning }">
        <template v-if="turnRunning">Lượt đang chạy · {{ fmtMs(elapsed) }}</template>
        <template v-else>Chờ lệnh</template>
      </span>

      <p v-if="!devices.length" class="hookup">
        Chưa thấy mic nào. Trên Jetson chạy <code>make voice</code>, và kiểm tra
        <code>ORCHESTRATOR_URL</code> trong <code>.env</code> của Jetson trỏ về máy chủ này.
      </p>
    </div>

    <SignalChain :stages="stages" :active="activeStage" />

    <div class="floor">
      <Conversation :turns="turns" :live="liveTurn" :ready="devices.length > 0" />
      <div class="right">
        <TurnLedger :turns="turns" />
        <EventLog :lines="log" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { connectEvents, type WsHandle } from '@shared/ws'
import Conversation from './components/Conversation.vue'
import EventLog from './components/EventLog.vue'
import SignalChain from './components/SignalChain.vue'
import TurnLedger from './components/TurnLedger.vue'
import {
  cancelTurn,
  fetchDevices,
  newConversation,
  setMuted,
  startListening,
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
const commandBad = ref(false)

const stages = reactive(blankStages())
const activeStage = ref<StageId | null>(null)
const turns = ref<TurnRecord[]>([])
const log = ref<LogLine[]>([])

// The turn being assembled right now. Null between turns — which is also what tells the UI
// whether "Dừng" can do anything.
const liveTurn = ref<Partial<TurnRecord> & { replyParts: string[] } | null>(null)
const turnRunning = computed(() => liveTurn.value !== null)
const elapsed = ref(0)

let logSeq = 0
let turnSeq = 0
let turnStartedAt = 0
let ticker: ReturnType<typeof setInterval> | undefined
let ws: WsHandle | null = null

function addLog(source: LogLine['source'], text: string, tone: LogLine['tone'] = 'plain') {
  log.value.unshift({ id: ++logSeq, at: new Date(), source, text, tone })
  // The log is evidence, not history: keep it short enough that the newest line is always the
  // top one on screen, and let the ledger carry what actually needs to persist.
  if (log.value.length > 60) log.value.length = 60
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
  liveTurn.value = null
  activeStage.value = null
  if (!t) return
  // A turn that never got as far as a transcript has nothing to compare against the others, so
  // it is logged but kept out of the ledger — an empty bar there would read as a fast turn.
  if (!t.heard && outcome !== 'ok') return
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
  })
  if (turns.value.length > 40) turns.value.length = 40
}

/** Device telemetry — the half of the turn only the Jetson can see. */
function onDeviceFrame(ev: Record<string, any>) {
  const stage = String(ev.stage ?? '')
  switch (stage) {
    case 'listening':
      beginTurn()
      setStage('mic', 'active', 'đang thu', 'mic mở')
      setStage('vad', 'active', 'chờ tiếng nói')
      addLog('device', 'mic mở — chờ khách nói', 'signal')
      break

    case 'transcribing':
      setStage('mic', 'done', 'xong')
      setStage('vad', 'done', fmtMs(ev.speech_ms), 'độ dài câu nói')
      setStage('stt', 'active', 'đang chép', 'PhoWhisper medium')
      if (liveTurn.value) liveTurn.value.speechMs = ev.speech_ms
      addLog('device', `hết tiếng nói sau ${fmtMs(ev.speech_ms)} — đưa sang Whisper`)
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

    case 'empty':
      setStage('stt', 'fault', 'không dùng được', 'im lặng, hoặc câu bịa đã bị lọc')
      addLog('device', 'Whisper không trả về câu nào dùng được', 'fault')
      endTurn('empty')
      break

    case 'timeout':
      setStage('mic', 'fault', 'không nghe thấy', `chờ ${fmtMs(ev.waited_ms)}`)
      setStage('vad', 'idle')
      addLog('device', 'hết giờ chờ — không có ai nói', 'fault')
      endTurn('timeout')
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

    case 'cancelled':
      addLog('device', `khách bấm dừng (${ev.at ?? '?'})`, 'fault')
      for (const id of Object.keys(stages) as StageId[]) {
        if (stages[id].state === 'active') setStage(id, 'fault', 'đã dừng')
      }
      endTurn('cancelled')
      break

    case 'muted':
      muted.value = Boolean(ev.muted)
      addLog('device', ev.muted ? 'tắt loa' : 'bật loa')
      break

    case 'error':
      setStage('agent', 'fault', 'lỗi', String(ev.detail ?? ''))
      addLog('device', `lỗi gọi agent: ${ev.detail}`, 'fault')
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

async function refreshDevices() {
  try {
    const res = await fetchDevices()
    devices.value = res.devices
    if (!robotId.value && res.devices.length) robotId.value = res.devices[0].robot_id
    if (!tableId.value) tableId.value = res.default_table_id
  } catch {
    devices.value = []
  }
}

function ack(res: { status: string }, okText: string) {
  commandBad.value = res.status !== 'ok'
  commandNote.value =
    res.status === 'ok' ? okText : 'Mic không nhận lệnh — Jetson chưa kết nối hub.'
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
  log.value = []
  resetStages()
  ack(res, 'Đã xoá trí nhớ hội thoại của bàn này.')
}
async function onToggleMute() {
  const next = !muted.value
  const res = await setMuted(robotId.value, tableId.value, next)
  if (res.status === 'ok') muted.value = next
  ack(res, next ? 'Đã tắt loa robot.' : 'Đã bật loa robot.')
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
