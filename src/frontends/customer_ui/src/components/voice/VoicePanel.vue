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

        <!-- Thinking dots -->
        <div v-if="voice.aiState === 'thinking'" class="ai-row">
          <div class="ai-avatar"><i class="ti ti-robot" aria-hidden="true"></i></div>
          <div class="bubble bubble-ai thinking">
            <span class="dot"></span><span class="dot"></span><span class="dot"></span>
          </div>
        </div>
      </div>

      <!-- Footer: compact inline listening row (the chat above stays fully visible),
           stop while busy, mic button when ready. -->
      <div class="vp-footer">
        <!-- Listening: small pulsing orb + cancel, no overlay hiding the AI's advice -->
        <div v-if="voice.aiState === 'listening'" class="listen-row">
          <div class="orb-mini">
            <span class="orb-ring" aria-hidden="true"></span>
            <span class="orb-ring orb-ring-2" aria-hidden="true"></span>
            <span class="orb-core" aria-hidden="true"></span>
            <i class="ti ti-microphone orb-mic" aria-hidden="true"></i>
          </div>
          <span class="listen-label">Đang lắng nghe...</span>
          <button class="stop-btn stop-btn-ghost listen-cancel" type="button" @click="voice.stop()">
            <i class="ti ti-x" aria-hidden="true"></i>
            Hủy
          </button>
        </div>

        <!-- Thinking: stop the processing -->
        <button
          v-else-if="voice.aiState === 'thinking'"
          class="stop-btn"
          type="button"
          @click="voice.stop()"
        >
          <i class="ti ti-player-stop-filled" aria-hidden="true"></i>
          Hủy — không trả lời câu này
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
  () => [voice.messages.length, voice.aiState],
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

/* Footer */
.vp-footer {
  padding: 0.75rem 1rem 1rem;
  border-top: 1px solid #34302A;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.6rem;
}

/* Compact inline listening row — the chat (the AI's advice) stays fully visible above it */
.listen-row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.orb-mini {
  position: relative;
  flex: 0 0 auto;
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: orb-breathe 3s ease-in-out infinite;
}

.orb-core {
  width: 38px;
  height: 38px;
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
    0 0 16px 4px rgba(168, 133, 62, 0.45),
    inset 0 0 10px rgba(255, 255, 255, 0.28);
  animation: orb-spin 7s linear infinite;
}

.orb-mic {
  position: absolute;
  font-size: 1.05rem;
  color: #1f1b16;
  text-shadow: 0 1px 3px rgba(255, 255, 255, 0.35);
}

.orb-ring {
  position: absolute;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  border: 2px solid rgba(168, 133, 62, 0.5);
  animation: orb-sonar 2.4s ease-out infinite;
}

.orb-ring-2 {
  animation-delay: 1.2s;
}

.listen-label {
  flex: 1;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--color-accent);
  animation: blink 1.6s infinite;
}

.listen-cancel {
  flex: 0 0 auto;
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
</style>
