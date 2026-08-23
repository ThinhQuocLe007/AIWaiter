<template>
  <!-- The rack. Read left to right: this really is the order the signal travels, so the wires
       between modules carry information rather than decorating the row. -->
  <section class="chain" aria-label="Các chặng của đường tín hiệu">
    <template v-for="(s, i) in ordered" :key="s.id">
      <div v-if="i > 0" class="wire" :class="{ live: isLive(i) }" aria-hidden="true">
        <span class="pulse"></span>
      </div>

      <article class="mod" :class="s.state">
        <header class="mod-head">
          <span class="tag">{{ s.label }}</span>
          <span class="lamp"></span>
        </header>
        <p class="caption">{{ s.caption }}</p>
        <p class="readout">{{ s.readout }}</p>
        <p class="detail" :title="s.detail">{{ s.detail }}</p>
      </article>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { STAGE_ORDER, type StageId, type StageView } from '../pipeline'

const props = defineProps<{
  stages: Record<StageId, StageView>
  active: StageId | null
}>()

const ordered = computed(() => STAGE_ORDER.map((id) => props.stages[id]))

/** A wire runs hot while the module it feeds is working — that is what "the signal is here" means. */
function isLive(index: number): boolean {
  return ordered.value[index]?.state === 'active'
}
</script>

<style scoped>
/* Flex, not grid: the wires are real children sitting BETWEEN the modules, so a 5-column grid
   would have to hold nine items and would wrap the rack onto a second row. Modules share the
   leftover width equally (flex: 1 1 0) and each wire takes a fixed span. */
.chain {
  display: flex;
  align-items: stretch;
}

.chain > .wire {
  position: relative;
  flex: 0 0 26px;
  z-index: 2;
}

.wire::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 0;
  width: 100%;
  height: 2px;
  background: var(--rule);
  transition: background 180ms ease;
}

.wire.live::before {
  background: color-mix(in srgb, var(--lamp) 55%, transparent);
}

.pulse {
  position: absolute;
  top: 50%;
  left: 0;
  width: 6px;
  height: 6px;
  margin-top: -3px;
  border-radius: 50%;
  background: var(--lamp);
  opacity: 0;
}

.wire.live .pulse {
  animation: travel 900ms linear infinite;
  box-shadow: 0 0 10px var(--lamp);
}

@keyframes travel {
  0% { transform: translateX(0); opacity: 0; }
  20% { opacity: 1; }
  80% { opacity: 1; }
  100% { transform: translateX(26px); opacity: 0; }
}

.mod {
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 1.1rem 1.15rem 1.2rem;
  background: var(--panel);
  border: 1px solid var(--rule);
  border-radius: 3px;
  min-height: 9.5rem;
  transition: border-color 180ms ease, background 180ms ease, box-shadow 180ms ease;
}

.mod-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.tag {
  font-family: var(--font-label);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--paper);
}

.lamp {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--rule);
  transition: background 180ms ease, box-shadow 180ms ease;
}

.caption {
  font-size: 0.8rem;
  color: var(--dim);
  margin: 0;
}

.readout {
  font-family: var(--font-data);
  font-size: 1.5rem;
  font-weight: 500;
  color: var(--dim);
  margin: 0.35rem 0 0;
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}

.detail {
  font-size: 0.78rem;
  color: var(--dim);
  margin: 0;
  /* Two lines then clip: a long spoken sentence must not be allowed to resize the whole rack. */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* --- states ------------------------------------------------------------------------- */
.mod.active {
  border-color: color-mix(in srgb, var(--lamp) 60%, transparent);
  background: color-mix(in srgb, var(--lamp) 7%, var(--panel));
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--lamp) 18%, transparent);
}
.mod.active .lamp {
  background: var(--lamp);
  box-shadow: 0 0 12px var(--lamp);
  animation: breathe 1.4s ease-in-out infinite;
}
.mod.active .readout { color: var(--lamp); }

.mod.done { border-color: color-mix(in srgb, var(--read) 30%, var(--rule)); }
.mod.done .lamp { background: var(--read); }
.mod.done .readout { color: var(--read); }

.mod.fault { border-color: color-mix(in srgb, var(--clay) 55%, transparent); }
.mod.fault .lamp { background: var(--clay); }
.mod.fault .readout { color: var(--clay); font-size: 1.05rem; }

@keyframes breathe {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.45; }
}

@media (prefers-reduced-motion: reduce) {
  .wire.live .pulse { animation: none; opacity: 1; transform: translateX(10px); }
  .mod.active .lamp { animation: none; }
}

@media (max-width: 900px) {
  /* Narrow screens drop the wires and let the modules wrap two-up — the left-to-right reading
     no longer fits, and a squeezed 5-across rack is unreadable long before it is pretty. */
  .chain { flex-wrap: wrap; gap: 0.6rem; }
  .chain > .wire { display: none; }
  .mod { flex: 1 1 calc(50% - 0.3rem); }
}
</style>
