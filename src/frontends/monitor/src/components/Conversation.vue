<template>
  <section class="convo">
    <header class="head">
      <h2>Hội thoại</h2>
      <span class="hint">đúng những gì robot nghe và nói</span>
    </header>

    <div class="scroll">
      <!-- The turn in flight sits at the top, filling in as it happens: heard first, then each
           sentence as the agent produces it. That progressive fill is the point of the panel. -->
      <article v-if="live" class="turn live">
        <p v-if="live.heard" class="said guest">{{ live.heard }}</p>
        <p v-else class="said guest waiting">đang nghe…</p>
        <p v-for="(s, i) in live.replyParts" :key="i" class="said robot">{{ s }}</p>
        <p v-if="live.heard && !live.replyParts.length" class="said robot waiting">
          agent đang soạn câu trả lời…
        </p>
      </article>

      <p v-if="!live && !turns.length" class="empty">
        <template v-if="ready">Chưa có lượt nào. Bấm <b>Bắt đầu nghe</b> rồi nói vào mic của robot.</template>
        <template v-else>Chưa có lượt nào. Bật mic trên Jetson rồi quay lại đây.</template>
      </p>

      <article v-for="t in turns" :key="t.n" class="turn" :class="t.outcome">
        <div class="meta">
          <span class="n">#{{ t.n }}</span>
          <span class="time">{{ clock(t.at) }}</span>
          <span v-if="t.stage" class="stage">{{ t.stage }}</span>
          <span v-if="t.outcome !== 'ok'" class="bad">{{ outcomeText(t) }}</span>
        </div>
        <p v-if="t.heard" class="said guest">{{ t.heard }}</p>
        <p v-if="t.reply" class="said robot">{{ t.reply }}</p>
        <p class="timing">
          Whisper {{ fmtMs(t.sttMs) }} · câu đầu {{ fmtMs(t.firstSentenceMs) }} ·
          cả lượt {{ fmtMs(t.turnMs) }}
        </p>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { fmtMs, type TurnRecord } from '../pipeline'

defineProps<{
  turns: TurnRecord[]
  live: ({ replyParts: string[] } & Partial<TurnRecord>) | null
  /** False while no mic is connected — the empty state must not point at a dead button. */
  ready: boolean
}>()

function clock(d: Date): string {
  return d.toLocaleTimeString('vi-VN', { hour12: false })
}

function outcomeText(t: TurnRecord): string {
  return {
    ok: '',
    cancelled: 'khách bấm dừng',
    timeout: 'không nghe thấy gì',
    empty: 'không chép được lời',
    error: t.note ?? 'lỗi',
  }[t.outcome]
}
</script>

<style scoped>
.convo {
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
.empty { line-height: 1.6; }
.empty b { color: var(--paper); font-weight: 500; }

.scroll {
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding-right: 0.3rem;
  min-height: 0;
}

.turn {
  border-left: 2px solid var(--rule);
  padding-left: 0.9rem;
}

.turn.live {
  border-left-color: var(--lamp);
}

.turn.cancelled,
.turn.timeout,
.turn.empty,
.turn.error {
  border-left-color: var(--clay);
}

.meta {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-family: var(--font-data);
  font-size: 0.7rem;
  color: var(--dim);
  margin-bottom: 0.4rem;
}

.stage {
  font-family: var(--font-label);
  font-size: 0.6rem;
  letter-spacing: 0.04em;
  color: var(--read);
}

.bad { color: var(--clay); }

.said {
  margin: 0 0 0.35rem;
  line-height: 1.55;
  font-size: 0.95rem;
}

/* Two voices, told apart by weight and colour rather than by chat bubbles — the panel is a
   transcript for reading at a distance, not a messaging app. */
.guest {
  color: var(--paper);
  font-weight: 500;
}

.guest::before {
  content: 'khách ';
  font-family: var(--font-label);
  font-size: 0.58rem;
  letter-spacing: 0.06em;
  color: var(--dim);
  margin-right: 0.45rem;
  vertical-align: 0.12em;
}

.robot {
  color: var(--lamp);
  font-weight: 300;
}

.robot::before {
  content: 'robot ';
  font-family: var(--font-label);
  font-size: 0.58rem;
  letter-spacing: 0.06em;
  color: var(--dim);
  margin-right: 0.45rem;
  vertical-align: 0.12em;
}

.waiting {
  opacity: 0.55;
  font-style: italic;
}

.timing {
  margin: 0.5rem 0 0;
  font-family: var(--font-data);
  font-size: 0.7rem;
  color: var(--dim);
  font-variant-numeric: tabular-nums;
}
</style>
