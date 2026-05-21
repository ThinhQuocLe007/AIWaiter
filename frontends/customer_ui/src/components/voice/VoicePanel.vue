<template>
  <Transition name="sheet">
    <div v-if="voice.isAiOpen" class="voice-panel">
      <!-- Header -->
      <div class="vp-header">
        <div class="vp-status">
          <span class="vp-dot" aria-hidden="true"></span>
          <span class="vp-title">Trợ lý RoboDish</span>
          <span class="vp-state">{{ stateLabel }}</span>
        </div>
        <div class="vp-actions">
          <button class="vp-icon-btn" type="button" :aria-label="voice.isSoundEnabled ? 'Tắt tiếng' : 'Bật tiếng'" @click="voice.toggleSound()">
            <i class="ti" :class="voice.isSoundEnabled ? 'ti-volume' : 'ti-volume-off'" aria-hidden="true"></i>
          </button>
          <button class="vp-icon-btn" type="button" aria-label="Đóng" @click="voice.closePanel()">
            <i class="ti ti-x" aria-hidden="true"></i>
          </button>
        </div>
      </div>

      <!-- Chat -->
      <div ref="chatEl" class="vp-chat">
        <template v-for="msg in voice.messages" :key="msg.id">
          <!-- User bubble -->
          <div v-if="msg.role === 'user'" class="bubble bubble-user">
            {{ msg.text }}
          </div>

          <!-- AI bubble -->
          <div v-else class="ai-row">
            <div class="ai-avatar"><i class="ti ti-robot" aria-hidden="true"></i></div>
            <div class="bubble bubble-ai">{{ msg.text }}</div>
          </div>
        </template>

        <!-- Recommended dish card (slides out under the AI bubble) -->
        <Transition name="reco">
          <div v-if="voice.recommendedItem" class="reco-card">
            <img :src="voice.recommendedItem.image" :alt="voice.recommendedItem.name" class="reco-img" />
            <div class="reco-info">
              <span class="reco-name">{{ voice.recommendedItem.name }}</span>
              <span class="reco-price">{{ formatPrice(voice.recommendedItem.price) }}</span>
            </div>
            <button class="reco-add" type="button" @click="voice.confirmRecommendation()">
              <i class="ti ti-plus" aria-hidden="true"></i>
              Thêm nhanh
            </button>
          </div>
        </Transition>

        <!-- Thinking dots -->
        <div v-if="voice.aiState === 'thinking'" class="ai-row">
          <div class="ai-avatar"><i class="ti ti-robot" aria-hidden="true"></i></div>
          <div class="bubble bubble-ai thinking">
            <span class="dot"></span><span class="dot"></span><span class="dot"></span>
          </div>
        </div>
      </div>

      <!-- Footer: waveform + stop while busy, mic button when ready -->
      <div class="vp-footer">
        <!-- Listening: waveform + cancel (pressed by mistake / misspoke) -->
        <template v-if="voice.aiState === 'listening'">
          <div class="waveform">
            <div class="bars">
              <span class="bar bar-1"></span>
              <span class="bar bar-2"></span>
              <span class="bar bar-3"></span>
              <span class="bar bar-4"></span>
              <span class="bar bar-5"></span>
            </div>
            <span class="listening-label">ĐANG LẮNG NGHE GIỌNG NÓI CỦA BẠN...</span>
          </div>
          <button class="stop-btn" type="button" @click="voice.stop()">
            <i class="ti ti-player-stop-filled" aria-hidden="true"></i>
            Hủy
          </button>
        </template>

        <!-- Thinking: stop the processing -->
        <button
          v-else-if="voice.aiState === 'thinking'"
          class="stop-btn"
          type="button"
          @click="voice.stop()"
        >
          <i class="ti ti-player-stop-filled" aria-hidden="true"></i>
          Dừng
        </button>

        <!-- Idle / speaking: talk again, plus stop while the AI is replying -->
        <template v-else>
          <button class="mic-btn" type="button" @click="voice.startListening()">
            <i class="ti ti-microphone" aria-hidden="true"></i>
            Nói tiếp
          </button>
          <button
            v-if="voice.aiState === 'speaking'"
            class="stop-btn stop-btn-ghost"
            type="button"
            @click="voice.stop()"
          >
            <i class="ti ti-player-stop-filled" aria-hidden="true"></i>
            Dừng
          </button>
        </template>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useVoiceStore } from '@/stores/voice'
import { formatPrice } from '@/utils/format'

const voice = useVoiceStore()
const chatEl = ref<HTMLElement | null>(null)

const stateLabel = computed(() => {
  switch (voice.aiState) {
    case 'listening':
      return 'Đang nghe'
    case 'thinking':
      return 'Đang xử lý'
    case 'speaking':
      return 'Đang trả lời'
    default:
      return 'Trực tuyến'
  }
})

// Keep the chat scrolled to the latest message.
watch(
  () => [voice.messages.length, voice.aiState, voice.recommendedItem],
  async () => {
    await nextTick()
    if (chatEl.value) chatEl.value.scrollTop = chatEl.value.scrollHeight
  },
)
</script>

<style scoped>
.voice-panel {
  position: absolute;
  inset-inline: 0;
  bottom: 0;
  z-index: 50;
  display: flex;
  flex-direction: column;
  max-height: 460px;
  background: #0f172a;
  border-top: 1px solid #1e293b;
  border-radius: 24px 24px 0 0;
  box-shadow: 0 -12px 40px rgba(0, 0, 0, 0.5);
  color: #e2e8f0;
  overflow: hidden;
}

/* Header */
.vp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #1e293b;
}

.vp-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.vp-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.6);
  animation: pulse-dot 1.6s infinite;
}

.vp-title {
  font-size: 0.875rem;
  font-weight: 700;
  color: #f8fafc;
}

.vp-state {
  font-size: 0.6875rem;
  color: #94a3b8;
}

.vp-actions {
  display: flex;
  gap: 0.25rem;
}

.vp-icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  min-width: 0;
  min-height: 0;
  border: none;
  border-radius: var(--radius-full);
  background: #1e293b;
  color: #cbd5e1;
  font-size: 1.05rem;
}

.vp-icon-btn:active {
  background: #334155;
}

/* Chat */
.vp-chat {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 1rem;
}

.bubble {
  max-width: 78%;
  padding: 0.6rem 0.85rem;
  font-size: 0.8125rem;
  line-height: 1.45;
  border-radius: 16px;
}

.bubble-user {
  align-self: flex-end;
  background: #1e293b;
  color: #e2e8f0;
  border-top-right-radius: 4px;
}

.ai-row {
  display: flex;
  align-items: flex-end;
  gap: 0.5rem;
  align-self: flex-start;
  max-width: 88%;
}

.ai-avatar {
  flex: 0 0 auto;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #e63946, #f77f00);
  color: #fff;
  font-size: 0.95rem;
}

.bubble-ai {
  background: linear-gradient(180deg, #1e293b, #172033);
  border: 1px solid #283548;
  color: #e2e8f0;
  border-bottom-left-radius: 4px;
}

/* Thinking dots */
.thinking {
  display: flex;
  gap: 4px;
  align-items: center;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #94a3b8;
  animation: blink 1.2s infinite ease-in-out;
}

.dot:nth-child(2) {
  animation-delay: 0.2s;
}

.dot:nth-child(3) {
  animation-delay: 0.4s;
}

/* Recommended card */
.reco-card {
  align-self: flex-start;
  margin-left: 38px;
  display: flex;
  align-items: center;
  gap: 0.65rem;
  background: #111c30;
  border: 1px solid #283548;
  border-radius: 14px;
  padding: 0.55rem;
  max-width: 88%;
}

.reco-img {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  object-fit: cover;
  flex: 0 0 auto;
}

.reco-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.reco-name {
  font-size: 0.8125rem;
  font-weight: 700;
  color: #f1f5f9;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 150px;
}

.reco-price {
  font-size: 0.8125rem;
  font-weight: 700;
  color: #fb923c;
}

.reco-add {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  margin-left: auto;
  background: #10b981;
  color: #fff;
  border: none;
  font-family: inherit;
  font-weight: 700;
  font-size: 0.75rem;
  min-height: 0;
  min-width: 0;
  padding: 0.45rem 0.7rem;
  border-radius: var(--radius-full);
  white-space: nowrap;
}

.reco-add:active {
  background: #059669;
  transform: scale(0.95);
}

/* Footer */
.vp-footer {
  padding: 0.75rem 1rem 1rem;
  border-top: 1px solid #1e293b;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.6rem;
}

.waveform {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.bars {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 32px;
}

.bar {
  width: 6px;
  height: 28px;
  border-radius: var(--radius-full);
  background: var(--color-primary);
  transform: scaleY(0.4);
}

.bar-1 {
  animation: wave 1.2s infinite ease-in-out;
}
.bar-2 {
  animation: wave 0.9s infinite ease-in-out;
}
.bar-3 {
  background: #f87171;
  animation: wave 1.4s infinite ease-in-out;
}
.bar-4 {
  background: #f43f5e;
  animation: wave 0.7s infinite ease-in-out;
}
.bar-5 {
  animation: wave 1.1s infinite ease-in-out;
}

.listening-label {
  font-size: 0.625rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: #f87171;
  animation: blink 1.4s infinite;
}

.mic-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: linear-gradient(110deg, #e63946, #f77f00);
  color: #fff;
  border: none;
  font-family: inherit;
  font-weight: 800;
  font-size: 0.8125rem;
  padding: 0.6rem 1.4rem;
  border-radius: var(--radius-full);
  box-shadow: 0 4px 14px rgba(230, 57, 70, 0.4);
}

.mic-btn:disabled {
  opacity: 0.5;
}

.mic-btn:not(:disabled):active {
  transform: scale(0.96);
}

/* Stop / cancel button (shown while the assistant is busy) */
.stop-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: #ef4444;
  color: #fff;
  border: none;
  font-family: inherit;
  font-weight: 800;
  font-size: 0.8125rem;
  padding: 0.55rem 1.3rem;
  border-radius: var(--radius-full);
  box-shadow: 0 4px 14px rgba(239, 68, 68, 0.35);
}

.stop-btn:active {
  transform: scale(0.96);
  background: #dc2626;
}

/* Ghost variant used next to "Nói tiếp" while the AI is speaking */
.stop-btn-ghost {
  background: transparent;
  color: #f87171;
  border: 1px solid #7f1d1d;
  box-shadow: none;
}

.stop-btn-ghost:active {
  background: rgba(239, 68, 68, 0.12);
}

/* Animations */
@keyframes wave {
  0%,
  100% {
    transform: scaleY(0.4);
  }
  50% {
    transform: scaleY(1.2);
  }
}

@keyframes blink {
  0%,
  100% {
    opacity: 0.3;
  }
  50% {
    opacity: 1;
  }
}

@keyframes pulse-dot {
  0% {
    box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.6);
  }
  70% {
    box-shadow: 0 0 0 6px rgba(16, 185, 129, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(16, 185, 129, 0);
  }
}

/* Slide-up transition */
.sheet-enter-active,
.sheet-leave-active {
  transition: transform 0.32s cubic-bezier(0.32, 0.72, 0, 1);
}
.sheet-enter-from,
.sheet-leave-to {
  transform: translateY(100%);
}

.reco-enter-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.reco-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
</style>
