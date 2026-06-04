<template>
  <Transition name="fade">
    <div v-if="item" class="backdrop" @click="ui.closeDetail()"></div>
  </Transition>
  <Transition name="pop">
    <div v-if="item" class="modal" role="dialog" aria-modal="true">
      <button class="close-btn" type="button" aria-label="Đóng" @click="ui.closeDetail()">
        ✕
      </button>

      <div class="image-wrapper">
        <img :src="item.image" :alt="item.name" />
      </div>

      <div class="body">
        <div class="title-row">
          <h2 class="name">{{ item.name }}</h2>
          <span v-if="item.dietType" class="diet" :class="dietClass">{{ item.dietType }}</span>
        </div>

        <span class="price">{{ formatPrice(item.price) }}</span>

        <p class="description">{{ item.description }}</p>

        <section v-if="item.ingredients" class="field">
          <h3 class="label">Thành phần</h3>
          <p class="value">{{ item.ingredients }}</p>
        </section>

        <section v-if="item.tasteProfile" class="field">
          <h3 class="label">Hương vị</h3>
          <p class="value">{{ item.tasteProfile }}</p>
        </section>

        <section v-if="item.tags && item.tags.length" class="field">
          <h3 class="label">Tags</h3>
          <div class="tags">
            <span v-for="tag in item.tags" :key="tag" class="tag">{{ tag }}</span>
          </div>
        </section>
      </div>

      <footer class="footer">
        <div v-if="quantity > 0" class="stepper">
          <button class="step-btn" type="button" aria-label="Bớt" @click="cart.decrement(item.id)">
            −
          </button>
          <span class="qty">{{ quantity }}</span>
          <button class="step-btn" type="button" aria-label="Thêm" @click="cart.increment(item.id)">
            +
          </button>
        </div>
        <TouchButton v-else variant="primary" block @click="cart.addItem(item)">
          + Thêm vào đơn
        </TouchButton>
      </footer>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useCartStore } from '@/stores/cart'
import { useUiStore } from '@/stores/ui'
import { formatPrice } from '@/utils/format'
import TouchButton from '@/components/common/TouchButton.vue'

const ui = useUiStore()
const cart = useCartStore()

const item = computed(() => ui.detailItem)
const quantity = computed(() => (item.value ? cart.quantityFor(item.value.id) : 0))
const dietClass = computed(() =>
  item.value?.dietType === 'chay' ? 'diet-veg' : 'diet-meat',
)
</script>

<style scoped>
.backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 199;
}

.modal {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 520px;
  max-height: 560px;
  background: var(--color-surface);
  border-radius: var(--radius-md);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  z-index: 200;
}

.close-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 40px;
  height: 40px;
  border: none;
  border-radius: var(--radius-full);
  background: rgba(0, 0, 0, 0.5);
  color: #fff;
  font-size: 1.125rem;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
}

.image-wrapper {
  width: 100%;
  height: 200px;
  flex-shrink: 0;
  background: #f0f0f0;
}

.image-wrapper img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.body {
  padding: 1.25rem 1.5rem;
  overflow-y: auto;
  flex: 1;
}

.title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.name {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
  color: var(--color-text);
}

.diet {
  flex-shrink: 0;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.25rem 0.625rem;
  border-radius: var(--radius-full);
  text-transform: capitalize;
}

.diet-meat {
  background: #fdecea;
  color: #c0392b;
}

.diet-veg {
  background: #e8f5e9;
  color: #2e7d32;
}

.price {
  display: block;
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-primary);
  margin-top: 0.25rem;
}

.description {
  font-size: 0.95rem;
  line-height: 1.5;
  color: var(--color-text);
  margin: 0.75rem 0 0;
}

.field {
  margin-top: 1rem;
}

.label {
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--color-text-muted);
  margin: 0 0 0.375rem;
}

.value {
  font-size: 0.95rem;
  line-height: 1.5;
  color: var(--color-text);
  margin: 0;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.tag {
  font-size: 0.8rem;
  padding: 0.25rem 0.75rem;
  border-radius: var(--radius-full);
  background: var(--color-bg);
  color: var(--color-text-muted);
}

.footer {
  flex-shrink: 0;
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--color-border);
  background: var(--color-surface);
}

.stepper {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1.5rem;
}

.step-btn {
  width: 56px;
  height: 56px;
  border: none;
  border-radius: var(--radius-full);
  background: #16a34a;
  color: #fff;
  font-size: 1.75rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

.step-btn:active {
  transform: scale(0.94);
  background: #15803d;
}

.qty {
  font-size: 1.5rem;
  font-weight: 700;
  min-width: 2rem;
  text-align: center;
  color: var(--color-text);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.pop-enter-active {
  transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.25s ease;
}
.pop-leave-active {
  transition: transform 0.2s ease, opacity 0.2s ease;
}
.pop-enter-from,
.pop-leave-to {
  opacity: 0;
  transform: translate(-50%, -50%) scale(0.9);
}
</style>
