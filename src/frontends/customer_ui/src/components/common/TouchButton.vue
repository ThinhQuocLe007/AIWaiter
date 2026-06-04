<template>
  <button
    class="touch-button"
    :class="[`variant-${variant}`, { block }]"
    type="button"
  >
    <slot />
  </button>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'ghost'
    block?: boolean
  }>(),
  {
    variant: 'primary',
    block: false,
  },
)
</script>

<style scoped>
.touch-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  min-height: 3.5rem; /* 56px - primary action target */
  padding: 0 1.5rem;
  border: none;
  border-radius: var(--radius-full);
  font-family: inherit;
  font-size: 1.25rem;
  font-weight: 700;
  line-height: 1;
}

.touch-button.block {
  width: 100%;
}

.variant-primary {
  background: #16a34a;
  color: #fff;
}

.variant-secondary {
  background: var(--color-surface);
  color: var(--color-primary);
  border: 2px solid var(--color-primary);
}

.variant-ghost {
  background: transparent;
  color: var(--color-text-muted);
}

.touch-button:active {
  transform: scale(0.96);
}
</style>
