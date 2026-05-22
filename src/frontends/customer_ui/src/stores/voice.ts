import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { FoodItem } from '@/types'
import { useCartStore } from '@/stores/cart'
import { useMenuStore } from '@/stores/menu'

// AI assistant lifecycle:
// - 'idle': waiting to start
// - 'listening': capturing the customer's speech (waveform animates)
// - 'thinking': running STT/LLM intent extraction (loading dots)
// - 'speaking': replying with advice + a recommended dish
export type AiState = 'idle' | 'listening' | 'thinking' | 'speaking'

export interface ChatMessage {
  id: number
  role: 'user' | 'ai'
  text: string
}

// Scripted turns used while the real speech/LLM backend is not wired up yet.
// TODO: Phase 2 - replace with Web Speech API (STT) + a call to the LLM endpoint.
interface MockTurn {
  speech: string
  response: string
  recommendedId: string
}

const MOCK_TURNS: MockTurn[] = [
  {
    speech: 'Mình muốn ăn gì đó cay cay, nóng hổi cho 2 người.',
    response:
      'Vậy bạn thử Lẩu Thái Tomyum Hải Sản nhé! Nước lẩu chua cay chuẩn vị Thái, kèm hải sản tươi, rất hợp cho 2-3 người.',
    recommendedId: '1',
  },
  {
    speech: 'Cho mình một món chay thanh đạm, tốt cho sức khỏe.',
    response:
      'Mình gợi ý Lẩu Nấm Chay Thanh Dưỡng - nước dùng ngọt thanh từ rau củ và nấm, bổ dưỡng mà vẫn nhẹ bụng nha.',
    recommendedId: '3',
  },
  {
    speech: 'Trời nóng quá, mình muốn uống gì đó mát mát.',
    response:
      'Trà Đào Cam Sả là lựa chọn tuyệt vời! Chua ngọt thanh mát, thơm lừng sả và cam, giải nhiệt cực đã.',
    recommendedId: '24',
  },
]

export const useVoiceStore = defineStore('voice', () => {
  const isAiOpen = ref(false)
  const aiState = ref<AiState>('idle')
  const speechText = ref('')
  const aiResponse = ref('')
  const recommendedItem = ref<FoodItem | null>(null)
  const isSoundEnabled = ref(true)
  const messages = ref<ChatMessage[]>([])

  let turnIndex = 0
  let messageId = 0
  const timers: ReturnType<typeof setTimeout>[] = []

  function schedule(fn: () => void, delay: number) {
    timers.push(setTimeout(fn, delay))
  }

  function clearTimers() {
    timers.forEach(clearTimeout)
    timers.length = 0
  }

  function pushMessage(role: ChatMessage['role'], text: string) {
    messages.value.push({ id: messageId++, role, text })
  }

  function openPanel() {
    isAiOpen.value = true
    startListening()
  }

  function closePanel() {
    clearTimers()
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

  // Drives one full listen -> think -> speak cycle (currently scripted).
  // TODO: Phase 2 - swap the timers for real STT capture + streaming LLM tokens.
  function startListening() {
    clearTimers()
    aiState.value = 'listening'
    speechText.value = ''
    aiResponse.value = ''
    recommendedItem.value = null

    const turn = MOCK_TURNS[turnIndex % MOCK_TURNS.length]
    turnIndex++
    if (!turn) return

    schedule(() => {
      speechText.value = turn.speech
      pushMessage('user', turn.speech)
      aiState.value = 'thinking'
    }, 2200)

    schedule(() => {
      const menu = useMenuStore()
      const item = menu.foodItems.find((f) => f.id === turn.recommendedId) ?? null
      aiState.value = 'speaking'
      aiResponse.value = turn.response
      recommendedItem.value = item
      pushMessage('ai', turn.response)
    }, 3900)
  }

  // Stops the current cycle mid-way (pressed by mistake, misspoke, or to interrupt
  // the AI) and returns to idle so the user can talk again or close the panel.
  // Keeps the chat history and any recommended dish so it stays actionable.
  function stop() {
    clearTimers()
    // Cancelled while still capturing speech: roll back the consumed mock turn
    // so the next listen replays it instead of skipping ahead.
    // TODO: Phase 2 - also abort the live STT stream / TTS playback here.
    if (aiState.value === 'listening') {
      turnIndex = Math.max(0, turnIndex - 1)
    }
    speechText.value = ''
    aiState.value = 'idle'
  }

  // Adds the recommended dish to the real cart (the agreement / "add to cart" intent).
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
    openPanel,
    closePanel,
    toggleSound,
    startListening,
    stop,
    confirmRecommendation,
  }
})
