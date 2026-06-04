import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { FoodItem } from '@/types'

export const useUiStore = defineStore('ui', () => {
  const cartOpen = ref(false)
  const detailItem = ref<FoodItem | null>(null)

  function openCart() {
    cartOpen.value = true
  }

  function closeCart() {
    cartOpen.value = false
  }

  function toggleCart() {
    cartOpen.value = !cartOpen.value
  }

  function openDetail(item: FoodItem) {
    detailItem.value = item
  }

  function closeDetail() {
    detailItem.value = null
  }

  return {
    cartOpen,
    detailItem,
    openCart,
    closeCart,
    toggleCart,
    openDetail,
    closeDetail,
  }
})
