<template>
  <!-- A big, self-explanatory glyph for the robot's action, so a room that never reads the
       transcript still sees WHAT the robot was told: go to a slot, lift, stop, resume, cancel.
       Colour follows the phase (currentColor) so it sits inside the same visual language. -->
  <div class="glyph" :class="`k-${kind}`" aria-hidden="true">
    <span class="halo" v-if="kind === 'navigate'"></span>
    <svg viewBox="0 0 120 120">
      <!-- navigate: a location pin -->
      <g v-if="kind === 'navigate'">
        <path
          d="M60 18c-15 0-26 11.5-26 25.5C34 60 60 88 60 88s26-28 26-44.5C86 29.5 75 18 60 18z"
          fill="currentColor"
          opacity="0.92"
        />
        <circle cx="60" cy="43" r="10" fill="#fff" />
      </g>

      <!-- lift up / down: an arrow over a box -->
      <g v-else-if="kind === 'lift'">
        <rect x="38" y="78" width="44" height="30" rx="6" fill="currentColor" opacity="0.9" />
        <rect x="44" y="84" width="32" height="6" rx="3" fill="#fff" opacity="0.8" />
        <path
          v-if="dir === 'up'"
          d="M60 64V26M44 42l16-16 16 16"
          fill="none"
          stroke="currentColor"
          stroke-width="7"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
        <path
          v-else
          d="M60 40V78M44 62l16 16 16-16"
          fill="none"
          stroke="currentColor"
          stroke-width="7"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </g>

      <!-- control: stop / resume / cancel -->
      <g v-else-if="kind === 'control'">
        <!-- stop: octagon + bar -->
        <path
          v-if="verb === 'stop'"
          d="M44 30h32l14 14v32l-14 14H44L30 76V44z"
          fill="currentColor"
          opacity="0.92"
        />
        <rect v-if="verb === 'stop'" x="44" y="57" width="32" height="8" rx="4" fill="#fff" />
        <!-- resume: play triangle -->
        <path
          v-else-if="verb === 'resume'"
          d="M42 32l40 28-40 28z"
          fill="currentColor"
          opacity="0.92"
        />
        <!-- cancel: ring + cross -->
        <g v-else>
          <circle cx="60" cy="60" r="30" fill="none" stroke="currentColor" stroke-width="8" />
          <path d="M45 45l30 30M75 45l-30 30" stroke="currentColor" stroke-width="8" stroke-linecap="round" />
        </g>
      </g>

      <!-- fallback: a speech dot -->
      <g v-else>
        <circle cx="60" cy="60" r="26" fill="currentColor" opacity="0.85" />
      </g>
    </svg>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ action: Record<string, any> | null }>()

const kind = computed(() => {
  const a = props.action
  if (!a) return 'none'
  if (a.type === 'navigate') return 'navigate'
  if (a.type === 'lift') return 'lift'
  if (a.type === 'control') return 'control'
  return 'none'
})

const verb = computed(() => String(props.action?.verb ?? 'stop'))
const dir = computed(() => String(props.action?.direction ?? 'up'))
</script>

<style scoped>
.glyph {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--state);
  filter: drop-shadow(0 10px 26px color-mix(in srgb, var(--state) 45%, transparent));
  animation: pop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1), breathe 2.4s ease-in-out infinite 0.4s;
}

.glyph svg {
  width: 100%;
  height: 100%;
  overflow: visible;
}

/* Navigate gets a soft ping ring pushing outward, like a target lighting up. */
.halo {
  position: absolute;
  width: 64%;
  height: 64%;
  border-radius: 50%;
  border: 3px solid var(--state);
  opacity: 0;
  animation: ping 1.8s ease-out infinite;
}

@keyframes pop {
  0% { transform: scale(0.5); opacity: 0; }
  100% { transform: scale(1); opacity: 1; }
}
@keyframes breathe {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.07); }
}
@keyframes ping {
  0% { opacity: 0.6; transform: scale(0.7); }
  100% { opacity: 0; transform: scale(1.6); }
}

@media (prefers-reduced-motion: reduce) {
  .glyph, .halo { animation: none; }
}
</style>
