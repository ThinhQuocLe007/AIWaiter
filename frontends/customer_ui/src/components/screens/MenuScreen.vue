<template>
  <div class="menu-screen">
    <!-- Top bar -->
    <header class="top-bar">
      <div class="brand">
        <div class="logo-box">
          <i class="ti ti-tools-kitchen-2" aria-hidden="true"></i>
          <i class="ti ti-robot" aria-hidden="true"></i>
        </div>
        <div class="brand-text">
          <span class="brand-name">ROBO<span class="accent">DISH</span></span>
          <span class="tagline">SMART DINING</span>
        </div>
      </div>
      <CartButton @click="ui.openCart()" />
    </header>

    <!-- Category tabs -->
    <CategoryTabs
      :categories="menu.sortedCategories"
      :active="menu.activeCategoryId"
      @select="menu.setActiveCategory($event)"
    />

    <!-- Food grid -->
    <main class="food-grid-container">
      <SmartBannerCard />
      <FoodGrid :items="menu.itemsByActiveCategory" :loading="menu.isLoading" />
    </main>

    <!-- Cart drawer -->
    <CartDrawer :open="ui.cartOpen" @close="ui.closeCart()" @confirm="confirmOrder" />

    <!-- Food detail modal -->
    <FoodDetailModal />

    <!-- Voice AI bottom sheet -->
    <VoicePanel />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useMenuStore } from '@/stores/menu'
import { useUiStore } from '@/stores/ui'
import CategoryTabs from '@/components/menu/CategoryTabs.vue'
import CartButton from '@/components/menu/CartButton.vue'
import FoodGrid from '@/components/menu/FoodGrid.vue'
import FoodDetailModal from '@/components/menu/FoodDetailModal.vue'
import CartDrawer from '@/components/cart/CartDrawer.vue'
import SmartBannerCard from '@/components/voice/SmartBannerCard.vue'
import VoicePanel from '@/components/voice/VoicePanel.vue'

const router = useRouter()
const menu = useMenuStore()
const ui = useUiStore()

onMounted(() => {
  if (menu.foodItems.length === 0) {
    menu.loadMenu()
  }
})

function confirmOrder() {
  // TODO: Phase 2 - POST the order to the FastAPI backend and publish to ROS2.
  ui.closeCart()
  router.push('/confirmation')
}
</script>

<style scoped>
.menu-screen {
  width: 1024px;
  height: 600px;
  display: grid;
  grid-template-rows: 56px 1fr;
  grid-template-columns: 172px 1fr;
  background: var(--color-bg);
  position: relative;
  overflow: hidden;
}

.top-bar {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1.25rem;
  height: 56px;
  background: var(--color-surface);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  z-index: 10;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-box {
  width: 36px;
  height: 36px;
  background: #6c63ff;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
}

.logo-box i {
  font-size: 16px;
  color: #fff;
}

.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.1;
}

.brand-name {
  font-size: 20px;
  font-weight: 800;
  color: var(--color-text);
  letter-spacing: 0.08em;
}

.accent {
  color: #6c63ff;
}

.tagline {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-muted);
  letter-spacing: 0.15em;
}

.food-grid-container {
  padding: 1rem 1.25rem;
  overflow-y: auto;
  border-left: 1px solid var(--color-border);
}
</style>
