<template>
  <div class="dish-group" :class="{ multi: isMulti }">
    <!-- Optional thumbnail; omitted entirely when no image (text-first) -->
    <img
      v-if="group.image"
      class="thumb"
      :src="group.image"
      :alt="group.name"
      loading="lazy"
      @click="openFirst"
    />

    <div class="content">
      <!-- Header: group/dish name + price (range for multi-option groups) -->
      <div class="head" @click="openFirst">
        <h3 class="name">
          <span v-if="isMulti" class="star" aria-hidden="true">⭐</span>
          {{ group.name }}
        </h3>
        <span class="price">{{ group.priceLabel }}đ</span>
      </div>

      <!-- Single dish: short taste hint -->
      <p v-if="!isMulti && firstItem.tasteProfile" class="hint" @click="openFirst">
        {{ firstItem.tasteProfile }}
      </p>

      <!-- Multi-option group: one row per option -->
      <ul v-if="isMulti" class="options">
        <li v-for="item in group.items" :key="item.id" class="option">
          <button class="opt-label" type="button" @click="ui.openDetail(item)">
            {{ optionLabel(item) }}
          </button>
          <span class="opt-price">{{ formatPrice(item.price) }}</span>
          <AddControl :item="item" />
        </li>
      </ul>
    </div>

    <!-- Single dish: add control on the right -->
    <div v-if="!isMulti" class="single-action">
      <AddControl :item="firstItem" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useUiStore } from '@/stores/ui'
import type { DishGroup, FoodItem } from '@/types'
import { formatPrice } from '@/utils/format'
import AddControl from './AddControl.vue'

const props = defineProps<{ group: DishGroup }>()
const ui = useUiStore()

const isMulti = computed(() => props.group.items.length > 1)
const firstItem = computed(() => props.group.items[0])

function openFirst() {
  ui.openDetail(firstItem.value)
}

// Strip the shared group prefix so "Cơm Chiên Tỏi" reads as "Tỏi".
function optionLabel(item: FoodItem): string {
  const prefix = props.group.name
  if (item.name.startsWith(prefix)) {
    const rest = item.name.slice(prefix.length).trim()
    return rest || item.name
  }
  return item.name
}
</script>

<style scoped>
.dish-group {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.625rem 0;
  border-bottom: 1px dashed var(--color-border);
}

.thumb {
  width: 64px;
  height: 64px;
  border-radius: var(--radius-sm);
  object-fit: cover;
  flex: 0 0 auto;
  background: #f0f0f0;
}

.content {
  flex: 1;
  min-width: 0;
}

.head {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
}

.name {
  font-size: 1rem;
  font-weight: 600;
  margin: 0;
  color: var(--color-text);
  flex: 1;
  min-width: 0;
}

.star {
  font-size: 0.875rem;
}

.price {
  font-size: 1rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--color-text);
  white-space: nowrap;
  flex: 0 0 auto;
}

.hint {
  font-size: 0.8125rem;
  color: var(--color-text-muted);
  margin: 0.15rem 0 0;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  line-clamp: 1;
  -webkit-box-orient: vertical;
}

.options {
  list-style: none;
  margin: 0.4rem 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.option {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.opt-label {
  flex: 1;
  min-width: 0;
  text-align: left;
  border: none;
  background: none;
  padding: 0;
  font-family: inherit;
  font-size: 0.875rem;
  color: var(--color-text);
}

.opt-price {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--color-text-muted);
  white-space: nowrap;
}

.single-action {
  flex: 0 0 auto;
  align-self: center;
}
</style>
