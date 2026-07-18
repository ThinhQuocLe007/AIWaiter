<template>
  <div class="robots-grid">
    <p v-if="!robots.length" class="empty">Chưa có robot</p>
    <article v-for="r in robots" :key="r.id" class="r-card" :class="r.status">
      <div class="r-top">
        <span class="r-name">🤖 {{ r.name ?? r.id }}</span>
        <span class="r-badge" :class="r.status">{{ statusLabel(r.status) }}</span>
      </div>
      <div class="r-activity">{{ r.activity ?? '—' }}</div>
      <div class="r-meta">
        <!-- Pin/vị trí chỉ có nghĩa khi robot đang gửi dữ liệu realtime; một robot chưa kích
             hoạt (bridge chưa chạy) không được phép khoe pin từ snapshot cũ. -->
        <span v-if="r.status === 'offline'" class="r-battery">🔌 Chờ dữ liệu realtime…</span>
        <span v-else class="r-battery" :class="{ low: (r.battery ?? 100) < 25 }">
          🔋 {{ r.battery != null ? Math.round(r.battery) + '%' : '—' }}
        </span>
      </div>
    </article>
  </div>
</template>

<script setup lang="ts">
import type { Robot } from '@shared/types'

defineProps<{ robots: Robot[] }>()

const labels: Record<string, string> = {
  idle: 'Rảnh',
  busy: 'Bận',
  returning: 'Đang về dock',
  charging: 'Đang sạc',
  offline: 'Chưa kết nối',
}
function statusLabel(s: string): string {
  return labels[s] ?? s
}
</script>
