import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import type { CartItem, FoodItem } from '@/types'

// The cart survives page reloads and closing the voice sheet: a guest who ordered by voice and
// then closed the assistant must still see their dishes on the cart card. Menu-independent —
// the FoodItem snapshot is persisted whole, so restoring doesn't wait for /menu.
const STORAGE_KEY = 'aiwaiter.cart.v1'

interface PersistedCart {
  items: CartItem[]
  ordered: CartItem[]
}

function loadPersisted(): PersistedCart {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as PersistedCart
      return { items: parsed.items ?? [], ordered: parsed.ordered ?? [] }
    }
  } catch {
    // corrupted / unavailable storage — start clean
  }
  return { items: [], ordered: [] }
}

// Diacritic-insensitive compare so the agent's official menu names match the tablet's menu items.
function normalizeName(s: string): string {
  return s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/đ/g, 'd')
    .trim()
}

export const useCartStore = defineStore('cart', () => {
  const persisted = loadPersisted()
  // Draft: what the guest is still composing (editable).
  const items = ref<CartItem[]>(persisted.items)
  // Already sent to the kitchen (confirmed by the voice agent or via "Xác Nhận Đặt Món").
  // Read-only in the UI; paid & cleared together at the end of the session.
  const orderedItems = ref<CartItem[]>(persisted.ordered)
  // Snapshot of the most recently confirmed batch, for the confirmation screen's summary.
  const lastOrder = ref<{ count: number; total: number } | null>(null)

  watch(
    [items, orderedItems],
    () => {
      try {
        localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({ items: items.value, ordered: orderedItems.value }),
        )
      } catch {
        // storage full/unavailable — the cart still works in-memory
      }
    },
    { deep: true },
  )

  // Draft totals (what would be sent by "Xác Nhận Đặt Món")
  const totalPrice = computed(() =>
    items.value.reduce((sum, item) => sum + item.foodItem.price * item.quantity, 0),
  )
  const totalQuantity = computed(() =>
    items.value.reduce((sum, item) => sum + item.quantity, 0),
  )

  // Kitchen-side totals (already ordered, to be paid at the end)
  const orderedTotal = computed(() =>
    orderedItems.value.reduce((sum, item) => sum + item.foodItem.price * item.quantity, 0),
  )
  const orderedQuantity = computed(() =>
    orderedItems.value.reduce((sum, item) => sum + item.quantity, 0),
  )

  // The cart badge counts everything the guest has in play — draft AND already ordered.
  const badgeCount = computed(() => totalQuantity.value + orderedQuantity.value)

  const isEmpty = computed(() => items.value.length === 0)
  const hasNothing = computed(() => items.value.length === 0 && orderedItems.value.length === 0)

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

  // Replace the draft with the voice agent's cart. `voiceItems` carry official menu names; each
  // is resolved against the loaded menu for price/image. Unresolvable names are skipped (the
  // agent's validator already strips off-menu items, so this should not happen in practice).
  function syncFromVoice(
    voiceItems: Array<{ name: string; quantity: number }>,
    foodItems: FoodItem[],
  ) {
    const next: CartItem[] = []
    for (const vi of voiceItems) {
      const match = foodItems.find((f) => normalizeName(f.name) === normalizeName(vi.name))
      if (match) {
        next.push({ foodItem: match, quantity: vi.quantity })
      } else {
        console.warn(`[cart] voice item not found in menu, skipped: "${vi.name}"`)
      }
    }
    items.value = next
  }

  // The draft was confirmed (sent to the kitchen): move it into orderedItems, merging
  // quantities of dishes that were already ordered earlier in the session.
  function markOrdered() {
    if (items.value.length === 0) return
    lastOrder.value = { count: totalQuantity.value, total: totalPrice.value }
    for (const draft of items.value) {
      const existing = orderedItems.value.find((o) => o.foodItem.id === draft.foodItem.id)
      if (existing) existing.quantity += draft.quantity
      else orderedItems.value.push({ ...draft })
    }
    items.value = []
  }

  // Clear only the draft (e.g. abandoning an unconfirmed selection)
  function clear() {
    items.value = []
  }

  // Session over (payment done): everything goes.
  function clearAll() {
    items.value = []
    orderedItems.value = []
    lastOrder.value = null
  }

  return {
    items,
    orderedItems,
    lastOrder,
    totalPrice,
    totalQuantity,
    orderedTotal,
    orderedQuantity,
    badgeCount,
    isEmpty,
    hasNothing,
    addItem,
    increment,
    decrement,
    quantityFor,
    syncFromVoice,
    markOrdered,
    clear,
    clearAll,
  }
})
