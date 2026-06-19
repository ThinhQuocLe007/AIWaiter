<template>
  <section class="menu-section">
    <header class="section-head">
      <span v-if="section.icon" class="section-icon">{{ section.icon }}</span>
      <h2 class="section-title">{{ section.name }}</h2>
    </header>

    <div class="groups">
      <DishGroupRow v-for="group in section.groups" :key="group.id" :group="group" />
    </div>
  </section>
</template>

<script setup lang="ts">
import DishGroupRow from './DishGroupRow.vue'
import type { MenuSectionData } from '@/stores/menu'

defineProps<{ section: MenuSectionData }>()
</script>

<style scoped>
.menu-section {
  scroll-margin-top: 0.5rem;
}

.section-head {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0;
  margin-bottom: 0.25rem;
  background: var(--color-bg);
  border-bottom: 2px solid var(--color-primary);
}

.section-icon {
  font-size: 1.25rem;
}

.section-title {
  font-size: 1.125rem;
  font-weight: 800;
  margin: 0;
  color: var(--color-text);
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.groups {
  display: flex;
  flex-direction: column;
}
</style>
