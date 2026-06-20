<template>
  <div class="board">
    <section v-for="col in columns" :key="col.status" class="col" :class="col.status">
      <h2 class="col-head" :class="col.status">
        {{ col.label }} <span class="count">{{ col.orders.length }}</span>
      </h2>

      <div class="cards">
        <p v-if="!col.orders.length" class="empty">Trống</p>

        <article v-for="order in col.orders" :key="order.id" class="card">
          <div class="card-top">
            <span class="table">{{ tableName(order.table_id) }}</span>
            <span class="time">{{ timeAgo(order.created_at, now) }}</span>
          </div>

          <ul class="items">
            <li v-for="item in order.items" :key="item.id">
              <span class="qty">{{ item.qty }}×</span> {{ item.name }}
            </li>
          </ul>

          <div class="card-bottom">
            <span class="total">{{ formatPrice(order.total) }}</span>
            <button
              v-if="nextLabel[order.status]"
              class="advance"
              :disabled="busy.has(order.id)"
              @click="$emit('advance', order)"
            >
              {{ nextLabel[order.status] }}
            </button>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Order, Table } from '@shared/types'
import { formatPrice, timeAgo } from '../format'

const props = defineProps<{
  orders: Order[]
  tables: Table[]
  busy: Set<number>
  now: number
}>()

defineEmits<{ (e: 'advance', order: Order): void }>()

const nextLabel: Record<string, string> = { CHO_BEP: 'Bắt đầu làm', DANG_LAM: 'Món xong ✓' }

const tableById = computed(() => new Map(props.tables.map((t) => [t.id, t])))
function tableName(id: number): string {
  return tableById.value.get(id)?.name ?? `Bàn ${id}`
}

// New/cooking are FIFO (oldest first); done shows the most recent few.
const columns = computed(() => [
  { status: 'CHO_BEP', label: 'Chờ bếp', orders: byStatus('CHO_BEP', 'asc') },
  { status: 'DANG_LAM', label: 'Đang làm', orders: byStatus('DANG_LAM', 'asc') },
  { status: 'XONG', label: 'Xong', orders: byStatus('XONG', 'desc').slice(0, 15) },
])

function byStatus(status: string, dir: 'asc' | 'desc'): Order[] {
  const list = props.orders.filter((o) => o.status === status)
  list.sort((a, b) =>
    dir === 'asc'
      ? a.created_at.localeCompare(b.created_at)
      : b.created_at.localeCompare(a.created_at),
  )
  return list
}
</script>
