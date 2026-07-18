import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { FoodItem } from '@/types'
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
  const recommendedItem = ref<FoodItem | null>(null)
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
      onReply(e.text, e.action, e.stage, e.cart, e.confirmed ?? false)
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
    recommendedItem.value = null
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
    syncCart(stage, voiceCart, confirmed)
    applyAction(action)
    clearTimeout(speakingTimer)
    speakingTimer = setTimeout(() => {
      if (aiState.value === 'speaking') aiState.value = 'idle'
    }, SPEAKING_HOLD_MS)
  }

  // Mirror the agent's cart into the tablet cart so both stay one cart:
  // - while drafting / awaiting confirmation → the agent's draft REPLACES the web draft;
  // - on the turn the order was sent to the kitchen (`confirmed`) → move it into the
  //   "đã gửi bếp" list, so closing the voice sheet keeps the dishes on the cart card;
  // - any other turn (plain chat, post-confirm smalltalk) leaves the web cart alone, so a
  //   manually-composed cart is never wiped by an unrelated voice turn.
  async function syncCart(stage?: string, voiceCart?: VoiceCartItem[] | null, confirmed = false) {
    const cart = useCartStore()
    const menu = useMenuStore()
    const applyDraft = async (items: VoiceCartItem[]) => {
      if (menu.foodItems.length === 0) await menu.loadMenu() // need prices/images to map names
      cart.syncFromVoice(items, menu.foodItems)
    }
    if (confirmed) {
      // Prefer the agent's authoritative list (covers a reloaded tablet with an empty draft).
      if (voiceCart && voiceCart.length > 0) await applyDraft(voiceCart)
      cart.markOrdered()
    } else if (stage === 'DRAFTING' || stage === 'AWAITING_CONFIRMATION') {
      if (Array.isArray(voiceCart)) await applyDraft(voiceCart)
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
    recommendedItem.value = null
  }

  // Speaker toggle — not just a local flag: it mutes the robot's actual TTS output (the audio
  // plays on the robot's Jetson, not this tablet). Muting cuts the sentence currently playing;
  // best-effort when no robot is at the table (the flag still drives the next turn's state).
  function toggleSound() {
    isSoundEnabled.value = !isSoundEnabled.value
    setVoiceMuted(getStoredTableId(), !isSoundEnabled.value).catch(() => {})
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

  // The "Hủy"/"Dừng" button. The device-side cancel is sent in EVERY phase — it kills whatever
  // part of the turn is alive there: an armed capture, the agent reply stream being consumed,
  // and the TTS sentence coming out of the robot's speaker. On top of that:
  // - listening: the utterance is never sent to the LLM; suppress its events in case it slipped.
  // - thinking: the utterance is (probably) already at the LLM — we can't unsend it, but we
  //   suppress its reply so the guest never sees (nor hears) an answer to the cancelled sentence.
  // - speaking: the reply already arrived; just cut the audio, keep the text on screen.
  function stop() {
    const phase = aiState.value
    clearTimeout(speakingTimer)
    speechText.value = ''
    aiState.value = 'idle'
    if (phase === 'listening' || phase === 'thinking') {
      suppressTurn = true
    }
    cancelVoiceListen(getStoredTableId()).catch(() => {})
  }

  // The "cuộc trò chuyện mới" button: wipe the agent's memory for this table (fresh LLM thread)
  // and clear the visible chat. The visit/bill continues — orders already sent to the kitchen
  // stay; only the conversation (and the agent's draft cart) starts over.
  async function newConversation() {
    clearTimeout(speakingTimer)
    suppressTurn = false
    messages.value = []
    recommendedItem.value = null
    speechText.value = ''
    aiResponse.value = ''
    aiState.value = 'idle'
    try {
      const res = await newVoiceChat(getStoredTableId()) // also stops any in-flight turn/speech
      if (res.status === 'ok') {
        pushMessage('ai', 'Dạ, mình bắt đầu cuộc trò chuyện mới nhé ạ!')
      } else {
        pushMessage('ai', 'Trợ lý chưa sẵn sàng làm mới ạ, anh/chị thử lại sau nhé.')
      }
    } catch {
      pushMessage('ai', 'Chưa làm mới được cuộc trò chuyện ạ, anh/chị thử lại nhé.')
    }
  }

  // Adds the recommended dish to the real cart (the "add to cart" intent).
  function confirmRecommendation() {
    if (!recommendedItem.value) return
    const cart = useCartStore()
    cart.addItem(recommendedItem.value)
    pushMessage('ai', `Đã thêm "${recommendedItem.value.name}" vào giỏ hàng của bạn rồi nhé! 🛒`)
  }

  return {
    isAiOpen,
    aiState,
    speechText,
    aiResponse,
    recommendedItem,
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
    confirmRecommendation,
  }
})
