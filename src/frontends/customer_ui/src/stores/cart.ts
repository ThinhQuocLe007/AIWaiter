import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { CartItem, FoodItem } from '@/types'

export const useCartStore = defineStore('cart', () => {
  const items = ref<CartItem[]>([])

  // Total price in VND
  const totalPrice = computed(() =>
    items.value.reduce((sum, item) => sum + item.foodItem.price * item.quantity, 0),
  )

  // Total quantity (for the cart badge)
  const totalQuantity = computed(() =>
    items.value.reduce((sum, item) => sum + item.quantity, 0),
  )

  const isEmpty = computed(() => items.value.length === 0)

  // Add an item to the cart (or increment if it already exists)
  function addItem(foodItem: FoodItem) {
    const existing = items.value.find((i) => i.foodItem.id === foodItem.id)
    if (existing) {
      existing.quantity++
    } else {
      items.value.push({ foodItem, quantity: 1 })
    }
  }

  function increment(foodId: string) {
    const item = items.value.find((i) => i.foodItem.id === foodId)
    if (item) item.quantity++
  }

  // Decrement quantity, removing the item when it reaches zero
  function decrement(foodId: string) {
    const item = items.value.find((i) => i.foodItem.id === foodId)
    if (item) {
      item.quantity--
      if (item.quantity <= 0) {
        items.value = items.value.filter((i) => i.foodItem.id !== foodId)
      }
    }
  }

  function quantityFor(foodId: string): number {
    return items.value.find((i) => i.foodItem.id === foodId)?.quantity ?? 0
  }

  // Clear the cart (after order confirmation)
  function clear() {
    items.value = []
  }

  return {
    items,
    totalPrice,
    totalQuantity,
    isEmpty,
    addItem,
    increment,
    decrement,
    quantityFor,
    clear,
  }
})
