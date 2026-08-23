<template>
  <section class="ledger">
    <header class="head">
      <h2>Sổ đo</h2>
      <span class="hint">mỗi lượt một dòng · thời gian chia theo chặng</span>
    </header>

    <p v-if="!turns.length" class="empty">Chưa đo lượt nào.</p>

    <ol v-else class="rows">
      <li v-for="t in turns" :key="t.n" class="row">
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
      <li><span class="sw stt"></span>Whisper</li>
      <li><span class="sw llm"></span>LLM tới câu đầu</li>
      <li><span class="sw talk"></span>robot nói</li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import { fmtMs, type TurnRecord } from '../pipeline'

const props = defineProps<{ turns: TurnRecord[] }>()

/** Longest turn on screen — every bar is drawn against it so the rows compare honestly. */
function scale(): number {
  return Math.max(1, ...props.turns.map(total))
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
  return { speech: 'khách nói', stt: 'Whisper', llm: 'LLM', talk: 'robot nói' }[k]
}
</script>

<style scoped>
.ledger {
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: 3px;
  padding: 1.1rem 1.2rem 1rem;
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
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  margin: 0;
  color: var(--paper);
}

.hint,
.empty {
  font-size: 0.78rem;
  color: var(--dim);
  margin: 0;
}

.rows {
  list-style: none;
  margin: 0 0 0.9rem;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
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
  background: color-mix(in srgb, var(--rule) 45%, transparent);
  border-radius: 1px;
  overflow: hidden;
}

.seg { height: 100%; }
.seg.speech { background: color-mix(in srgb, var(--paper) 42%, transparent); }
.seg.stt { background: var(--read); }
.seg.llm { background: var(--lamp); }
.seg.talk { background: color-mix(in srgb, var(--lamp) 40%, var(--rule)); }

.key {
  list-style: none;
  margin: 0;
  padding: 0.7rem 0 0;
  border-top: 1px solid var(--rule);
  display: flex;
  flex-wrap: wrap;
  gap: 0.9rem;
  font-size: 0.72rem;
  color: var(--dim);
}

.key li { display: flex; align-items: center; gap: 0.35rem; }

.sw { width: 10px; height: 10px; border-radius: 1px; }
.sw.speech { background: color-mix(in srgb, var(--paper) 42%, transparent); }
.sw.stt { background: var(--read); }
.sw.llm { background: var(--lamp); }
.sw.talk { background: color-mix(in srgb, var(--lamp) 40%, var(--rule)); }
</style>
