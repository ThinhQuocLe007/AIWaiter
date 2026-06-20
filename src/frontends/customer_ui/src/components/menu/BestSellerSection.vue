<template>
  <section class="bestseller">
    <header class="section-head">
      <span class="section-icon" aria-hidden="true">⭐</span>
      <h2 class="section-title">Best Seller</h2>
    </header>

    <div class="strip-wrap">
      <button
        v-show="canLeft"
        class="nav-arrow left"
        type="button"
        aria-label="Xem món trước"
        @click="scrollByDir(-1)"
      >
        ‹
      </button>

      <div ref="stripEl" class="strip" @scroll="updateArrows">
        <article
          v-for="item in items"
          :key="item.id"
          class="bs-card"
          role="button"
          @click="ui.openDetail(item)"
        >
          <div class="bs-image">
            <img v-if="item.image" :src="item.image" :alt="item.name" loading="lazy" />
            <div v-else class="bs-placeholder" aria-hidden="true">⭐</div>
          </div>
          <div class="bs-body">
            <h3 class="bs-name">{{ item.featuredName || item.name }}</h3>
            <p v-if="item.tasteProfile" class="bs-hint">{{ item.tasteProfile }}</p>
            <div class="bs-foot">
              <span class="bs-price">{{ formatPrice(item.price) }}</span>
              <AddControl :item="item" />
            </div>
          </div>
        </article>
      </div>

      <button
        v-show="canRight"
        class="nav-arrow right"
        type="button"
        aria-label="Xem món tiếp"
        @click="scrollByDir(1)"
      >
        ›
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { useUiStore } from '@/stores/ui'
import type { FoodItem } from '@/types'
import { formatPrice } from '@/utils/format'
import AddControl from './AddControl.vue'

const props = defineProps<{ items: FoodItem[] }>()
const ui = useUiStore()

const stripEl = ref<HTMLElement>()
const canLeft = ref(false)
const canRight = ref(false)

function updateArrows() {
  const el = stripEl.value
  if (!el) return
  canLeft.value = el.scrollLeft > 4
  canRight.value = el.scrollLeft + el.clientWidth < el.scrollWidth - 4
}

// Scroll by ~2 cards in the given direction (-1 left, 1 right).
function scrollByDir(dir: number) {
  const el = stripEl.value
  if (!el) return
  const card = el.querySelector('.bs-card') as HTMLElement | null
  const step = card ? card.offsetWidth + 12 : 180 // card width + gap
  el.scrollBy({ left: dir * step * 2, behavior: 'smooth' })
}

onMounted(() => nextTick(updateArrows))
watch(() => props.items.length, () => nextTick(updateArrows))
</script>

<style scoped>
.bestseller {
  scroll-margin-top: 0.5rem;
  margin-bottom: 1rem;
}

.section-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0;
  margin-bottom: 0.5rem;
  border-bottom: 1px solid var(--color-text);
}

.section-icon {
  font-size: 1.15rem;
}

.section-title {
  font-family: var(--font-display);
  font-size: 1.3rem;
  font-weight: 600;
  margin: 0;
  color: var(--color-text);
  letter-spacing: 0.01em;
}

.strip-wrap {
  position: relative;
}

.strip {
  display: flex;
  gap: 0.75rem;
  overflow-x: auto;
  padding-bottom: 0.5rem;
  scroll-snap-type: x mandatory;
  scroll-behavior: smooth;
}

.nav-arrow {
  position: absolute;
  top: calc(50% - 0.25rem);
  transform: translateY(-50%);
  z-index: 5;
  width: 40px;
  height: 40px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  background: var(--color-surface);
  color: var(--color-text);
  box-shadow: var(--shadow-md);
  font-size: 1.75rem;
  font-weight: 600;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.nav-arrow:active {
  transform: translateY(-50%) scale(0.92);
}

.nav-arrow.left {
  left: -6px;
}

.nav-arrow.right {
  right: -6px;
}

.bs-card {
  flex: 0 0 168px;
  width: 168px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  scroll-snap-align: start;
}

.bs-card:active {
  transform: scale(0.98);
}

.bs-image {
  width: 100%;
  height: 96px;
  background: var(--color-accent-soft);
}

.bs-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.bs-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2.5rem;
  color: var(--color-accent);
  background: var(--color-accent-soft);
}

.bs-body {
  padding: 0.5rem 0.625rem 0.625rem;
  display: flex;
  flex-direction: column;
  flex: 1;
}

.bs-name {
  font-size: 0.9375rem;
  font-weight: 700;
  margin: 0;
  color: var(--color-text);
  line-height: 1.2;
}

.bs-hint {
  font-size: 0.75rem;
  color: var(--color-text);
  margin: 0.2rem 0 0;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}

.bs-foot {
  margin-top: auto;
  padding-top: 0.4rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
}

.bs-price {
  font-size: 1rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--color-text);
  white-space: nowrap;
  text-align: center;
}
</style>
