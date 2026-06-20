<template>
  <div v-if="quantity > 0" class="stepper" @click.stop>
    <button class="step-btn" type="button" aria-label="Bớt" @click="cart.decrement(item.id)">−</button>
    <span class="step-qty">{{ quantity }}</span>
    <button class="step-btn" type="button" aria-label="Thêm" @click="cart.increment(item.id)">+</button>
  </div>
  <button v-else class="add-btn" type="button" @click.stop="cart.addItem(item)">+ Thêm</button>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useCartStore } from '@/stores/cart'
import type { FoodItem } from '@/types'

const props = defineProps<{ item: FoodItem }>()
const cart = useCartStore()
const quantity = computed(() => cart.quantityFor(props.item.id))
</script>

<style scoped>
.add-btn {
  background: transparent;
  color: var(--color-add);
  border: 1px solid var(--color-add);
  padding: 0 0.85rem;
  height: 30px;
  border-radius: var(--radius-sm);
  font-family: inherit;
  font-weight: 600;
  font-size: 0.8125rem;
  letter-spacing: 0.02em;
  white-space: nowrap;
  flex: 0 0 auto;
}

.add-btn:active {
  background: var(--color-add);
  color: #fff;
  transform: scale(0.94);
}

.stepper {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  flex: 0 0 auto;
}

.step-btn {
  width: 26px;
  height: 26px;
  border: none;
  border-radius: var(--radius-full);
  background: var(--color-add);
  color: #fff;
  font-size: 1rem;
  font-weight: 700;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.step-btn:active {
  transform: scale(0.9);
  background: var(--color-add-dark);
}

.step-qty {
  min-width: 1rem;
  text-align: center;
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--color-text);
}
</style>
