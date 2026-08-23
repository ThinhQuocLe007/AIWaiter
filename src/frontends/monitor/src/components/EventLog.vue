<template>
  <section class="log">
    <header class="head">
      <h2>Nhật ký sự kiện</h2>
      <span class="hint">thiết bị và agent, theo thứ tự đến</span>
    </header>

    <p v-if="!lines.length" class="empty">Chưa có sự kiện nào.</p>

    <ol v-else class="lines">
      <li v-for="l in lines" :key="l.id" :class="[l.source, l.tone]">
        <span class="t">{{ clock(l.at) }}</span>
        <span class="src">{{ l.source === 'device' ? 'THIẾT BỊ' : 'AGENT' }}</span>
        <span class="msg">{{ l.text }}</span>
      </li>
    </ol>
  </section>
</template>

<script setup lang="ts">
import type { LogLine } from '../pipeline'

defineProps<{ lines: LogLine[] }>()

function clock(d: Date): string {
  return d.toLocaleTimeString('vi-VN', { hour12: false })
}
</script>

<style scoped>
.log {
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: 3px;
  padding: 1.1rem 1.2rem;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.8rem;
}

h2 {
  font-family: var(--font-label);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  margin: 0;
  color: var(--type);
}

.hint,
.empty {
  font-size: 0.78rem;
  color: var(--dim);
  margin: 0;
}

.lines {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  min-height: 0;
  font-family: var(--font-data);
  font-size: 0.75rem;
  line-height: 1.5;
}

.lines li {
  display: grid;
  grid-template-columns: 4.6rem 4.4rem 1fr;
  gap: 0.5rem;
  padding: 0.22rem 0;
  border-bottom: 1px solid color-mix(in srgb, var(--rule) 60%, transparent);
  color: var(--dim);
}

.t { font-variant-numeric: tabular-nums; }

.src {
  font-family: var(--font-label);
  font-size: 0.55rem;
  letter-spacing: 0.05em;
  padding-top: 0.15em;
}

.device .src { color: var(--read); }
.agent .src { color: var(--lamp); }

.msg { color: var(--dim); overflow-wrap: anywhere; }
.signal .msg { color: var(--type); }
.fault .msg { color: var(--clay); }

/* The 7" panel. The two fixed columns shrink to exactly what they hold — "23:04:11" and
   "THIẾT BỊ" — so the message keeps as much of a ~340px-wide column as it can. */
@media (max-height: 700px) {
  .log { padding: 0.45rem 0.55rem; border-radius: 2px; }
  .head { margin-bottom: 0.3rem; }
  h2 { font-size: 0.56rem; }
  .hint { display: none; }
  .empty { font-size: 0.68rem; }

  .lines { font-size: 0.58rem; line-height: 1.4; }
  .lines li {
    grid-template-columns: 3.1rem 3.1rem 1fr;
    gap: 0.3rem;
    padding: 0.1rem 0;
  }
  .src { font-size: 0.46rem; }
}
</style>
