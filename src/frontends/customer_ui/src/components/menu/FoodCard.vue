<template>
  <div class="food-card" role="button" @click="ui.openDetail(item)">
    <div class="image-wrapper">
      <img :src="item.image" :alt="item.name" loading="lazy" />
      <Transition name="badge-pop">
        <div v-if="quantity > 0" class="quantity-badge">{{ quantity }}</div>
      </Transition>
    </div>
    <div class="info">
      <h3 class="name">{{ item.name }}</h3>
      <p class="description">{{ item.description }}</p>
      <div class="footer">
        <span class="price">{{ formatPrice(item.price) }}</span>
        <div v-if="quantity > 0" class="stepper" @click.stop>
          <button class="step-btn" type="button" aria-label="Bớt" @click="cart.decrement(item.id)">
            −
          </button>
          <span class="step-qty">{{ quantity }}</span>
          <button class="step-btn" type="button" aria-label="Thêm" @click="cart.increment(item.id)">
            +
          </button>
        </div>
        <button v-else class="add-btn" type="button" @click.stop="cart.addItem(item)">
          + Thêm
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useCartStore } from '@/stores/cart'
import { useUiStore } from '@/stores/ui'
import type { FoodItem } from '@/types'
import { formatPrice } from '@/utils/format'

const props = defineProps<{ item: FoodItem }>()
const cart = useCartStore()
const ui = useUiStore()

const quantity = computed(() => cart.quantityFor(props.item.id))
</script>

<style scoped>
.food-card {
  background: var(--color-surface);
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  display: flex;
  flex-direction: column;
  height: 280px;
}

.food-card:active {
  transform: scale(0.98);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}

.image-wrapper {
  position: relative;
  width: 100%;
  height: 140px;
  overflow: hidden;
  background: #f0f0f0;
}

.image-wrapper img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.quantity-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  background: var(--color-primary);
  color: #fff;
  font-weight: 700;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
}

.info {
  padding: 0.75rem;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.name {
  font-size: 1.125rem;
  font-weight: 700;
  margin: 0 0 0.25rem 0;
  color: var(--color-text);
}

.description {
  font-size: 0.875rem;
  color: var(--color-text-muted);
  margin: 0;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  line-clamp: 1;
  -webkit-box-orient: vertical;
}

.footer {
  margin-top: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.price {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--color-primary);
}

.add-btn {
  background: transparent;
  color: #16a34a;
  border: 1.5px solid #16a34a;
  padding: 0 0.875rem;
  height: 32px;
  border-radius: var(--radius-full);
  font-family: inherit;
  font-weight: 700;
  font-size: 0.8125rem;
  white-space: nowrap;
}

.add-btn:active {
  background: #16a34a;
  color: #fff;
  transform: scale(0.94);
}

.stepper {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.step-btn {
  width: 16px;
  height: 16px;
  border: none;
  border-radius: var(--radius-full);
  background: #16a34a;
  color: #fff;
  font-size: 0.75rem;
  font-weight: 700;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.step-btn:active {
  transform: scale(0.9);
  background: #15803d;
}

.step-qty {
  min-width: 0.75rem;
  text-align: center;
  font-size: 0.8125rem;
  font-weight: 700;
  color: var(--color-text);
}

.badge-pop-enter-active {
  transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.badge-pop-enter-from {
  transform: scale(0);
}
</style>
