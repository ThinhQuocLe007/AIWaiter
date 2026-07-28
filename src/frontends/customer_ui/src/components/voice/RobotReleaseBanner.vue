<template>
  <Transition name="rr">
    <div v-if="seconds !== null" class="rr-banner" role="status" aria-live="polite">
      <div class="rr-ring" :style="{ '--rr-progress': progress }">
        <span class="rr-count">{{ seconds }}</span>
      </div>
      <div class="rr-text">
        <p class="rr-title">Robot sắp về trạm</p>
        <p class="rr-sub">{{ subtitle }}</p>
      </div>
      <button class="rr-btn" type="button" @click="voice.startListening()">
        <i class="ti ti-microphone" aria-hidden="true"></i>
        Gọi thêm món
      </button>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useVoiceStore } from '@/stores/voice'

const voice = useVoiceStore()

const seconds = computed(() => voice.releaseCountdown)

// The full delay this countdown started from — captured off the first tick the backend sent
// rather than written down here, so the ring stays proportional whatever _RELEASE_DELAY is
// set to server-side. Re-armed countdowns come in at full value again and re-seed it.
const total = ref(0)
watch(
  seconds,
  (now, before) => {
    // `before` is undefined on the immediate run, null when no countdown was showing —
    // both mean "this is a fresh countdown", same as a value that jumped back up (re-arm).
    if (now !== null && (before == null || now > before)) total.value = now
  },
  { immediate: true },
)

const progress = computed(() => {
  if (seconds.value === null || total.value <= 0) return 0
  return seconds.value / total.value
})

const subtitle = computed(() =>
  seconds.value === 0
    ? 'Đang rời bàn...'
    : 'Đơn đã gửi bếp. Nhấn nút bên cạnh nếu anh/chị cần gọi thêm ạ.',
)
</script>

<style scoped>
.rr-banner {
  position: absolute;
  top: 1rem;
  left: 50%;
  transform: translateX(-50%);
  z-index: 60; /* above the voice panel (50) — it must stay readable while the sheet is open */
  display: flex;
  align-items: center;
  gap: 0.875rem;
  padding: 0.625rem 0.875rem;
  max-width: 620px;
  background: #1f1b16;
  border: 1px solid var(--color-accent-dark);
  border-radius: 14px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4);
  color: #e8e2d6;
}

/* Countdown ring: conic sweep driven by --rr-progress (1 → 0). */
.rr-ring {
  position: relative;
  flex: 0 0 auto;
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: conic-gradient(
    var(--color-accent, #d9a441) calc(var(--rr-progress) * 360deg),
    #3a342c 0
  );
  transition: background 0.9s linear;
}

.rr-ring::after {
  content: '';
  position: absolute;
  inset: 4px;
  border-radius: 50%;
  background: #1f1b16;
}

.rr-count {
  position: relative; /* above the ::after disc */
  font-size: 1rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.rr-text {
  min-width: 0;
}

.rr-title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 700;
}

.rr-sub {
  margin: 0.125rem 0 0;
  font-size: 0.8rem;
  color: #b8b0a2;
}

.rr-btn {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.5rem 0.875rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: #1f1b16;
  background: var(--color-accent, #d9a441);
  border: none;
  border-radius: 10px;
  cursor: pointer;
}

.rr-btn:active {
  transform: scale(0.97);
}

.rr-enter-active,
.rr-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.rr-enter-from,
.rr-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-8px);
}
</style>
