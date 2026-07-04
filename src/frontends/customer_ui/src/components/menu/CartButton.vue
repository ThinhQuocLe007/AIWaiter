<template>
  <button class="cart-button" type="button" aria-label="Open cart">
    <span class="cart-icon">🛒</span>
    <Transition name="badge-pop">
      <span v-if="count > 0" class="badge">{{ count }}</span>
    </Transition>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useCartStore } from '@/stores/cart'

const cart = useCartStore()
// Draft + already-sent-to-kitchen: the badge shows everything the guest has in play.
const count = computed(() => cart.badgeCount)
</script>

<style scoped>
.cart-button {
  position: relative;
  width: 3.5rem;
  height: 3.5rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
  display: flex;
  align-items: center;
  justify-content: center;
}

.cart-icon {
  font-size: 1.75rem;
  line-height: 1;
}

.badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 1.5rem;
  height: 1.5rem;
  padding: 0 0.35rem;
  border-radius: var(--radius-full);
  background: var(--color-primary);
  color: #fff;
  font-size: 0.875rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 6px rgba(31, 27, 22, 0.2);
}

.badge-pop-enter-active {
  transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.badge-pop-enter-from {
  transform: scale(0);
}
</style>
