<script setup lang="ts">
import { RouterView } from 'vue-router'
import { useViewportScale } from '@/composables/useViewportScale'

// Scale the fixed 1024x600 stage to fit the current viewport (kiosk: scale = 1).
useViewportScale()
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
