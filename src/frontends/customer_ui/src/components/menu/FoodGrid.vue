<template>
  <div class="food-grid">
    <template v-if="loading">
      <LoadingSkeleton v-for="n in 6" :key="n" />
    </template>

    <template v-else-if="items.length > 0">
      <FoodCard v-for="item in items" :key="item.id" :item="item" />
    </template>

    <div v-else class="empty-state">
      <span class="empty-icon">🍽️</span>
      <p>Chưa có món trong danh mục này</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import FoodCard from './FoodCard.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import type { FoodItem } from '@/types'

withDefaults(
  defineProps<{
    items: FoodItem[]
    loading?: boolean
  }>(),
  {
    loading: false,
  },
)
</script>

<style scoped>
.food-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}

.empty-state {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 3rem 0;
  color: var(--color-text-muted);
  font-size: 1.125rem;
}

.empty-icon {
  font-size: 3rem;
}
</style>
