<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { RouterView } from 'vue-router'
import { useViewportScale } from '@/composables/useViewportScale'
import { useVoiceStore } from '@/stores/voice'

// Scale the fixed 1024x600 stage to fit the current viewport (kiosk: scale = 1).
useViewportScale()

// Open the voice mirror (role=customer WS) for the whole app lifetime so the assistant panel can
// pop up the moment the robot hears this table speak — even before the guest taps the banner.
const voice = useVoiceStore()
onMounted(() => voice.connect())
onUnmounted(() => voice.disconnect())
</script>

<template>
  <div class="app-container">
    <RouterView v-slot="{ Component }">
      <Transition name="page" mode="out-in">
        <component :is="Component" />
      </Transition>
    </RouterView>
  </div>
</template>

<style>
.app-container {
  width: 1024px;
  height: 600px;
  overflow: hidden;
  position: relative;
  background: var(--color-bg);
  flex: 0 0 auto;
  transform: scale(var(--app-scale, 1));
  transform-origin: center center;
}

.page-enter-active,
.page-leave-active {
  transition: opacity 0.3s ease;
}
.page-enter-from,
.page-leave-to {
  opacity: 0;
}
</style>
