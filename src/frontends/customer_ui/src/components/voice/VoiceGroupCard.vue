<template>
  <div class="group-card">
    <!-- One representative photo stands for the whole family; the sub-line
         ("3 loại · 255.000 – 355.000") tells the guest it covers several options. -->
    <div class="gc-head">
      <img v-if="group.image" :src="group.image" :alt="group.name" class="gc-img" loading="lazy" />
      <div v-else class="gc-img gc-img-placeholder" aria-hidden="true">{{ categoryIcon }}</div>
      <div class="gc-title">
        <span class="gc-name">{{ group.name }}</span>
        <span class="gc-sub">{{ group.items.length }} loại · {{ group.priceLabel }}đ</span>
      </div>
    </div>

    <!-- Every option keeps its own price + add control: the photo is shared, the price is not. -->
    <ul class="gc-options">
      <li v-for="item in group.items" :key="item.id" class="gc-option">
        <span class="opt-label">{{ optionLabel(item) }}</span>
        <span class="opt-price">{{ formatPrice(item.price) }}</span>
        <div v-if="cart.quantityFor(item.id) > 0" class="stepper" @click.stop>
          <button class="step-btn" type="button" aria-label="Bớt" @click="cart.decrement(item.id)">−</button>
          <span class="step-qty">{{ cart.quantityFor(item.id) }}</span>
          <button class="step-btn" type="button" aria-label="Thêm" @click="cart.increment(item.id)">+</button>
        </div>
        <button v-else class="opt-add" type="button" :aria-label="`Thêm ${item.name}`" @click.stop="cart.addItem(item)">+</button>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useCartStore } from '@/stores/cart'
import { useMenuStore } from '@/stores/menu'
import { formatPrice } from '@/utils/format'
import type { DishGroup, FoodItem } from '@/types'

const props = defineProps<{ group: DishGroup }>()
const cart = useCartStore()
const menu = useMenuStore()

const categoryIcon = computed(
  () => menu.categories.find((c) => c.id === props.group.categoryId)?.icon ?? '🍽️',
)

// Strip the shared group prefix so "Lẩu Thái" reads as "Thái" under the "Lẩu" header.
function optionLabel(item: FoodItem): string {
  if (item.name.startsWith(props.group.name)) {
    const rest = item.name.slice(props.group.name.length).trim()
    return rest || item.name
  }
  return item.name
}
</script>

<style scoped>
.group-card {
  background: #2A2620;
  border: 1px solid #3A352D;
  border-radius: var(--radius-md);
  padding: 0.45rem 0.55rem;
}

.gc-head {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.gc-img {
  width: 52px;
  height: 52px;
  border-radius: 10px;
  object-fit: cover;
  flex: 0 0 auto;
  background: #F5F1E8;
}

.gc-img-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.4rem;
  background: #34302A;
}

.gc-title {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  min-width: 0;
}

.gc-name {
  font-size: 0.78rem;
  font-weight: 700;
  color: #F5F1E8;
}

.gc-sub {
  font-size: 0.7rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--color-accent);
}

.gc-options {
  list-style: none;
  margin: 0.35rem 0 0;
  padding: 0;
}

.gc-option {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.28rem 0;
}

.gc-option + .gc-option {
  border-top: 1px solid #34302A;
}

.opt-label {
  flex: 1;
  min-width: 0;
  font-size: 0.72rem;
  font-weight: 600;
  color: #E8E2D6;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.opt-price {
  flex: 0 0 auto;
  font-size: 0.72rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--color-accent);
}

.opt-add {
  flex: 0 0 auto;
  width: 26px;
  height: 26px;
  min-width: 0;
  min-height: 0;
  border: none;
  border-radius: var(--radius-full);
  background: var(--color-accent);
  color: #1F1B16;
  font-size: 0.95rem;
  font-weight: 700;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.opt-add:active {
  background: var(--color-accent-dark);
  transform: scale(0.9);
}

.stepper {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  flex: 0 0 auto;
}

.step-btn {
  width: 24px;
  height: 24px;
  min-width: 0;
  min-height: 0;
  border: none;
  border-radius: var(--radius-full);
  background: var(--color-accent);
  color: #1F1B16;
  font-size: 0.9rem;
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
  min-width: 1rem;
  text-align: center;
  font-size: 0.75rem;
  font-weight: 700;
  color: #F5F1E8;
}
</style>
