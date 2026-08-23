<template>
  <section class="ledger">
    <header class="head">
      <h2>Sổ đo</h2>
      <span class="hint">mỗi lượt một dòng · thời gian chia theo chặng</span>
    </header>

    <p v-if="!measured.length" class="empty">Chưa đo lượt nào.</p>

    <ol v-else class="rows">
      <li v-for="t in measured" :key="t.n" class="row">
        <span class="n">#{{ t.n }}</span>

        <div class="bar" :title="barTitle(t)">
          <span
            v-for="seg in segments(t)"
            :key="seg.key"
            class="seg"
            :class="seg.key"
            :style="{ width: pct(seg.ms) }"
          ></span>
        </div>

        <span class="total">{{ fmtMs(total(t)) }}</span>
      </li>
    </ol>

    <ul class="key">
      <li><span class="sw speech"></span>khách nói</li>
      <li><span class="sw stt"></span>chép lời</li>
      <li><span class="sw llm"></span>LLM tới câu đầu</li>
      <li><span class="sw talk"></span>robot nói</li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { fmtMs, type TurnRecord } from '../pipeline'

const props = defineProps<{ turns: TurnRecord[] }>()

/** Only turns that actually took measurable time. A turn where nobody spoke belongs in the feed
 *  — it is a real thing that happened — but it has no phases to draw, and an empty bar sitting
 *  next to real ones reads as a turn that finished instantly rather than one that never ran. */
const measured = computed(() => props.turns.filter((t) => total(t) > 0))

/** Longest turn on screen — every bar is drawn against it so the rows compare honestly. */
function scale(): number {
  return Math.max(1, ...measured.value.map(total))
}

function total(t: TurnRecord): number {
  // Prefer the device's own end-to-end figure. It is the only one that includes the speaking
  // time; summing the phases would silently under-report a long reply.
  return t.turnMs ?? (t.speechMs ?? 0) + (t.sttMs ?? 0) + (t.llmTotalMs ?? 0)
}

interface Seg {
  key: 'speech' | 'stt' | 'llm' | 'talk'
  ms: number
}

function segments(t: TurnRecord): Seg[] {
  const speech = t.speechMs ?? 0
  const stt = t.sttMs ?? 0
  const llm = t.firstSentenceMs ?? t.llmTotalMs ?? 0
  // Whatever the device measured beyond the three known phases is time spent speaking. Clamped
  // at zero: the two clocks are on different machines, so a small negative is drift, not talking.
  const talk = Math.max(0, (t.turnMs ?? speech + stt + llm) - speech - stt - llm)
  return [
    { key: 'speech', ms: speech },
    { key: 'stt', ms: stt },
    { key: 'llm', ms: llm },
    { key: 'talk', ms: talk },
  ].filter((s) => s.ms > 0) as Seg[]
}

function pct(ms: number): string {
  return `${(ms / scale()) * 100}%`
}

function barTitle(t: TurnRecord): string {
  const s = segments(t)
    .map((seg) => `${label(seg.key)} ${fmtMs(seg.ms)}`)
    .join(' · ')
  return `${s} — tổng ${fmtMs(total(t))}`
}

function label(k: Seg['key']): string {
  return { speech: 'khách nói', stt: 'chép lời', llm: 'LLM', talk: 'robot nói' }[k]
}
</script>

<style scoped>
.ledger {
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: 3px;
  padding: 1.1rem 1.2rem 1rem;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.9rem;
}

h2 {
  font-family: var(--font-label);
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  margin: 0;
  color: var(--type);
}

.hint,
.empty {
  font-size: 0.78rem;
  color: var(--dim);
  margin: 0;
}



/* A strip, not a column: the ledger sits at the bottom of the control rail and earns a glance,
   so it holds about five bars and scrolls for the rest. The bars still share one scale, which is
   the whole point — comparability survives the diet. */
.rows {
  list-style: none;
  margin: 0 0 0.7rem;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  max-height: 8rem;
  overflow-y: auto;
}

.row {
  display: grid;
  grid-template-columns: 2.2rem 1fr 3.4rem;
  align-items: center;
  gap: 0.6rem;
}

.n,
.total {
  font-family: var(--font-data);
  font-size: 0.76rem;
  color: var(--dim);
  font-variant-numeric: tabular-nums;
}

.total { text-align: right; color: var(--read); }

.bar {
  display: flex;
  height: 10px;
  background: color-mix(in srgb, var(--rule) 55%, transparent);
  border-radius: 1px;
  overflow: hidden;
}

.seg { height: 100%; }
.seg.speech { background: var(--speech); }
.seg.stt { background: var(--read-lit); }
.seg.llm { background: var(--lamp-lit); }
.seg.talk { background: color-mix(in srgb, var(--lamp-lit) 45%, var(--rule)); }

.key {
  list-style: none;
  margin: 0;
  flex: 0 0 auto;
  padding: 0.55rem 0 0;
  border-top: 1px solid var(--rule);
  display: flex;
  flex-wrap: wrap;
  gap: 0.7rem;
  font-size: 0.68rem;
  color: var(--dim);
}

.key li { display: flex; align-items: center; gap: 0.35rem; }

.sw { width: 10px; height: 10px; border-radius: 1px; }
.sw.speech { background: var(--speech); }
.sw.stt { background: var(--read-lit); }
.sw.llm { background: var(--lamp-lit); }
.sw.talk { background: color-mix(in srgb, var(--lamp-lit) 45%, var(--rule)); }

/* The 7" panel: about three bars before it scrolls. */
@media (max-height: 700px) {
  .ledger { padding: 0.45rem 0.6rem 0.45rem; border-radius: 5px; }
  .head { margin-bottom: 0.35rem; }
  h2 { font-size: 0.62rem; }
  .hint { display: none; }
  .empty { font-size: 0.72rem; }

  .rows { gap: 0.25rem; margin-bottom: 0.4rem; max-height: 4.6rem; }
  .row { grid-template-columns: 1.7rem 1fr 2.7rem; gap: 0.4rem; }
  .n,
  .total { font-size: 0.68rem; }
  .bar { height: 8px; }

  .key { padding-top: 0.35rem; gap: 0.55rem; font-size: 0.6rem; }
  .sw { width: 8px; height: 8px; }
}
</style>
