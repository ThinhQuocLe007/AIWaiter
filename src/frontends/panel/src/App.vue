<template>
  <div class="panel">
    <header class="bar">
      <div class="brand-wrap">
        <span class="logo-box"><span>🍳</span></span>
        <span class="brand">ROBO<span class="accent">DISH</span></span>
        <span class="bar-divider"></span>
        <h1>Bảng Điều Khiển</h1>
      </div>
      <div class="bar-right">
        <span class="clock">{{ clock }}</span>
        <div class="status">
          <span class="dot" :class="{ on: connected }"></span>
          {{ connected ? 'Đã kết nối realtime' : 'Mất kết nối — đang thử lại…' }}
        </div>
        <button class="reset-btn" :disabled="resetting" @click="resetAll">
          {{ resetting ? 'Đang reset…' : '↺ Reset hệ thống' }}
        </button>
      </div>
    </header>

    <p v-if="loadError" class="load-error">{{ loadError }}</p>

    <main class="dash">
      <section class="zone">
        <h2 class="zone-head">
          Tổng quan bàn
          <span class="zone-sub">{{ freeCount }} trống / {{ tables.length }} bàn</span>
        </h2>
        <TablesOverview
          :tables="tables"
          :orders="orders"
          :now="now"
          :call-busy="callBusy"
          @end-table="endTable"
          @call="callTable"
        />
      </section>

      <section class="zone">
        <h2 class="zone-head">Robot</h2>
        <RobotBoard :robots="robots" />
      </section>

      <section class="zone">
        <h2 class="zone-head">
          Hàng đợi nhiệm vụ
          <span class="zone-sub">{{ activeTaskCount }} đang chờ / thực hiện</span>
        </h2>
        <TasksBoard :tasks="tasks" :now="now" />
      </section>

      <section class="zone grow">
        <h2 class="zone-head">Bếp (KDS)</h2>
        <KitchenBoard :orders="orders" :tables="tables" :busy="busy" :now="now" @advance="advance" />
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import type { Order, Robot, Table, Task, WsEvent } from '@shared/types'
import {
  callRobot,
  fetchOrders,
  fetchRobots,
  fetchTables,
  fetchTasks,
  resetSystem,
  updateOrderStatus,
  updateTableStatus,
} from '@shared/rest'
import { connectEvents, type WsHandle } from '@shared/ws'
import TablesOverview from './components/TablesOverview.vue'
import RobotBoard from './components/RobotBoard.vue'
import KitchenBoard from './components/KitchenBoard.vue'
import TasksBoard from './components/TasksBoard.vue'

// Kitchen workflow: a new order waits, then is being cooked, then done.
const nextStatus: Record<string, string> = { CHO_BEP: 'DANG_LAM', DANG_LAM: 'XONG' }

const orders = ref<Order[]>([])
const tables = ref<Table[]>([])
const robots = ref<Robot[]>([])
const tasks = ref<Task[]>([])
const connected = ref(false)
const loadError = ref<string | null>(null)
const busy = reactive(new Set<number>()) // order ids with an in-flight PATCH
const callBusy = reactive(new Set<number>()) // table ids with an in-flight call request
const now = ref(Date.now()) // ticked so "đã ngồi" durations stay live
const clock = ref(formatClock()) // live wall-clock HH:MM:SS
const resetting = ref(false)

function formatClock(): string {
  return new Date().toLocaleTimeString('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

let ws: WsHandle | null = null
let pollTimer: ReturnType<typeof setInterval> | undefined
let clockTimer: ReturnType<typeof setInterval> | undefined

const freeCount = computed(() => tables.value.filter((t) => t.status === 'TRONG').length)
const activeTaskCount = computed(() => tasks.value.filter((t) => t.status !== 'DONE').length)

function upsertOrder(order: Order) {
  const i = orders.value.findIndex((o) => o.id === order.id)
  if (i >= 0) orders.value[i] = order
  else orders.value.push(order)
}

function upsertTable(table: Table) {
  const i = tables.value.findIndex((t) => t.id === table.id)
  if (i >= 0) tables.value[i] = table
  else tables.value.push(table)
}

function upsertRobot(robot: Robot) {
  const i = robots.value.findIndex((r) => r.id === robot.id)
  if (i >= 0) robots.value[i] = robot
  else robots.value.push(robot)
}

function upsertTask(task: Task) {
  const i = tasks.value.findIndex((t) => t.id === task.id)
  if (i >= 0) tasks.value[i] = task
  else tasks.value.push(task)
}

async function callTable(id: number) {
  if (callBusy.has(id)) return
  callBusy.add(id)
  try {
    upsertTask(await callRobot(id)) // instant feedback; WS task.created echo is idempotent
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : 'Không gọi được robot'
  } finally {
    callBusy.delete(id)
  }
}

async function advance(order: Order) {
  const next = nextStatus[order.status]
  if (!next || busy.has(order.id)) return
  busy.add(order.id)
  try {
    upsertOrder(await updateOrderStatus(order.id, next)) // instant feedback; WS echo is idempotent
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : 'Cập nhật thất bại'
  } finally {
    busy.delete(order.id)
  }
}

async function endTable(id: number) {
  try {
    upsertTable(await updateTableStatus(id, 'TRONG'))
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : 'Không kết thúc được bàn'
  }
}

async function resetAll() {
  if (resetting.value) return
  if (!window.confirm('Reset toàn bộ hệ thống? Mọi đơn & lượt ngồi sẽ bị xoá, tất cả bàn về Trống.'))
    return
  resetting.value = true
  try {
    await resetSystem() // backend also broadcasts 'reset'; reload here for instant feedback
    await load()
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : 'Reset thất bại'
  } finally {
    resetting.value = false
  }
}

async function load() {
  try {
    const [t, o, r, k] = await Promise.all([
      fetchTables(),
      fetchOrders(),
      fetchRobots(),
      fetchTasks(),
    ])
    tables.value = t
    orders.value = o
    robots.value = r
    tasks.value = k
    loadError.value = null
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : 'Không tải được dữ liệu'
  }
}

function onEvent(e: WsEvent) {
  if (e.type === 'order.created' || e.type === 'order.updated') upsertOrder(e.order)
  else if (e.type === 'table.updated') upsertTable(e.table)
  else if (e.type === 'robot.updated') upsertRobot(e.robot)
  else if (e.type === 'task.created' || e.type === 'task.updated') upsertTask(e.task)
  else if (e.type === 'reset') load() // demo reset: re-pull everything (orders cleared, tables freed)
}

onMounted(() => {
  load()
  ws = connectEvents('panel', onEvent, (ok) => (connected.value = ok))
  // Safety re-sync in case a WS event was missed (e.g. during a brief disconnect).
  pollTimer = setInterval(load, 15000)
  clockTimer = setInterval(() => {
    now.value = Date.now()
    clock.value = formatClock()
  }, 1000)
})

onUnmounted(() => {
  ws?.close()
  if (pollTimer) clearInterval(pollTimer)
  if (clockTimer) clearInterval(clockTimer)
})
</script>
