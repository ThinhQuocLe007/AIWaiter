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
  color: #fff;
  background: linear-gradient(110deg, var(--color-ai-dark) 0%, var(--color-ai) 45%, var(--color-ai-light) 100%);
  box-shadow: 0 6px 18px rgba(2, 132, 199, 0.35);
}

.smart-banner:active {
  transform: scale(0.99);
}

.banner-bot {
  position: absolute;
  right: -8px;
  bottom: -16px;
  font-size: 8rem;
  opacity: 0.15;
  pointer-events: none;
}

.banner-content {
  position: relative;
  z-index: 1;
  max-width: 80%;
}

.banner-tag {
  display: inline-block;
  background: rgba(255, 255, 255, 0.2);
  font-size: 0.625rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 0.15rem 0.6rem;
  border-radius: var(--radius-full);
  margin-bottom: 0.4rem;
}

.banner-title {
  font-size: 1.15rem;
  font-weight: 800;
  margin: 0 0 0.25rem 0;
}

.banner-subtitle {
  font-size: 0.75rem;
  line-height: 1.4;
  color: rgba(255, 255, 255, 0.88);
  margin: 0 0 0.75rem 0;
}

.banner-cta {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: #fff;
  color: var(--color-ai-dark);
  font-family: inherit;
  font-weight: 800;
  font-size: 0.8125rem;
  min-height: 0;
  min-width: 0;
  padding: 0.55rem 1rem;
  border: none;
  border-radius: var(--radius-sm);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
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
