<template>
  <nav class="category-tabs">
    <button
      v-for="category in categories"
      :key="category.id"
      class="tab"
      :class="{ active: category.id === active }"
      type="button"
      @click="$emit('select', category.id)"
    >
      <span v-if="category.icon" class="tab-icon">{{ category.icon }}</span>
      <span class="tab-name">{{ category.name }}</span>
    </button>
  </nav>
</template>

<script setup lang="ts">
interface NavItem {
  id: string
  name: string
  icon?: string
}

defineProps<{
  categories: NavItem[]
  active: string
}>()

defineEmits<{
  (e: 'select', categoryId: string): void
}>()
</script>

<style scoped>
.category-tabs {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.75rem 0.5rem;
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--color-bg);
  height: 100%;
  box-sizing: border-box;
}

.tab {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-height: 2.75rem;
  padding: 0.375rem 0.625rem;
  border: 2px solid transparent;
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: var(--color-text);
  font-family: inherit;
  font-size: 0.875rem;
  font-weight: 600;
  white-space: normal;
  text-align: left;
  line-height: 1.3;
  width: 100%;
  flex: 0 0 auto;
  transition: background 0.15s ease, color 0.15s ease;
}

.tab.active {
  background: var(--color-primary);
  color: #fff;
  box-shadow: 0 2px 8px rgba(230, 57, 70, 0.3);
}

.tab-icon {
  font-size: 1.125rem;
  flex-shrink: 0;
}
</style>
