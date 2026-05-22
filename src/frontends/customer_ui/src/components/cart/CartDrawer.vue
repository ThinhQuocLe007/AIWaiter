<template>
  <!-- Positioned absolutely within the .menu-screen so it stays inside the
       scaled 1024x600 stage instead of the raw viewport. -->
  <Transition name="fade">
    <div v-if="open" class="backdrop" @click="$emit('close')"></div>
  </Transition>
  <Transition name="slide">
    <aside v-if="open" class="drawer">
      <header class="drawer-header">
        <h2>Đơn hàng của bạn</h2>
        <button class="close-btn" type="button" aria-label="Close cart" @click="$emit('close')">
          ✕
        </button>
      </header>

      <div v-if="cart.isEmpty" class="empty">
        <span class="empty-icon">🛒</span>
        <p>Chưa có món nào trong đơn hàng</p>
      </div>

      <div v-else class="items">
        <CartItem v-for="item in cart.items" :key="item.foodItem.id" :item="item" />
      </div>

      <footer v-if="!cart.isEmpty" class="drawer-footer">
        <CartSummary />
        <TouchButton variant="primary" block @click="$emit('confirm')">
          Xác Nhận Đặt Món
        </TouchButton>
      </footer>
    </aside>
  </Transition>
</template>

<script setup lang="ts">
import { useCartStore } from '@/stores/cart'
import CartItem from './CartItem.vue'
import CartSummary from './CartSummary.vue'
import TouchButton from '@/components/common/TouchButton.vue'

defineProps<{ open: boolean }>()

defineEmits<{
  (e: 'close'): void
  (e: 'confirm'): void
}>()

const cart = useCartStore()
</script>

<style scoped>
.backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 99;
}

.drawer {
  position: absolute;
  top: 0;
  right: 0;
  width: 400px;
  height: 600px;
  background: var(--color-surface);
  display: flex;
  flex-direction: column;
  box-shadow: -4px 0 16px rgba(0, 0, 0, 0.15);
  z-index: 100;
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--color-border);
}

.drawer-header h2 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
}

.close-btn {
  width: 44px;
  height: 44px;
  border: none;
  border-radius: var(--radius-full);
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 1.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  color: var(--color-text-muted);
  font-size: 1.125rem;
}

.empty-icon {
  font-size: 3rem;
  opacity: 0.6;
}

.items {
  flex: 1;
  overflow-y: auto;
  padding: 0 1.5rem;
}

.drawer-footer {
  padding: 1.25rem 1.5rem;
  border-top: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: 1rem;
  background: var(--color-surface);
}

.slide-enter-active,
.slide-leave-active {
  transition: transform 0.3s ease;
}
.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
