<template>
  <div class="smart-banner" role="button" @click="voice.openPanel()">
    <i class="ti ti-robot banner-bot" aria-hidden="true"></i>
    <div class="banner-content">
      <span class="banner-tag">Đặc Quyền Rảnh Tay ⚡</span>
      <h3 class="banner-title">Hôm nay bạn muốn ăn gì?</h3>
      <p class="banner-subtitle">
        Chỉ cần nói cho Trợ lý ảo RoboDish sở thích, chúng mình sẽ chọn món siêu ngon giúp bạn
        trong 5 giây!
      </p>
      <button class="banner-cta" type="button" @click.stop="voice.openPanel()">
        <i class="ti ti-microphone cta-mic" aria-hidden="true"></i>
        Nói Chuyện Với AI Ngay
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useVoiceStore } from '@/stores/voice'

const voice = useVoiceStore()
</script>

<style scoped>
.smart-banner {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-md);
  padding: 1.1rem 1.25rem;
  margin-bottom: 1rem;
  color: #F5F1E8;
  background: linear-gradient(120deg, #1F1B16 0%, #2A2620 100%);
  border: 1px solid var(--color-accent-dark);
  box-shadow: var(--shadow-md);
}

.smart-banner:active {
  transform: scale(0.99);
}

.banner-bot {
  position: absolute;
  right: -8px;
  bottom: -16px;
  font-size: 8rem;
  opacity: 0.12;
  color: var(--color-accent);
  pointer-events: none;
}

.banner-content {
  position: relative;
  z-index: 1;
  max-width: 80%;
}

.banner-tag {
  display: inline-block;
  color: var(--color-accent);
  background: rgba(168, 133, 62, 0.16);
  border: 1px solid rgba(168, 133, 62, 0.4);
  font-size: 0.625rem;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  padding: 0.15rem 0.6rem;
  border-radius: var(--radius-full);
  margin-bottom: 0.5rem;
}

.banner-title {
  font-family: var(--font-display);
  font-size: 1.35rem;
  font-weight: 600;
  margin: 0 0 0.3rem 0;
}

.banner-subtitle {
  font-size: 0.75rem;
  line-height: 1.5;
  color: rgba(245, 241, 232, 0.78);
  margin: 0 0 0.85rem 0;
}

.banner-cta {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: var(--color-accent);
  color: #1F1B16;
  font-family: inherit;
  font-weight: 600;
  font-size: 0.8125rem;
  letter-spacing: 0.03em;
  min-height: 0;
  min-width: 0;
  padding: 0.55rem 1.1rem;
  border: none;
  border-radius: var(--radius-sm);
  box-shadow: 0 2px 6px rgba(31, 27, 22, 0.25);
}

.banner-cta:active {
  transform: scale(0.95);
}

.cta-mic {
  font-size: 0.95rem;
  animation: cta-bounce 1s infinite;
}

@keyframes cta-bounce {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-3px);
  }
}
</style>
