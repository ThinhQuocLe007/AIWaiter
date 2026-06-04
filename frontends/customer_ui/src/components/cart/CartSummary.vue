<template>
  <div class="cart-summary">
    <div class="row">
      <span class="label">Số món</span>
      <span class="value">{{ cart.totalQuantity }}</span>
    </div>
    <div class="row total">
      <span class="label">Tổng cộng</span>
      <span class="total-price">{{ formatPrice(cart.totalPrice) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useCartStore } from '@/stores/cart'
import { formatPrice } from '@/utils/format'

const cart = useCartStore()
</script>

<style scoped>
.cart-summary {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.label {
  font-size: 1rem;
  color: var(--color-text-muted);
}

.value {
  font-size: 1rem;
  font-weight: 600;
}

.row.total .label {
  font-size: 1.125rem;
  color: var(--color-text);
  font-weight: 600;
}

.total-price {
  font-size: 1.75rem;
  font-weight: 800;
  color: var(--color-primary);
}
</style>
