import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { Category, DishGroup, FoodItem } from '@/types'
import { adaptMenu } from '@/data/menuAdapter'
import { fetchMenu } from '@/data/api'

export const BEST_SELLER_ID = 'best-seller'

export interface MenuSectionData {
  id: string
  name: string
  icon?: string
  groups: DishGroup[]
}

export const useMenuStore = defineStore('menu', () => {
  const categories = ref<Category[]>([])
  const foodItems = ref<FoodItem[]>([])
  const bestSellers = ref<FoodItem[]>([])
  const groupsByCategory = ref<Record<string, DishGroup[]>>({})
  const isLoading = ref(false)
  // Holds a fetch failure message so the screen can show a retry instead of a blank menu.
  const loadError = ref<string | null>(null)
  // The id of the section currently scrolled into view (drives the nav highlight).
  const activeCategoryId = ref<string>(BEST_SELLER_ID)
  // Free-text dish search (diacritic-insensitive).
  const searchQuery = ref('')

  const sortedCategories = computed(() =>
    [...categories.value].sort((a, b) => a.order - b.order),
  )

  // Content sections rendered top-to-bottom (categories only; Best Seller is a
  // separate showcase rendered above these).
  const sections = computed<MenuSectionData[]>(() =>
    sortedCategories.value.map((c) => ({
      id: c.id,
      name: c.name,
      icon: c.icon,
      groups: groupsByCategory.value[c.id] ?? [],
    })),
  )

  // Left-hand jump navigation: Best Seller pinned on top, then categories.
  const navItems = computed(() => [
    { id: BEST_SELLER_ID, name: 'Best Seller', icon: '⭐' },
    ...sortedCategories.value.map((c) => ({ id: c.id, name: c.name, icon: c.icon })),
  ])

  // Strip Vietnamese diacritics so "so" matches "sò", "soup" matches "Súp", etc.
  function normalize(s: string): string {
    return s
      .toLowerCase()
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .replace(/đ/g, 'd')
      .trim()
  }

  const isSearching = computed(() => searchQuery.value.trim().length > 0)

  // Sections to render: all of them normally, or only matching dishes when searching.
  // A group is kept whole when its own name matches; otherwise only its matching options.
  const displaySections = computed<MenuSectionData[]>(() => {
    if (!isSearching.value) return sections.value
    const q = normalize(searchQuery.value)
    const fmt = (n: number) => new Intl.NumberFormat('vi-VN').format(n)
    const result: MenuSectionData[] = []
    for (const sec of sections.value) {
      const groups: DishGroup[] = []
      for (const g of sec.groups) {
        if (normalize(g.name).includes(q)) {
          groups.push(g)
          continue
        }
        const items = g.items.filter((it) => normalize(it.name).includes(q))
        if (items.length) {
          const prices = items.map((i) => i.price)
          const min = Math.min(...prices)
          const max = Math.max(...prices)
          groups.push({ ...g, items, priceLabel: min === max ? fmt(min) : `${fmt(min)} – ${fmt(max)}` })
        }
      }
      if (groups.length) result.push({ ...sec, groups })
    }
    return result
  })

  // Total matching dishes (for the result count label).
  const resultCount = computed(() =>
    displaySections.value.reduce((sum, sec) => sum + sec.groups.reduce((s, g) => s + g.items.length, 0), 0),
  )

  function clearSearch() {
    searchQuery.value = ''
  }

  // Load the menu from the Orchestrator backend (GET /menu) and shape it for display.
  async function loadMenu() {
    isLoading.value = true
    loadError.value = null
    try {
      const raw = await fetchMenu()
      const adapted = adaptMenu(raw)
      categories.value = adapted.categories
      foodItems.value = adapted.foodItems
      bestSellers.value = adapted.bestSellers
      groupsByCategory.value = adapted.groupsByCategory
    } catch (err) {
      loadError.value = err instanceof Error ? err.message : 'Không tải được menu'
      console.error('[menu] loadMenu failed:', err)
    } finally {
      isLoading.value = false
    }
  }

  function setActiveCategory(categoryId: string) {
    activeCategoryId.value = categoryId
  }

  return {
    categories,
    foodItems,
    bestSellers,
    groupsByCategory,
    isLoading,
    loadError,
    activeCategoryId,
    searchQuery,
    sortedCategories,
    sections,
    displaySections,
    isSearching,
    resultCount,
    navItems,
    loadMenu,
    setActiveCategory,
    clearSearch,
  }
})
