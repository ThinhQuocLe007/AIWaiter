<template>
  <div class="welcome-screen" role="button" @click="enterMenu">
    <div class="bg-decoration"></div>

    <div
      class="content"
      v-motion
      :initial="{ opacity: 0, y: 50 }"
      :enter="{ opacity: 1, y: 0, transition: { duration: 800 } }"
    >
      <div class="logo-box">
        <i class="ti ti-tools-kitchen-2"></i>
        <i class="ti ti-robot"></i>
      </div>

      <h1 class="title">ROBO<span class="accent">DISH</span></h1>
      <div class="rule" aria-hidden="true"></div>
      <p class="tagline">SMART DINING</p>
      <p class="subtitle">Chạm vào màn hình để bắt đầu</p>

      <div class="tap-indicator">
        <div class="pulse"></div>
        <span>👆</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

function enterMenu() {
  router.push('/menu')
}
</script>

<style scoped>
.welcome-screen {
  width: 1024px;
  height: 600px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg);
  position: relative;
  overflow: hidden;
}

.bg-decoration {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(
      circle at 20% 25%,
      rgba(168, 133, 62, 0.08) 0%,
      transparent 55%
    ),
    radial-gradient(circle at 82% 78%, rgba(168, 133, 62, 0.06) 0%, transparent 55%);
}

.content {
  text-align: center;
  z-index: 1;
}

.logo-box {
  width: 92px;
  height: 92px;
  background: var(--color-primary);
  border: 1px solid var(--color-accent);
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-bottom: 1.75rem;
  animation: float 4s ease-in-out infinite;
  box-shadow: 0 16px 40px rgba(31, 27, 22, 0.18);
}

.logo-box i {
  font-size: 34px;
  color: var(--color-accent);
}

.title {
  font-family: var(--font-display);
  font-size: 3.75rem;
  font-weight: 700;
  color: var(--color-text);
  margin: 0;
  letter-spacing: 0.06em;
}

.accent {
  color: var(--color-accent);
  font-style: italic;
}

.rule {
  width: 64px;
  height: 1px;
  margin: 1rem auto;
  background: var(--color-accent);
}

.tagline {
  font-size: 1rem;
  font-weight: 500;
  color: var(--color-accent-dark);
  letter-spacing: 0.4em;
  margin: 0 0 1.25rem 0;
}

.subtitle {
  font-size: 1.125rem;
  color: var(--color-text-muted);
  letter-spacing: 0.02em;
  margin: 0 0 3rem 0;
}

.tap-indicator {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 3rem;
}

.pulse {
  position: absolute;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: rgba(168, 133, 62, 0.22);
  animation: pulse 2s ease-in-out infinite;
}

@keyframes float {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-16px);
  }
}

@keyframes pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 0.6;
  }
  50% {
    transform: scale(1.5);
    opacity: 0;
  }
}
</style>
