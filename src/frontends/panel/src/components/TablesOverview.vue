<template>
  <div class="tables-grid">
    <article
      v-for="t in tables"
      :key="t.id"
      class="t-card"
      :class="t.status"
    >
      <div class="t-top">
        <span class="t-name">{{ t.name }}</span>
        <span class="t-badge" :class="t.status">{{ statusLabel(t) }}</span>
      </div>

      <div v-if="t.status === 'TRONG'" class="t-empty">Sẵn sàng đón khách</div>

      <template v-else>
        <div class="t-meta">
          <span v-if="t.party_size">👥 {{ t.party_size }} khách</span>
          <span v-if="t.seated_at">⏱ {{ durationLabel(t.seated_at, now) }}</span>
        </div>

        <div v-if="orderOf(t)" class="t-order">
          <span class="t-dishes">🍽 {{ dishCount(orderOf(t)!) }} món</span>
          <span class="t-kitchen" :class="orderOf(t)!.status">
            {{ kitchenLabel[orderOf(t)!.status] ?? orderOf(t)!.status }}
          </span>
          <span class="t-total">{{ formatPrice(orderOf(t)!.total) }}</span>
        </div>
        <div v-else class="t-order muted">Chưa gọi món</div>
      </template>

      <button
        v-if="t.status === 'DA_THANH_TOAN'"
        class="t-end"
        @click="$emit('end-table', t.id)"
      >
        Kết thúc bàn
      </button>
    </article>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Order, Table } from '@shared/types'
import { durationLabel, formatPrice } from '../format'

const props = defineProps<{ tables: Table[]; orders: Order[]; now: number }>()
defineEmits<{ (e: 'end-table', id: number): void }>()

const kitchenLabel: Record<string, string> = {
  CHO_BEP: 'Chờ bếp',
  DANG_LAM: 'Đang làm',
  XONG: 'Đã xong',
}

const orderById = computed(() => new Map(props.orders.map((o) => [o.id, o])))

function orderOf(t: Table): Order | undefined {
  return t.current_order_id ? orderById.value.get(t.current_order_id) : undefined
}

function dishCount(o: Order): number {
  return o.items.reduce((n, it) => n + it.qty, 0)
}

function statusLabel(t: Table): string {
  if (t.status === 'TRONG') return 'Trống'
  if (t.status === 'DA_THANH_TOAN') return 'Đã xong'
  return t.current_order_id ? 'Đang ăn' : 'Mới vào'
}
</script>
