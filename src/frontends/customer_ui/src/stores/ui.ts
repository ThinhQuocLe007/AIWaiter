import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { FoodItem } from '@/types'

export const useUiStore = defineStore('ui', () => {
  const cartOpen = ref(false)
  const detailItem = ref<FoodItem | null>(null)

  // Which physical table this tablet is attached to (1..6, see restaurant_positions.md).
  // Single source for both display and POST /orders. Defaults to 1 if VITE_TABLE_ID unset.
  const tableId = ref(Number(import.meta.env.VITE_TABLE_ID ?? 1) || 1)

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
    tableId,
    openCart,
    closeCart,
    toggleCart,
    openDetail,
    closeDetail,
  }
})
