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

      <div v-if="cart.hasNothing" class="empty">
        <span class="empty-icon">🛒</span>
        <p>Chưa có món nào trong đơn hàng</p>
      </div>

      <div v-else class="items">
        <!-- Draft: still editable, not sent yet -->
        <CartItem v-for="item in cart.items" :key="item.foodItem.id" :item="item" />

        <!-- Already sent to the kitchen (confirmed by voice or by this screen) — read-only -->
        <section v-if="cart.orderedItems.length" class="ordered">
          <h3 class="ordered-head">
            <i class="ti ti-chef-hat" aria-hidden="true"></i>
            Đã gửi bếp
          </h3>
          <div v-for="item in cart.orderedItems" :key="item.foodItem.id" class="ordered-row">
            <span class="ordered-qty">{{ item.quantity }}×</span>
            <span class="ordered-name">{{ item.foodItem.name }}</span>
            <span class="ordered-price">{{ formatPrice(item.foodItem.price * item.quantity) }}</span>
          </div>
          <div class="ordered-total">
            <span>Tạm tính phần đã đặt</span>
            <strong>{{ formatPrice(cart.orderedTotal) }}</strong>
          </div>
        </section>
      </div>

      <footer v-if="!cart.hasNothing" class="drawer-footer">
        <template v-if="!cart.isEmpty">
          <CartSummary />
          <p v-if="error" class="order-error">{{ error }}</p>
          <TouchButton
            variant="primary"
            block
            :disabled="submitting"
            @click="$emit('confirm')"
          >
            {{ submitting ? 'Đang gửi đơn…' : 'Xác Nhận Đặt Món' }}
          </TouchButton>
        </template>
        <!-- Everything ordered (e.g. by voice) → the guest can go straight to the bill -->
        <TouchButton
          v-if="cart.orderedItems.length"
          :variant="cart.isEmpty ? 'primary' : 'secondary'"
          block
          :disabled="paying"
          @click="$emit('pay')"
        >
          <i class="ti ti-qrcode" aria-hidden="true"></i>
          {{ paying ? 'Đang lấy hoá đơn…' : 'Thanh toán' }}
        </TouchButton>
      </footer>
    </aside>
  </Transition>
</template>

<script setup lang="ts">
import { useCartStore } from '@/stores/cart'
import { formatPrice } from '@/utils/format'
import CartItem from './CartItem.vue'
import CartSummary from './CartSummary.vue'
import TouchButton from '@/components/common/TouchButton.vue'

defineProps<{ open: boolean; submitting?: boolean; paying?: boolean; error?: string | null }>()

defineEmits<{
  (e: 'close'): void
  (e: 'confirm'): void
  (e: 'pay'): void
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
  box-shadow: -12px 0 40px rgba(31, 27, 22, 0.16);
  z-index: 100;
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.875rem 1.25rem;
  border-bottom: 1px solid var(--color-border);
}

.drawer-header h2 {
  font-family: var(--font-display);
  font-size: 1.35rem;
  font-weight: 600;
  margin: 0;
}

.close-btn {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: var(--radius-full);
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 1.0625rem;
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
  padding: 0 1.25rem;
}

.drawer-footer {
  padding: 0.875rem 1.25rem;
  border-top: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  background: var(--color-surface);
}

.drawer-footer :deep(.touch-button) {
  min-height: 2.75rem;
  font-size: 1rem;
}

.ordered {
  margin: 0.75rem 0 1rem;
  padding: 0.75rem;
  background: var(--color-bg);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md, 12px);
}

.ordered-head {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin: 0 0 0.5rem;
  font-size: 0.875rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--color-text-muted);
  text-transform: uppercase;
}

.ordered-row {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  padding: 0.25rem 0;
  font-size: 0.9375rem;
}

.ordered-qty {
  flex: 0 0 auto;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--color-accent);
}

.ordered-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ordered-price {
  flex: 0 0 auto;
  font-variant-numeric: tabular-nums;
  color: var(--color-text-muted);
}

.ordered-total {
  display: flex;
  justify-content: space-between;
  margin-top: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--color-border);
  font-size: 0.9375rem;
}

.order-error {
  margin: 0;
  font-size: 0.875rem;
  color: var(--color-danger, #d9534f);
  text-align: center;
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
