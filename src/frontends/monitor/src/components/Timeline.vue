<template>
  <!-- One feed, newest first. The conversation and the raw frames used to be two panels side by
       side, which meant reading a turn required looking in two places and mentally joining them
       on timestamp. Here each turn owns its own evidence: what was said, what it cost, and the
       frames that prove the numbers came from somewhere. -->
  <section class="feed">
    <header class="head">
      <h2>Diễn biến</h2>
      <span class="hint">khách nói · robot trả lời · từng frame đo được</span>
    </header>

    <div class="scroll">
      <!-- The turn in flight, filling in as it happens: heard first, then each sentence as the
           agent produces it. That progressive fill is the point of the panel. -->
      <article v-if="live" class="turn live">
        <p v-if="live.heard" class="said guest">{{ live.heard }}</p>
        <p v-else class="said guest waiting">đang nghe…</p>
        <p v-for="(s, i) in live.replyParts" :key="i" class="said robot">{{ s }}</p>
        <p v-if="live.heard && !live.replyParts.length" class="said robot waiting">
          agent đang soạn câu trả lời…
        </p>
        <ol v-if="liveLog.length" class="frames">
          <li v-for="l in liveLog" :key="l.id" :class="[l.source, l.tone]">
            <span class="t">{{ clock(l.at) }}</span>
            <span class="src">{{ l.source === 'device' ? 'THIẾT BỊ' : 'AGENT' }}</span>
            <span class="msg">{{ l.text }}</span>
          </li>
        </ol>
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
          <span v-if="outcomeText(t)" class="aside">{{ outcomeText(t) }}</span>
        </div>
        <p v-if="t.heard" class="said guest">{{ t.heard }}</p>
        <p v-if="t.reply" class="said robot">{{ t.reply }}</p>
        <p v-if="t.outcome === 'ok'" class="timing">
          Chép lời {{ fmtMs(t.sttMs) }} · câu đầu {{ fmtMs(t.firstSentenceMs) }} ·
          cả lượt {{ fmtMs(t.turnMs) }}
        </p>
        <ol v-if="t.log.length" class="frames">
          <li v-for="l in t.log" :key="l.id" :class="[l.source, l.tone]">
            <span class="t">{{ clock(l.at) }}</span>
            <span class="src">{{ l.source === 'device' ? 'THIẾT BỊ' : 'AGENT' }}</span>
            <span class="msg">{{ l.text }}</span>
          </li>
        </ol>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { clock, fmtMs, type LogLine, type TurnRecord } from '../pipeline'

defineProps<{
  turns: TurnRecord[]
  live: ({ replyParts: string[] } & Partial<TurnRecord>) | null
  /** Frames of the turn currently in flight — they join their turn record when it closes. */
  liveLog: LogLine[]
  /** False while no mic is connected — the empty state must not point at a dead button. */
  ready: boolean
}>()

/** Wording matters here: these are read by an audience, not by whoever is debugging. Three of
 *  the four are the pipeline behaving correctly on an empty input, so they are stated as facts,
 *  not as failures — and the agent error deliberately does NOT print its exception text. */
function outcomeText(t: TurnRecord): string {
  return {
    ok: '',
    cancelled: 'đã dừng',
    timeout: 'không có ai nói',
    empty: 'không nghe rõ',
    error: 'chưa trả lời được',
  }[t.outcome]
}
</script>

<style scoped>
.feed {
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
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  margin: 0;
  color: var(--type);
}

.hint,
.empty {
  font-size: 0.8rem;
  color: var(--dim);
  margin: 0;
}
.empty { line-height: 1.6; }
.empty b { color: var(--type); font-weight: 600; }

.scroll {
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1.15rem;
  padding-right: 0.4rem;
  min-height: 0;
}

.turn {
  border-left: 2px solid var(--rule);
  padding-left: 0.9rem;
}

.turn.live { border-left-color: var(--lamp-lit); }

/* No red rule down the side of a turn where nobody spoke — see outcomeText. Only a genuine
   agent failure gets the fault colour, and even then only on the rule, not on the words. */
.turn.error { border-left-color: var(--clay); }

.meta {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-family: var(--font-data);
  font-size: 0.72rem;
  color: var(--dim);
  margin-bottom: 0.4rem;
}

.stage {
  font-family: var(--font-label);
  font-size: 0.64rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--read);
}

.aside { color: var(--dim); font-style: italic; }

.said {
  margin: 0 0 0.35rem;
  line-height: 1.5;
  font-size: 1.02rem;
}

/* Two voices, told apart by weight and colour rather than by chat bubbles — the panel is a
   transcript for reading at a distance, not a messaging app. */
.guest {
  color: var(--type);
  font-weight: 600;
}

.guest::before {
  content: 'khách ';
  font-family: var(--font-label);
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--dim);
  margin-right: 0.45rem;
  vertical-align: 0.12em;
}

.robot {
  color: var(--lamp);
  font-weight: 400;
}

.robot::before {
  content: 'robot ';
  font-family: var(--font-label);
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--dim);
  margin-right: 0.45rem;
  vertical-align: 0.12em;
}

.waiting {
  opacity: 0.6;
  font-style: italic;
}

.timing {
  margin: 0.45rem 0 0;
  font-family: var(--font-data);
  font-size: 0.74rem;
  color: var(--dim);
  font-variant-numeric: tabular-nums;
}

/* --- the frames belonging to this turn ------------------------------------------------- */
/* Recessive on purpose. The speech above is ~1rem and these are ~0.7rem mono: the size gap is
   what stops a wall of frames from burying the two sentences people actually came to read. */
.frames {
  list-style: none;
  margin: 0.5rem 0 0;
  padding: 0.4rem 0 0;
  border-top: 1px solid color-mix(in srgb, var(--rule) 60%, transparent);
  font-family: var(--font-data);
  font-size: 0.72rem;
  line-height: 1.45;
}

.frames li {
  display: grid;
  grid-template-columns: 4.4rem 4.2rem 1fr;
  gap: 0.5rem;
  padding: 0.1rem 0;
  color: var(--dim);
}

.t { font-variant-numeric: tabular-nums; }

.src {
  font-family: var(--font-label);
  font-size: 0.56rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  padding-top: 0.2em;
}

.device .src { color: var(--read); }
.agent .src { color: var(--lamp); }

.msg { overflow-wrap: anywhere; }
.signal .msg { color: var(--type); }
.fault .msg { color: var(--clay); }

/* --- the Jetson's 7" panel -------------------------------------------------------------- */
/* The speech gets BIGGER here than it was when this was two panels: merging bought back the
   width of a whole column plus one panel's worth of chrome, and reading the reply from across a
   fair stand is the one thing this screen is for. The frames stay small. */
@media (max-height: 700px) {
  .feed { padding: 0.5rem 0.6rem; border-radius: 5px; }
  .head { margin-bottom: 0.4rem; }
  h2 { font-size: 0.64rem; }
  .hint { display: none; }
  .empty { font-size: 0.8rem; }

  .scroll { gap: 0.7rem; padding-right: 0.3rem; }
  .turn { padding-left: 0.6rem; }
  .meta { font-size: 0.64rem; gap: 0.45rem; margin-bottom: 0.2rem; }
  .stage { font-size: 0.54rem; }
  .said { font-size: 0.95rem; line-height: 1.4; margin-bottom: 0.2rem; }
  .guest::before,
  .robot::before { font-size: 0.52rem; margin-right: 0.3rem; }
  .timing { font-size: 0.68rem; margin-top: 0.3rem; }

  .frames {
    margin-top: 0.35rem;
    padding-top: 0.3rem;
    font-size: 0.66rem;
    line-height: 1.35;
  }
  .frames li { grid-template-columns: 3.6rem 3.4rem 1fr; gap: 0.35rem; padding: 0.05rem 0; }
  .src { font-size: 0.5rem; }
}
</style>
