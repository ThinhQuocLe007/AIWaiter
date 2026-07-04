import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { FoodItem } from '@/types'
import { getStoredTableId, storeTableId } from '@/data/tableSession'
import { useCartStore } from '@/stores/cart'
import { useVoiceStore } from '@/stores/voice'

export const useUiStore = defineStore('ui', () => {
  const cartOpen = ref(false)
  const detailItem = ref<FoodItem | null>(null)

  // Which table this tablet currently orders for (1..6). Persisted so a demo operator can switch
  // tables from the menu and have it stick across reloads (see tableSession.ts).
  const tableId = ref(getStoredTableId())
  const availableTables = Array.from({ length: 6 }, (_, i) => i + 1)

  function setTableId(id: number) {
    if (id === tableId.value) return
    tableId.value = id
    storeTableId(id)
    // Each table has its own cart bucket and its own conversation: bàn 6 must not show bàn 1's
    // dishes or chat. The old table's cart stays persisted under its own key.
    const cart = useCartStore()
    cart.switchTable(id)
    // Validate the loaded bucket against the backend — drops leftovers from a dead session
    // (reset/restart that happened while this tablet wasn't looking).
    void cart.pruneIfSessionOver(id)
    useVoiceStore().resetConversation()
  }

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
    availableTables,
    setTableId,
    openCart,
    closeCart,
    toggleCart,
    openDetail,
    closeDetail,
  }
})
