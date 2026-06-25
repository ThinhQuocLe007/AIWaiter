<template>
  <div class="tasks-wrap">
    <div v-if="!active.length" class="empty">Không có nhiệm vụ nào đang chờ</div>
    <div v-else class="tasks-grid">
      <article v-for="t in active" :key="t.id" class="task-card" :class="t.status">
        <div class="task-top">
          <span class="task-kind">{{ kindIcon[t.kind] ?? '•' }} {{ kindLabel[t.kind] ?? t.kind }}</span>
          <span class="task-badge" :class="t.status">{{ statusLabel[t.status] ?? t.status }}</span>
        </div>
        <div class="task-meta">
          <span class="task-table">{{ t.table_id != null ? `Bàn ${t.table_id}` : '—' }}</span>
          <span class="task-robot">{{ t.robot_id ? `🤖 ${t.robot_id}` : 'chờ phân robot' }}</span>
        </div>
        <div class="task-time">#{{ t.id }} · {{ timeAgo(t.updated_at, now) }}</div>
      </article>
    </div>
    <p v-if="doneCount" class="tasks-done-note">{{ doneCount }} nhiệm vụ đã hoàn tất</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Task } from '@shared/types'
import { timeAgo } from '../format'

const props = defineProps<{ tasks: Task[]; now: number }>()

const kindLabel: Record<string, string> = {
  go_to_table: 'Đón khách',
  deliver: 'Giao món',
  call: 'Gọi phục vụ',
}
const kindIcon: Record<string, string> = {
  go_to_table: '🪑',
  deliver: '🍽',
  call: '🔔',
}
const statusLabel: Record<string, string> = {
  PENDING: 'Chờ robot',
  ASSIGNED: 'Đã giao việc',
  IN_PROGRESS: 'Đang thực hiện',
  DONE: 'Hoàn tất',
}

// Active queue: anything not finished, oldest first (the order the dispatcher serves them).
const active = computed(() =>
  props.tasks
    .filter((t) => t.status !== 'DONE')
    .sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id - b.id),
)

const doneCount = computed(() => props.tasks.filter((t) => t.status === 'DONE').length)
</script>
