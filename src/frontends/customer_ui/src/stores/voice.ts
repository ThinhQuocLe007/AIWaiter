import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { FoodItem } from '@/types'
import { useCartStore } from '@/stores/cart'
import { useMenuStore } from '@/stores/menu'
import { getStoredTableId } from '@/data/tableSession'
import { startVoiceListen, cancelVoiceListen, createPayment } from '@/data/api'
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

  function toggleSound() {
    isSoundEnabled.value = !isSoundEnabled.value
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
      // Best-effort device-side abort; harmless if the utterance already left the device.
      cancelVoiceListen(getStoredTableId()).catch(() => {})
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
    toggleSound,
    startListening,
    stop,
    confirmRecommendation,
  }
})
