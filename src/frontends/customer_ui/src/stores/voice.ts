import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { FoodItem } from '@/types'
import { useCartStore } from '@/stores/cart'
import { getStoredTableId } from '@/data/tableSession'
import router from '@/router'
import { connectEvents, type WsHandle } from '@shared/ws'
import type { UiAction, WsEvent } from '@shared/types'

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
      onReply(e.text, e.action)
    }
  }

  // The robot heard the guest: surface the words immediately and show "thinking" while the
  // server runs the LLM. Auto-open the panel so the guest sees the conversation start.
  function onHeard(text: string) {
    clearTimeout(speakingTimer)
    isAiOpen.value = true
    aiState.value = 'thinking'
    speechText.value = text
    recommendedItem.value = null
    if (text.trim()) pushMessage('user', text)
  }

  // The agent replied: show the spoken text and follow any UI action (open the menu / the bill).
  function onReply(text: string, action: UiAction | null) {
    aiState.value = 'speaking'
    aiResponse.value = text
    if (text.trim()) pushMessage('ai', text)
    applyAction(action)
    clearTimeout(speakingTimer)
    speakingTimer = setTimeout(() => {
      if (aiState.value === 'speaking') aiState.value = 'idle'
    }, SPEAKING_HOLD_MS)
  }

  // Mirror the agent's tablet command: a successful order step opens the menu, a payment request
  // brings up the bill. Guarded so we don't re-navigate to the screen we're already on.
  function applyAction(action: UiAction | null) {
    if (!action) return
    const target =
      action.action === 'open_payment' ? 'payment' : action.action === 'open_menu' ? 'menu' : null
    if (target && router.currentRoute.value.name !== target) {
      router.push({ name: target })
    }
  }

  function openPanel() {
    connect()
    isAiOpen.value = true
  }

  function closePanel() {
    clearTimeout(speakingTimer)
    isAiOpen.value = false
    aiState.value = 'idle'
    speechText.value = ''
    aiResponse.value = ''
    recommendedItem.value = null
    messages.value = []
  }

  function toggleSound() {
    isSoundEnabled.value = !isSoundEnabled.value
  }

  // Kept for the panel's "Nói tiếp" button. The mic is on the robot, so this tablet can't start a
  // capture — it just clears any lingering state so the guest knows the robot is ready to listen.
  function startListening() {
    clearTimeout(speakingTimer)
    aiState.value = 'idle'
  }

  // Stop button: drop back to idle. (Interrupting the robot's TTS would need a separate signal to
  // the robot; not wired — this only resets the tablet's view.)
  function stop() {
    clearTimeout(speakingTimer)
    speechText.value = ''
    aiState.value = 'idle'
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
    toggleSound,
    startListening,
    stop,
    confirmRecommendation,
  }
})
