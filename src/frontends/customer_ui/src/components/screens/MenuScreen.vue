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

      <div class="search-box">
        <i class="ti ti-search" aria-hidden="true"></i>
        <input
          v-model="menu.searchQuery"
          type="text"
          class="search-input"
          placeholder="Tìm món ăn..."
        />
        <button
          v-if="menu.isSearching"
          class="search-clear"
          type="button"
          aria-label="Xóa tìm kiếm"
          @click="menu.clearSearch()"
        >
          ✕
        </button>
      </div>

      <CartButton @click="ui.openCart()" />
    </header>

    <!-- Left jump navigation -->
    <CategoryTabs
      :categories="menu.navItems"
      :active="menu.activeCategoryId"
      @select="scrollToSection"
    />

    <!-- Scrolling menu: Best Seller showcase + category sections -->
    <main ref="scrollEl" class="menu-scroll">
      <SmartBannerCard />

      <template v-if="menu.isLoading">
        <LoadingSkeleton v-for="n in 4" :key="n" />
      </template>

      <div v-else-if="menu.loadError" class="load-error">
        <span class="empty-icon">⚠️</span>
        <p>Không tải được menu từ máy chủ.</p>
        <p class="load-error-detail">{{ menu.loadError }}</p>
        <button class="retry-btn" type="button" @click="menu.loadMenu()">Thử lại</button>
      </div>

      <template v-else>
        <BestSellerSection
          v-if="!menu.isSearching && menu.bestSellers.length"
          :items="menu.bestSellers"
          :data-section-id="BEST_SELLER_ID"
        />

        <p v-if="menu.isSearching" class="search-meta">
          {{ menu.resultCount }} món khớp “{{ menu.searchQuery.trim() }}”
        </p>

        <MenuSection
          v-for="section in menu.displaySections"
          :key="section.id"
          :section="section"
          :data-section-id="section.id"
        />

        <div v-if="menu.isSearching && menu.resultCount === 0" class="empty-search">
          <span class="empty-icon">🔍</span>
          <p>Không tìm thấy món nào khớp “{{ menu.searchQuery.trim() }}”. Thử từ khác xem.</p>
        </div>
      </template>
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
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { BEST_SELLER_ID, useMenuStore } from '@/stores/menu'
import { useUiStore } from '@/stores/ui'
import CategoryTabs from '@/components/menu/CategoryTabs.vue'
import CartButton from '@/components/menu/CartButton.vue'
import BestSellerSection from '@/components/menu/BestSellerSection.vue'
import MenuSection from '@/components/menu/MenuSection.vue'
import FoodDetailModal from '@/components/menu/FoodDetailModal.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import CartDrawer from '@/components/cart/CartDrawer.vue'
import SmartBannerCard from '@/components/voice/SmartBannerCard.vue'
import VoicePanel from '@/components/voice/VoicePanel.vue'

const router = useRouter()
const menu = useMenuStore()
const ui = useUiStore()

const scrollEl = ref<HTMLElement>()
let observer: IntersectionObserver | null = null

function scrollToSection(id: string) {
  // Leave search mode first so every section exists in the DOM to scroll to.
  if (menu.isSearching) menu.clearSearch()
  menu.setActiveCategory(id)
  nextTick(() => {
    scrollEl.value
      ?.querySelector(`[data-section-id="${id}"]`)
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

// Highlight the nav item for whichever section currently sits near the top.
function setupObserver() {
  observer?.disconnect()
  if (!scrollEl.value) return
  observer = new IntersectionObserver(
    (entries) => {
      const visible = entries.filter((e) => e.isIntersecting)
      if (!visible.length) return
      visible.sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
      const id = visible[0].target.getAttribute('data-section-id')
      if (id) menu.setActiveCategory(id)
    },
    { root: scrollEl.value, rootMargin: '0px 0px -75% 0px', threshold: 0 },
  )
  scrollEl.value
    .querySelectorAll('[data-section-id]')
    .forEach((el) => observer!.observe(el))
}

onMounted(() => {
  if (menu.foodItems.length === 0) {
    menu.loadMenu()
  }
})

// The rendered section list changes on load and on every search; (re)wire the observer.
watch(
  () => `${menu.isSearching}|${menu.displaySections.length}`,
  () => nextTick(setupObserver),
  { immediate: true },
)

onUnmounted(() => observer?.disconnect())

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
  gap: 1rem;
  padding: 0 1.25rem;
  height: 56px;
  background: var(--color-surface);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  z-index: 10;
}

.search-box {
  position: relative;
  flex: 1 1 auto;
  max-width: 420px;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  height: 38px;
  padding: 0 0.75rem;
  background: var(--color-bg);
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius-full);
}

.search-box:focus-within {
  border-color: var(--color-primary);
}

.search-box i {
  font-size: 1.125rem;
  color: var(--color-text-muted);
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  min-width: 0;
  padding-right: 2.25rem; /* clear the absolutely-positioned ✕ button */
  border: none;
  background: none;
  outline: none;
  font-family: inherit;
  font-size: 0.9375rem;
  color: var(--color-text);
}

.search-clear {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 34px;
  height: 34px;
  padding: 0;
  margin: 0;
  border: none;
  border-radius: 50%;
  background: #6B6B6B;
  color: #fff;
  font-size: 0.8rem;
  display: grid;
  place-items: center;
  cursor: pointer;
}

.search-clear:active {
  transform: translateY(-50%) scale(0.9);
}

.search-meta {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--color-text-muted);
  margin: 0.25rem 0 0.5rem;
}

.empty-search {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 2.5rem 1rem;
  text-align: center;
  color: var(--color-text-muted);
}

.empty-icon {
  font-size: 2.5rem;
}

.load-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 2.5rem 1rem;
  text-align: center;
  color: var(--color-text-muted);
}

.load-error-detail {
  font-size: 0.8125rem;
  opacity: 0.7;
  word-break: break-word;
}

.retry-btn {
  margin-top: 0.5rem;
  padding: 0.5rem 1.5rem;
  border: none;
  border-radius: var(--radius-full);
  background: var(--color-primary);
  color: #fff;
  font-family: inherit;
  font-size: 0.9375rem;
  font-weight: 600;
  cursor: pointer;
}

.retry-btn:active {
  transform: scale(0.96);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-box {
  width: 36px;
  height: 36px;
  background: var(--color-ai);
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
  color: var(--color-ai);
}

.tagline {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-muted);
  letter-spacing: 0.15em;
}

.menu-scroll {
  padding: 0.5rem 1.25rem 1.5rem;
  overflow-y: auto;
  border-left: 1px solid var(--color-border);
}
</style>
