<template>
  <div class="kiosk">
    <header class="bar">
      <h1>🍽️ Mời Quý Khách Chọn Bàn</h1>
      <div class="status">
        <span class="dot" :class="{ on: !loadError }"></span>
        {{ loadError ? 'Mất kết nối — đang thử lại…' : `${freeCount} bàn trống` }}
      </div>
    </header>

    <p v-if="loadError" class="load-error">{{ loadError }}</p>
    <p v-if="notice" class="notice">{{ notice }}</p>

    <main class="grid">
      <p v-if="!tables.length && !loadError" class="empty">Đang tải danh sách bàn…</p>

      <button
        v-for="t in tables"
        :key="t.id"
        class="table-card"
        :class="{ free: isFree(t), busy: !isFree(t) }"
        :disabled="!isFree(t)"
        @click="pick(t)"
      >
        <span class="t-name">{{ t.name }}</span>
        <span class="t-cap">{{ t.capacity }} chỗ</span>
        <span class="t-state">{{ isFree(t) ? 'Trống' : statusLabel(t.status) }}</span>
      </button>
    </main>

    <!-- Party-size step: choose how many guests, then seat. -->
    <div v-if="selected" class="overlay" @click.self="cancel">
      <div class="sheet">
        <h2>{{ selected.name }}</h2>
        <p class="sub">Quý khách đi mấy người?</p>

        <div class="stepper">
          <button class="step" :disabled="party <= 1" @click="party--">−</button>
          <span class="party">{{ party }}</span>
          <button class="step" :disabled="party >= selected.capacity" @click="party++">+</button>
        </div>
        <p class="cap-hint">Tối đa {{ selected.capacity }} người</p>

        <p v-if="seatErr" class="seat-err">{{ seatErr }}</p>

        <div class="actions">
          <button class="ghost" :disabled="seating" @click="cancel">Huỷ</button>
          <button class="primary" :disabled="seating" @click="seat">
            {{ seating ? 'Đang xếp bàn…' : 'Vào bàn' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Success: confirm the table is ready, then auto-return for the next guest. -->
    <div v-if="done" class="overlay done-overlay">
      <div class="sheet center">
        <div class="check">✓</div>
        <h2>{{ done.name }} đã sẵn sàng</h2>
        <p class="sub">Mời quý khách vào bàn và đặt món trên màn hình tại bàn.</p>
        <button class="primary" @click="reset">Xong</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import type { Table } from '@shared/types'
import { createSeating, fetchTables } from '@shared/rest'

const tables = ref<Table[]>([])
const loadError = ref<string | null>(null)
const notice = ref<string | null>(null)

const selected = ref<Table | null>(null) // table being seated (party-size step open)
const party = ref(2)
const seating = ref(false)
const seatErr = ref<string | null>(null)
const done = ref<Table | null>(null) // success overlay

let pollTimer: ReturnType<typeof setInterval> | undefined
let noticeTimer: ReturnType<typeof setTimeout> | undefined
let doneTimer: ReturnType<typeof setTimeout> | undefined

const STATUS_LABEL: Record<string, string> = {
  TRONG: 'Trống',
  DANG_PHUC_VU: 'Đang phục vụ',
  CHO_BEP: 'Đang phục vụ',
  DANG_LAM: 'Đang phục vụ',
}

function isFree(t: Table): boolean {
  return t.status === 'TRONG'
}

function statusLabel(status: string): string {
  return STATUS_LABEL[status] ?? 'Đang phục vụ'
}

const freeCount = computed(() => tables.value.filter(isFree).length)

async function load() {
  try {
    tables.value = await fetchTables()
    loadError.value = null
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : 'Không tải được danh sách bàn'
  }
}

function flashNotice(msg: string) {
  notice.value = msg
  clearTimeout(noticeTimer)
  noticeTimer = setTimeout(() => (notice.value = null), 4000)
}

function pick(t: Table) {
  if (!isFree(t)) return
  selected.value = t
  party.value = Math.min(2, t.capacity)
  seatErr.value = null
}

function cancel() {
  if (seating.value) return
  selected.value = null
}

async function seat() {
  const t = selected.value
  if (!t || seating.value) return
  seating.value = true
  seatErr.value = null
  try {
    const updated = await createSeating(t.id, party.value)
    selected.value = null
    done.value = updated
    // Auto-return to the table list for the next guest.
    doneTimer = setTimeout(reset, 6000)
    load() // reflect the now-occupied table immediately
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Không xếp được bàn'
    // 409 = someone took this table between fetch and submit → bounce back to the list.
    if (msg.includes('409')) {
      selected.value = null
      flashNotice(`${t.name} vừa có khách, mời quý khách chọn bàn khác.`)
      load()
    } else {
      seatErr.value = msg
    }
  } finally {
    seating.value = false
  }
}

function reset() {
  clearTimeout(doneTimer)
  done.value = null
  load()
}

onMounted(() => {
  load()
  // No WS event for table status, so poll to reflect tables freeing up / filling.
  pollTimer = setInterval(load, 8000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  clearTimeout(noticeTimer)
  clearTimeout(doneTimer)
})
</script>
