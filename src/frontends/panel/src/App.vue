<template>
  <div class="panel">
    <header class="bar">
      <h1>🍳 Bảng Điều Khiển Bếp</h1>
      <div class="status">
        <span class="dot" :class="{ on: connected }"></span>
        {{ connected ? 'Đã kết nối realtime' : 'Mất kết nối — đang thử lại…' }}
      </div>
    </header>

    <p v-if="loadError" class="load-error">{{ loadError }}</p>

    <main class="board">
      <section v-for="col in columns" :key="col.status" class="col">
        <h2 class="col-head" :class="col.status">
          {{ col.label }} <span class="count">{{ col.orders.length }}</span>
        </h2>

        <div class="cards">
          <p v-if="!col.orders.length" class="empty">Trống</p>

          <article v-for="order in col.orders" :key="order.id" class="card">
            <div class="card-top">
              <span class="table">{{ tableName(order.table_id) }}</span>
              <span class="time">{{ timeAgo(order.created_at) }}</span>
            </div>

            <ul class="items">
              <li v-for="item in order.items" :key="item.id">
                <span class="qty">{{ item.qty }}×</span> {{ item.name }}
              </li>
            </ul>

            <div class="card-bottom">
              <span class="total">{{ formatPrice(order.total) }}</span>
              <button
                v-if="nextStatus[order.status]"
                class="advance"
                :disabled="busy.has(order.id)"
                @click="advance(order)"
              >
                {{ nextLabel[order.status] }}
              </button>
            </div>
          </article>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import type { Order, Table, WsEvent } from '@shared/types'
import { fetchOrders, fetchTables, updateOrderStatus } from '@shared/rest'
import { connectEvents, type WsHandle } from '@shared/ws'

// Kitchen workflow: a new order waits, then is being cooked, then done.
const nextStatus: Record<string, string> = { CHO_BEP: 'DANG_LAM', DANG_LAM: 'XONG' }
const nextLabel: Record<string, string> = { CHO_BEP: 'Bắt đầu làm', DANG_LAM: 'Món xong ✓' }

const orders = ref<Order[]>([])
const tables = ref<Table[]>([])
const connected = ref(false)
const loadError = ref<string | null>(null)
const busy = reactive(new Set<number>()) // order ids with an in-flight PATCH

let ws: WsHandle | null = null
let pollTimer: ReturnType<typeof setInterval> | undefined

const tableById = computed(() => new Map(tables.value.map((t) => [t.id, t])))

function tableName(id: number): string {
  return tableById.value.get(id)?.name ?? `Bàn ${id}`
}

// Three kitchen columns. New/cooking are FIFO (oldest first); done shows the most recent.
const columns = computed(() => [
  { status: 'CHO_BEP', label: 'Chờ bếp', orders: byStatus('CHO_BEP', 'asc') },
  { status: 'DANG_LAM', label: 'Đang làm', orders: byStatus('DANG_LAM', 'asc') },
  { status: 'XONG', label: 'Xong', orders: byStatus('XONG', 'desc').slice(0, 15) },
])

function byStatus(status: string, dir: 'asc' | 'desc'): Order[] {
  const list = orders.value.filter((o) => o.status === status)
  list.sort((a, b) =>
    dir === 'asc' ? a.created_at.localeCompare(b.created_at) : b.created_at.localeCompare(a.created_at),
  )
  return list
}

function upsert(order: Order) {
  const i = orders.value.findIndex((o) => o.id === order.id)
  if (i >= 0) orders.value[i] = order
  else orders.value.push(order)
}

async function advance(order: Order) {
  const next = nextStatus[order.status]
  if (!next || busy.has(order.id)) return
  busy.add(order.id)
  try {
    upsert(await updateOrderStatus(order.id, next)) // instant feedback; WS echo is idempotent
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : 'Cập nhật thất bại'
  } finally {
    busy.delete(order.id)
  }
}

const priceFmt = new Intl.NumberFormat('vi-VN')
function formatPrice(v: number): string {
  return `${priceFmt.format(v)}đ`
}

function timeAgo(ts: string): string {
  // SQLite stores UTC "YYYY-MM-DD HH:MM:SS"; mark it as UTC before parsing.
  const then = new Date(ts.replace(' ', 'T') + 'Z').getTime()
  const mins = Math.max(0, Math.round((Date.now() - then) / 60000))
  if (mins < 1) return 'vừa xong'
  if (mins < 60) return `${mins} phút trước`
  return `${Math.floor(mins / 60)} giờ trước`
}

async function load() {
  try {
    const [t, o] = await Promise.all([fetchTables(), fetchOrders()])
    tables.value = t
    orders.value = o
    loadError.value = null
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : 'Không tải được dữ liệu'
  }
}

function onEvent(e: WsEvent) {
  if (e.type === 'order.created' || e.type === 'order.updated') upsert(e.order)
}

onMounted(() => {
  load()
  ws = connectEvents('panel', onEvent, (ok) => (connected.value = ok))
  // Safety re-sync in case a WS event was missed (e.g. during a brief disconnect).
  pollTimer = setInterval(load, 15000)
})

onUnmounted(() => {
  ws?.close()
  if (pollTimer) clearInterval(pollTimer)
})
</script>
