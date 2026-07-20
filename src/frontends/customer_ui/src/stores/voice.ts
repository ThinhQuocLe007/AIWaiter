import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useCartStore } from '@/stores/cart'
import { useMenuStore } from '@/stores/menu'
import { getStoredTableId } from '@/data/tableSession'
import {
  startVoiceListen,
  cancelVoiceListen,
  setVoiceMuted,
  newVoiceChat,
  createPayment,
} from '@/data/api'
import router from '@/router'
import { connectEvents, type WsHandle } from '@shared/ws'
import type { UiAction, VoiceCartItem, WsEvent } from '@shared/types'

// AI assistant lifecycle:
// - 'idle': nothing happening
// - 'listening': the robot is capturing the guest's speech (orb animates) — only shown if the
//   server emits it; the mic lives on the robot, not this tablet
// - 'thinking': the server heard us and is running STT/LLM (loading dots)
// - 'speaking': the robot is replying with advice / an action
export type AiState = 'idle' | 'listening' | 'thinking' | 'speaking'

export interface ChatMessage {
  id: number
  role: 'user' | 'ai'
  text: string
}

// How long to keep the 'speaking' state lit after a reply before settling back to idle. The real
// audio plays on the robot's speaker (we don't get a "done" signal), so this is just a UI hint.
const SPEAKING_HOLD_MS = 4000

export const useVoiceStore = defineStore('voice', () => {
  const isAiOpen = ref(false)
  const aiState = ref<AiState>('idle')
  const speechText = ref('')
  const aiResponse = ref('')
  const isSoundEnabled = ref(true)
  const messages = ref<ChatMessage[]>([])

  let messageId = 0
  let wsHandle: WsHandle | null = null
  let speakingTimer: ReturnType<typeof setTimeout> | undefined
  // "Hủy" was pressed for the turn in flight: swallow its voice.heard/voice.reply when (if)
  // they arrive, so a cancelled utterance never shows up nor mutates the cart. Cleared when
  // the suppressed reply lands, or when the guest deliberately starts a new turn.
  let suppressTurn = false

  function pushMessage(role: ChatMessage['role'], text: string) {
    messages.value.push({ id: messageId++, role, text })
  }

  // Subscribe to the backend voice mirror (role=customer). Idempotent: connecting once on app
  // mount is enough — the panel auto-opens when the robot hears this table speak.
  function connect() {
    if (wsHandle) return
    wsHandle = connectEvents('customer', onEvent)
  }

  function disconnect() {
    wsHandle?.close()
    wsHandle = null
  }

  function onEvent(e: WsEvent) {
    // Only react to voice events meant for the table this tablet is standing in for.
    if (e.type === 'voice.heard') {
      if (e.table_id !== getStoredTableId()) return
      onHeard(e.text)
    } else if (e.type === 'voice.reply') {
      if (e.table_id !== getStoredTableId()) return
      onReply(e.text, e.action, e.stage, e.cart, e.confirmed ?? false, e.cart_touched ?? false)
    } else if (e.type === 'voice.progress') {
      if (e.table_id !== getStoredTableId()) return
      aiState.value = 'thinking'
    } else if (e.type === 'robot.arrived') {
      // The robot is standing at this table now: bring the tablet to the screen matching the
      // visit step, so the guest never has to navigate by hand. go_to_table = fresh party →
      // straight to the menu; call = mid-meal service → the "order more / pay" chooser.
      // deliver needs no screen change (the guest just takes the food).
      if (e.table_id !== getStoredTableId()) return
      if (e.kind === 'go_to_table' && router.currentRoute.value.name !== 'menu') {
        router.push({ name: 'menu' })
      } else if (e.kind === 'call' && router.currentRoute.value.name !== 'service') {
        router.push({ name: 'service' })
      }
    } else if (e.type === 'table.updated') {
      // Session lifecycle for THIS table: paid (DA_THANH_TOAN) or ended from the panel (TRONG)
      // means the visit is over — the dishes must leave the cart card, no matter where the
      // payment was confirmed (tablet, voice agent, or panel).
      if (e.table.id !== getStoredTableId()) return
      if (e.table.status === 'DA_THANH_TOAN' || e.table.status === 'TRONG') {
        endSession()
      }
    } else if (e.type === 'reset') {
      // Panel-side system reset: every session is gone — wipe EVERY table's persisted cart
      // bucket (not just the active one) plus the conversation.
      useCartStore().clearAllTables()
      resetConversation()
    }
  }

  // The visit is over (paid / table ended / system reset): clear the persisted cart AND the
  // conversation, so the next guest at this table starts from zero.
  function endSession() {
    useCartStore().clearAll()
    resetConversation()
  }

  // Drop the visible conversation only (e.g. the operator switched the tablet to another table —
  // the chat on screen belonged to the previous table). The cart is handled separately: it swaps
  // per-table buckets in the cart store rather than being wiped.
  function resetConversation() {
    clearTimeout(speakingTimer)
    messages.value = []
    suppressTurn = false
    closePanel()
  }

  // The robot heard the guest: surface the words immediately and show "thinking" while the
  // server runs the LLM. Auto-open the panel so the guest sees the conversation start.
  function onHeard(text: string) {
    // A cancelled utterance that slipped past the device-side abort: don't show it.
    if (suppressTurn) return
    clearTimeout(speakingTimer)
    isAiOpen.value = true
    aiState.value = 'thinking'
    speechText.value = text
    if (text.trim()) pushMessage('user', text)
  }

  // The agent replied: show the spoken text, mirror its cart into the web cart, and follow any
  // UI action (open the menu / the bill).
  function onReply(
    text: string,
    action: UiAction | null,
    stage?: string,
    voiceCart?: VoiceCartItem[] | null,
    confirmed = false,
    cartTouched = false,
  ) {
    // The guest cancelled this turn: swallow the reply entirely (no bubble, no cart change,
    // no navigation) and re-arm for the next turn.
    if (suppressTurn) {
      suppressTurn = false
      return
    }
    aiState.value = 'speaking'
    aiResponse.value = text
    if (text.trim()) pushMessage('ai', text)
    syncCart(voiceCart, confirmed, cartTouched)
    applyAction(action)
    clearTimeout(speakingTimer)
    speakingTimer = setTimeout(() => {
      if (aiState.value === 'speaking') aiState.value = 'idle'
    }, SPEAKING_HOLD_MS)
  }

  // Mirror the agent's cart into the tablet cart so both stay one cart:
  // - on a turn that actually changed the agent's cart (`cartTouched`) → its draft REPLACES the
  //   web draft;
  // - on the turn the order was sent to the kitchen (`confirmed`) → move it into the
  //   "đã gửi bếp" list, so closing the voice sheet keeps the dishes on the cart card;
  // - any other turn (a search, plain chat, post-confirm smalltalk) leaves the web cart alone.
  //
  // The gate used to be `stage === 'DRAFTING' | 'AWAITING_CONFIRMATION'`, but the stage is
  // STICKY: it stays AWAITING_CONFIRMATION across later search/chat turns, so every one of them
  // replayed the agent's cart and silently undid whatever the guest had since added by hand.
  // `cartTouched` is per-turn, so it can't. Manual edits travel the other way (cart store →
  // POST /voice/cart), which is what keeps the agent's copy worth mirroring in the first place.
  async function syncCart(
    voiceCart?: VoiceCartItem[] | null,
    confirmed = false,
    cartTouched = false,
  ) {
    const cart = useCartStore()
    const menu = useMenuStore()
    const applyDraft = async (items: VoiceCartItem[]) => {
      if (menu.foodItems.length === 0) await menu.loadMenu() // need prices/images to map names
      cart.syncFromVoice(items, menu.foodItems)
    }
    if (confirmed) {
      // Prefer the agent's authoritative list (covers a reloaded tablet with an empty draft).
      if (voiceCart && voiceCart.length > 0) await applyDraft(voiceCart)
      // push: false — the agent confirmed this itself; don't echo an empty cart back at it.
      cart.markOrdered({ push: false })
    } else if (cartTouched && Array.isArray(voiceCart)) {
      await applyDraft(voiceCart)
    }
  }

  // Mirror the agent's tablet command: a successful order step opens the menu, a payment request
  // brings up the bill. Guarded so we don't re-navigate to the screen we're already on.
  async function applyAction(action: UiAction | null) {
    if (!action) return
    if (action.action === 'open_payment') {
      if (router.currentRoute.value.name === 'payment') return
      // The agent already opened the gộp payment server-side; fetch it (idempotent) so we can carry
      // its amount + QR + id to the payment screen as query params — the same shape the manual
      // "Thanh toán" button passes. Without this the screen reads no amount and shows 0đ.
      try {
        const payment = await createPayment(getStoredTableId())
        router.push({
          name: 'payment',
          query: {
            amount: String(payment.amount),
            qrUrl: payment.qr_url ?? '',
            paymentId: String(payment.id),
          },
        })
      } catch {
        router.push({ name: 'payment' })  // still show the screen; better than staying put
      }
      return
    }
    if (action.action === 'open_menu' && router.currentRoute.value.name !== 'menu') {
      router.push({ name: 'menu' })
    }
  }

  function openPanel() {
    connect()
    isAiOpen.value = true
  }

  // Close the sheet WITHOUT forgetting anything: the conversation stays (reopening shows the
  // robot still remembers the order — its memory lives server-side per session anyway) and the
  // cart is untouched (it lives in the cart store, synced + persisted).
  function closePanel() {
    clearTimeout(speakingTimer)
    isAiOpen.value = false
    aiState.value = 'idle'
    speechText.value = ''
    aiResponse.value = ''
  }

  // Speaker toggle — not just a local flag: it mutes the robot's actual TTS output (the audio
  // plays on the robot's Jetson, not this tablet). Muting cuts the sentence currently playing;
  // best-effort when no robot is at the table (the flag still drives the next turn's state).
  async function toggleSound() {
    isSoundEnabled.value = !isSoundEnabled.value
    // Say so when the command didn't reach a robot. The toggle used to swallow every failure,
    // so a guest at a table with no robot bound saw the icon flip and the speaker keep talking,
    // with nothing on screen explaining why — indistinguishable from a dead button.
    try {
      const res = await setVoiceMuted(getStoredTableId(), !isSoundEnabled.value)
      if (res.status === 'no_device') pushMessage('ai', 'Chưa kết nối được loa của robot ạ.')
    } catch {
      pushMessage('ai', 'Chưa đổi được chế độ loa ạ, anh/chị thử lại nhé.')
    }
  }

  // The "talk to AI" / "Nói tiếp" button. The mic lives on the table's voice device (Jetson/laptop),
  // not this tablet — so we don't record here. We tell the backend to signal that device to start
  // listening; it then does mic → STT → agent, and the turn comes back over the voice bridge
  // (onHeard/onReply). Light the orb optimistically; if no device is connected, settle back to idle.
  async function startListening() {
    clearTimeout(speakingTimer)
    connect()
    suppressTurn = false // a new deliberate turn always shows its own transcript + reply
    aiState.value = 'listening'
    // Re-sync the speaker preference first: the device may have (re)connected after the guest
    // toggled it, and its own mute flag lives in device RAM.
    setVoiceMuted(getStoredTableId(), !isSoundEnabled.value).catch(() => {})
    try {
      const res = await startVoiceListen(getStoredTableId())
      if (res.status === 'no_device') {
        aiState.value = 'idle'
        pushMessage('ai', 'Trợ lý giọng nói chưa sẵn sàng ạ, anh/chị thử lại sau nhé.')
      }
    } catch {
      aiState.value = 'idle'
      pushMessage('ai', 'Không kết nối được trợ lý giọng nói ạ, anh/chị thử lại nhé.')
    }
  }

  // The "Hủy"/"Dừng" button. What it does depends on where the turn is:
  // - listening: tell the voice device to abort the capture → the utterance is never sent to
  //   the LLM. Suppress the turn's events too, in case the device had already posted it.
  // - thinking: the utterance is (probably) already at the LLM — we can't unsend it, but we
  //   suppress its reply so the guest never sees an answer to the cancelled sentence.
  // - speaking / idle: just settle the view back to idle.
  function stop() {
    const phase = aiState.value
    clearTimeout(speakingTimer)
    speechText.value = ''
    aiState.value = 'idle'
    if (phase === 'listening' || phase === 'thinking') {
      suppressTurn = true
      // Best-effort device-side abort; harmless if the utterance already left the device. The
      // view is already back to idle either way — but if the command never reached a robot the
      // speaker keeps going, so name that instead of leaving the guest with a silent no-op.
      cancelVoiceListen(getStoredTableId())
        .then((res) => {
          if (res.status === 'no_device') pushMessage('ai', 'Chưa kết nối được robot để dừng ạ.')
        })
        .catch(() => {})
    }
  }

  // The "cuộc trò chuyện mới" button: wipe the agent's memory for this table (fresh LLM thread)
  // and clear the visible chat. The visit/bill continues — orders already sent to the kitchen
  // stay; only the conversation (and the agent's draft cart) starts over.
  async function newConversation() {
    clearTimeout(speakingTimer)
    suppressTurn = false
    messages.value = []
    speechText.value = ''
    aiResponse.value = ''
    aiState.value = 'idle'
    try {
      const res = await newVoiceChat(getStoredTableId()) // also stops any in-flight turn/speech
      if (res.status === 'ok') {
        pushMessage('ai', 'Dạ, mình bắt đầu cuộc trò chuyện mới nhé ạ!')
        // Memory wiped, but no robot mic to cut off: it may still be finishing the previous
        // answer aloud. Say it, so the leftover speech doesn't look like the reset failed.
        if (res.device === false) {
          pushMessage('ai', '(Chưa kết nối được robot nên câu đang nói có thể vẫn phát hết ạ.)')
        }
      } else {
        pushMessage('ai', 'Trợ lý chưa sẵn sàng làm mới ạ, anh/chị thử lại sau nhé.')
      }
    } catch {
      pushMessage('ai', 'Chưa làm mới được cuộc trò chuyện ạ, anh/chị thử lại nhé.')
    }
  }

  return {
    isAiOpen,
    aiState,
    speechText,
    aiResponse,
    isSoundEnabled,
    messages,
    connect,
    disconnect,
    openPanel,
    closePanel,
    resetConversation,
    newConversation,
    toggleSound,
    startListening,
    stop,
  }
})
