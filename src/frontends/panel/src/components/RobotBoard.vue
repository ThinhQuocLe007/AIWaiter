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
        <span class="r-battery" :class="{ low: (r.battery ?? 100) < 25 }">
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
  charging: 'Đang sạc',
  offline: 'Ngoại tuyến',
}
function statusLabel(s: string): string {
  return labels[s] ?? s
}
</script>
