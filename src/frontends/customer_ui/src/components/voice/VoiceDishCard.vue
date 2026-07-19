<template>
  <div class="dish-card">
    <img v-if="item.image" :src="item.image" :alt="item.name" class="dish-img" loading="lazy" />
    <!-- No photo for this dish: its category icon (🥤, 🦪, …) beats a generic plate. -->
    <div v-else class="dish-img dish-img-placeholder" aria-hidden="true">{{ categoryIcon }}</div>
    <div class="dish-info">
      <span class="dish-name">{{ item.name }}</span>
      <span class="dish-price">{{ formatPrice(item.price) }}</span>
    </div>
    <!-- Tap-to-order next to the AI's suggestion: quicker than saying "chốt món" out loud.
         Dark-theme twin of menu/AddControl (its colors assume the light background). -->
    <div v-if="quantity > 0" class="stepper" @click.stop>
      <button class="step-btn" type="button" aria-label="Bớt" @click="cart.decrement(item.id)">−</button>
      <span class="step-qty">{{ quantity }}</span>
      <button class="step-btn" type="button" aria-label="Thêm" @click="cart.increment(item.id)">+</button>
    </div>
    <button v-else class="add-btn" type="button" @click.stop="cart.addItem(item)">+ Thêm</button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useCartStore } from '@/stores/cart'
import { useMenuStore } from '@/stores/menu'
import { formatPrice } from '@/utils/format'
import type { FoodItem } from '@/types'

const props = defineProps<{ item: FoodItem }>()
const cart = useCartStore()
const menu = useMenuStore()
const quantity = computed(() => cart.quantityFor(props.item.id))
const categoryIcon = computed(
  () => menu.categories.find((c) => c.id === props.item.categoryId)?.icon ?? '🍽️',
)
</script>

<style scoped>
.dish-card {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  background: #2A2620;
  border: 1px solid #3A352D;
  border-radius: var(--radius-md);
  padding: 0.45rem 0.55rem;
}

.dish-img {
  width: 52px;
  height: 52px;
  border-radius: 10px;
  object-fit: cover;
  flex: 0 0 auto;
  background: #F5F1E8;
}

.dish-img-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.4rem;
  background: #34302A;
}

.dish-info {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  min-width: 0;
  flex: 1;
}

.dish-name {
  font-size: 0.75rem;
  font-weight: 600;
  color: #F5F1E8;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.dish-price {
  font-size: 0.78rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--color-accent);
}

.add-btn {
  flex: 0 0 auto;
  background: var(--color-accent);
  color: #1F1B16;
  border: none;
  font-family: inherit;
  font-weight: 700;
  font-size: 0.72rem;
  min-height: 0;
  min-width: 0;
  padding: 0.4rem 0.7rem;
  border-radius: var(--radius-sm);
  white-space: nowrap;
}

.add-btn:active {
  background: var(--color-accent-dark);
  transform: scale(0.95);
}

.stepper {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex: 0 0 auto;
}

.step-btn {
  width: 28px;
  height: 28px;
  min-width: 0;
  min-height: 0;
  border: none;
  border-radius: var(--radius-full);
  background: var(--color-accent);
  color: #1F1B16;
  font-size: 1rem;
  font-weight: 700;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.step-btn:active {
  transform: scale(0.9);
  background: var(--color-accent-dark);
}

.step-qty {
  min-width: 1.1rem;
  text-align: center;
  font-size: 0.8rem;
  font-weight: 700;
  color: #F5F1E8;
}
</style>
