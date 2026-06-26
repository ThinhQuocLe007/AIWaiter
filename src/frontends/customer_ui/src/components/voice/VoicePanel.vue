<template>
  <!-- Siri / Gemini-style listening orb, centered over the whole screen -->
  <Transition name="orb">
    <div v-if="voice.isAiOpen && voice.aiState === 'listening'" class="voice-orb-overlay">
      <div class="orb">
        <span class="orb-ring orb-ring-1" aria-hidden="true"></span>
        <span class="orb-ring orb-ring-2" aria-hidden="true"></span>
        <span class="orb-ring orb-ring-3" aria-hidden="true"></span>
        <span class="orb-core" aria-hidden="true"></span>
        <i class="ti ti-microphone orb-mic" aria-hidden="true"></i>
      </div>
      <span class="orb-label">ĐANG LẮNG NGHE...</span>
      <button class="orb-cancel" type="button" @click="voice.stop()">
        <i class="ti ti-x" aria-hidden="true"></i>
        Hủy
      </button>
    </div>
  </Transition>

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
            <img
              v-if="voice.recommendedItem.image"
              :src="voice.recommendedItem.image"
              :alt="voice.recommendedItem.name"
              class="reco-img"
            />
            <div v-else class="reco-img reco-img-placeholder" aria-hidden="true">🍽️</div>
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

      <!-- Footer: stop while busy, mic button when ready.
           While listening, the centered orb overlay replaces these controls. -->
      <div class="vp-footer">
        <!-- Thinking: stop the processing -->
        <button
          v-if="voice.aiState === 'thinking'"
          class="stop-btn"
          type="button"
          @click="voice.stop()"
        >
          <i class="ti ti-player-stop-filled" aria-hidden="true"></i>
          Dừng
        </button>

        <!-- Idle / speaking: talk again, plus stop while the AI is replying -->
        <template v-else-if="voice.aiState !== 'listening'">
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
  background: #1F1B16;
  border-top: 1px solid var(--color-accent-dark);
  border-radius: 16px 16px 0 0;
  box-shadow: 0 -16px 48px rgba(0, 0, 0, 0.45);
  color: #E8E2D6;
  overflow: hidden;
}

/* Header */
.vp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #34302A;
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
  background: var(--color-accent);
  box-shadow: 0 0 0 0 rgba(168, 133, 62, 0.6);
  animation: pulse-dot 1.6s infinite;
}

.vp-title {
  font-family: var(--font-display);
  font-size: 0.95rem;
  font-weight: 600;
  color: #F5F1E8;
}

.vp-state {
  font-size: 0.6875rem;
  color: #A89F90;
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
  background: #34302A;
  color: #C9C0B0;
  font-size: 1.05rem;
}

.vp-icon-btn:active {
  background: #443F37;
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
  background: #34302A;
  color: #E8E2D6;
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
  background: linear-gradient(135deg, var(--color-accent), var(--color-accent-dark));
  color: #1F1B16;
  font-size: 0.95rem;
}

.bubble-ai {
  background: #2A2620;
  border: 1px solid #3A352D;
  color: #E8E2D6;
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
  background: #A89F90;
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
  background: #2A2620;
  border: 1px solid #3A352D;
  border-radius: var(--radius-md);
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

.reco-img-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  color: var(--color-accent);
  background: #34302A;
}

.reco-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.reco-name {
  font-size: 0.8125rem;
  font-weight: 600;
  color: #F5F1E8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 150px;
}

.reco-price {
  font-size: 0.85rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: #F5F1E8;
}

.reco-add {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  margin-left: auto;
  background: var(--color-accent);
  color: #1F1B16;
  border: none;
  font-family: inherit;
  font-weight: 600;
  font-size: 0.75rem;
  min-height: 0;
  min-width: 0;
  padding: 0.45rem 0.8rem;
  border-radius: var(--radius-sm);
  white-space: nowrap;
}

.reco-add:active {
  background: var(--color-accent-dark);
  transform: scale(0.95);
}

/* Footer */
.vp-footer {
  padding: 0.75rem 1rem 1rem;
  border-top: 1px solid #34302A;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.6rem;
}

/* Centered listening orb overlay (Siri / Gemini style) */
.voice-orb-overlay {
  position: absolute;
  inset: 0;
  z-index: 60;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1.6rem;
  background: radial-gradient(circle at center, rgba(31, 27, 22, 0.7), rgba(20, 17, 13, 0.94));
  backdrop-filter: blur(5px);
  -webkit-backdrop-filter: blur(5px);
}

.orb {
  position: relative;
  width: 180px;
  height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: orb-breathe 3s ease-in-out infinite;
}

.orb-core {
  width: 128px;
  height: 128px;
  border-radius: 50%;
  background:
    radial-gradient(circle at 32% 28%, rgba(255, 255, 255, 0.5), transparent 55%),
    conic-gradient(
      from 0deg,
      var(--color-accent),
      var(--color-ai-light),
      var(--color-accent-dark),
      var(--color-accent)
    );
  box-shadow:
    0 0 50px 10px rgba(168, 133, 62, 0.55),
    inset 0 0 28px rgba(255, 255, 255, 0.28);
  animation: orb-spin 7s linear infinite;
}

.orb-mic {
  position: absolute;
  font-size: 2.4rem;
  color: #1f1b16;
  text-shadow: 0 1px 3px rgba(255, 255, 255, 0.35);
}

.orb-ring {
  position: absolute;
  width: 128px;
  height: 128px;
  border-radius: 50%;
  border: 2px solid rgba(168, 133, 62, 0.5);
  animation: orb-sonar 2.4s ease-out infinite;
}

.orb-ring-2 {
  animation-delay: 0.8s;
}

.orb-ring-3 {
  animation-delay: 1.6s;
}

.orb-label {
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.22em;
  color: var(--color-accent);
  animation: blink 1.6s infinite;
}

.orb-cancel {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: rgba(52, 48, 42, 0.85);
  color: #e8e2d6;
  border: 1px solid #4a443b;
  font-family: inherit;
  font-weight: 600;
  font-size: 0.8rem;
  padding: 0.5rem 1.4rem;
  border-radius: var(--radius-full);
}

.orb-cancel:active {
  transform: scale(0.96);
  background: #443f37;
}

.mic-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: linear-gradient(110deg, var(--color-accent), var(--color-accent-dark));
  color: #1F1B16;
  border: none;
  font-family: inherit;
  font-weight: 600;
  font-size: 0.8125rem;
  letter-spacing: 0.03em;
  padding: 0.6rem 1.4rem;
  border-radius: var(--radius-sm);
  box-shadow: 0 4px 14px rgba(31, 27, 22, 0.35);
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
  background: var(--color-danger);
  color: #fff;
  border: none;
  font-family: inherit;
  font-weight: 600;
  font-size: 0.8125rem;
  letter-spacing: 0.03em;
  padding: 0.55rem 1.3rem;
  border-radius: var(--radius-sm);
  box-shadow: 0 4px 14px rgba(155, 58, 53, 0.3);
}

.stop-btn:active {
  transform: scale(0.96);
  background: #7E2E2A;
}

/* Ghost variant used next to "Nói tiếp" while the AI is speaking */
.stop-btn-ghost {
  background: transparent;
  color: #C97A74;
  border: 1px solid #5E2A27;
  box-shadow: none;
}

.stop-btn-ghost:active {
  background: rgba(155, 58, 53, 0.14);
}

/* Animations */
@keyframes orb-breathe {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.08);
  }
}

@keyframes orb-spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes orb-sonar {
  0% {
    transform: scale(0.7);
    opacity: 0.7;
  }
  100% {
    transform: scale(1.7);
    opacity: 0;
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
    box-shadow: 0 0 0 0 rgba(168, 133, 62, 0.6);
  }
  70% {
    box-shadow: 0 0 0 6px rgba(168, 133, 62, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(168, 133, 62, 0);
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

/* Orb overlay fade */
.orb-enter-active,
.orb-leave-active {
  transition: opacity 0.3s ease;
}
.orb-enter-from,
.orb-leave-to {
  opacity: 0;
}

.reco-enter-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.reco-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
</style>
