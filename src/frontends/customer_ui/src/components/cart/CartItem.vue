<template>
  <div class="cart-item">
    <img :src="item.foodItem.image" :alt="item.foodItem.name" />
    <div class="info">
      <h4 class="name">{{ item.foodItem.name }}</h4>
      <p class="unit-price">{{ formatPrice(item.foodItem.price) }} / phần</p>
      <p class="subtotal">{{ formatPrice(item.foodItem.price * item.quantity) }}</p>
    </div>
    <div class="controls">
      <button
        class="qty-btn"
        type="button"
        aria-label="Decrease quantity"
        @click="cart.decrement(item.foodItem.id)"
      >
        −
      </button>
      <span class="qty">{{ item.quantity }}</span>
      <button
        class="qty-btn"
        type="button"
        aria-label="Increase quantity"
        @click="cart.increment(item.foodItem.id)"
      >
        +
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useCartStore } from '@/stores/cart'
import type { CartItem } from '@/types'
import { formatPrice } from '@/utils/format'

defineProps<{ item: CartItem }>()
const cart = useCartStore()
</script>

<style scoped>
.cart-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 0;
  border-bottom: 1px solid var(--color-border);
}

.cart-item img {
  width: 60px;
  height: 60px;
  border-radius: var(--radius-sm);
  object-fit: cover;
  flex: 0 0 auto;
  background: #f0f0f0;
}

.info {
  flex: 1;
  min-width: 0;
}

.name {
  font-size: 1rem;
  font-weight: 700;
  margin: 0 0 0.15rem 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.unit-price {
  font-size: 0.8125rem;
  color: var(--color-text-muted);
  margin: 0;
}

.subtotal {
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-primary);
  margin: 0.15rem 0 0 0;
}

.controls {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 0 0 auto;
}

.qty-btn {
  width: 44px;
  height: 44px;
  border: none;
  border-radius: var(--radius-full);
  background: #16a34a;
  color: #fff;
  font-size: 1.5rem;
  font-weight: 700;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.qty-btn:active {
  background: #15803d;
  transform: scale(0.94);
}

.qty {
  min-width: 1.75rem;
  text-align: center;
  font-size: 1.25rem;
  font-weight: 700;
}
</style>
