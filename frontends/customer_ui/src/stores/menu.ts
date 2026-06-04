import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { Category, FoodItem } from '@/types'
import { mockCategories, mockFoodItems } from '@/data/mockMenu'

export const useMenuStore = defineStore('menu', () => {
  const categories = ref<Category[]>([])
  const foodItems = ref<FoodItem[]>([])
  const isLoading = ref(false)
  const activeCategoryId = ref<string>('')

  const sortedCategories = computed(() =>
    [...categories.value].sort((a, b) => a.order - b.order),
  )

  const itemsByActiveCategory = computed(() =>
    foodItems.value.filter(
      (item) => item.categoryId === activeCategoryId.value && item.available,
    ),
  )

  // Load menu data. Uses mock data for now.
  // TODO: Phase 2 - fetch categories/items from the FastAPI backend.
  async function loadMenu() {
    isLoading.value = true
    // Simulate a short network delay so the loading skeleton is visible.
    await new Promise((resolve) => setTimeout(resolve, 400))
    categories.value = mockCategories
    foodItems.value = mockFoodItems
    const firstCategory = sortedCategories.value[0]
    if (!activeCategoryId.value && firstCategory) {
      activeCategoryId.value = firstCategory.id
    }
    isLoading.value = false
  }

  function setActiveCategory(categoryId: string) {
    activeCategoryId.value = categoryId
  }

  return {
    categories,
    foodItems,
    isLoading,
    activeCategoryId,
    sortedCategories,
    itemsByActiveCategory,
    loadMenu,
    setActiveCategory,
  }
})
