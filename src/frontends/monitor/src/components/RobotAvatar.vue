<template>
  <!-- Drawn, not photographed. An AMR (autonomous mobile robot) recolours with the phase — the
       beacon, the LIDAR ring, the friendly eyes and the chest light all take `currentColor`,
       which the page sets to the phase colour — so a room reads the robot's state without text. -->
  <svg
    class="bot"
    :class="[`is-${phase}`, { active: phase === 'listening' || phase === 'speaking' }]"
    viewBox="0 0 260 292"
    role="img"
    :aria-label="`AGV — ${phase}`"
  >
    <defs>
      <linearGradient id="shell" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#ffffff" />
        <stop offset="58%" stop-color="#eef2f6" />
        <stop offset="100%" stop-color="#cdd7e2" />
      </linearGradient>
      <linearGradient id="visor" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#1e293b" />
        <stop offset="100%" stop-color="#0f172a" />
      </linearGradient>
      <radialGradient id="lamp" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="currentColor" stop-opacity="0.95" />
        <stop offset="100%" stop-color="currentColor" stop-opacity="0" />
      </radialGradient>
    </defs>

    <!-- Halo: faint phase-coloured rings behind the robot, so the state reads from the back of
         the room even before anyone reads the caption. -->
    <g class="halo" fill="none" stroke="currentColor">
      <circle cx="130" cy="150" r="104" stroke-width="1.5" opacity="0.28" />
      <circle cx="130" cy="150" r="124" stroke-width="1.2" opacity="0.16" />
      <circle cx="130" cy="150" r="144" stroke-width="1" opacity="0.08" />
    </g>

    <ellipse class="ground" cx="130" cy="280" rx="82" ry="10" fill="#000" opacity="0.16" />

    <g class="body">
      <!-- beacon on top -->
      <circle class="tip" cx="130" cy="46" r="12" fill="currentColor" />
      <circle class="tip-glow" cx="130" cy="46" r="24" fill="url(#lamp)" />

      <!-- LIDAR dome -->
      <rect x="104" y="86" width="52" height="24" rx="12" fill="#c2cdda" />
      <ellipse cx="130" cy="84" rx="36" ry="15" fill="url(#shell)" stroke="#c2cdda" stroke-width="1.5" />
      <ellipse cx="130" cy="84" rx="36" ry="15" fill="none" stroke="currentColor" stroke-width="2" opacity="0.55" />

      <!-- main body -->
      <rect x="44" y="104" width="172" height="158" rx="44" fill="url(#shell)" stroke="#c2cdda" stroke-width="2" />

      <!-- face screen -->
      <rect x="74" y="140" width="112" height="70" rx="26" fill="url(#visor)" />
      <g class="eyes" fill="currentColor">
        <rect x="98" y="162" width="22" height="14" rx="7" />
        <rect x="140" y="162" width="22" height="14" rx="7" />
      </g>
      <!-- talking mouth: only while the robot is actually speaking, so a room reads "nó đang nói"
           without a word of the transcript. -->
      <g v-if="phase === 'speaking'" class="mouth" fill="currentColor">
        <rect x="108" y="190" width="6" height="14" rx="3" />
        <rect x="119" y="187" width="6" height="18" rx="3" />
        <rect x="130" y="186" width="6" height="20" rx="3" />
        <rect x="141" y="187" width="6" height="18" rx="3" />
        <rect x="152" y="190" width="6" height="14" rx="3" />
      </g>

      <!-- chest status light -->
      <circle class="chest" cx="130" cy="228" r="9" fill="currentColor" />

      <!-- wheels -->
      <rect x="54" y="236" width="30" height="40" rx="15" fill="#334155" />
      <rect x="176" y="236" width="30" height="40" rx="15" fill="#334155" />
    </g>
  </svg>
</template>

<script setup lang="ts">
import type { Phase } from '../phase'

defineProps<{ phase: Phase }>()
</script>

<style scoped>
.bot {
  width: 100%;
  height: 100%;
  overflow: visible;
  color: inherit;
  filter: drop-shadow(0 18px 34px rgba(15, 23, 42, 0.28));
}

/* A slow float, always on: a perfectly still robot in the middle of a big screen looks switched
   off, and the demo's first impression happens before anyone presses a button. */
.body {
  animation: float 5s ease-in-out infinite;
  transform-origin: 130px 170px;
}
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-7px); }
}

.halo { opacity: 0.5; transform-origin: 130px 150px; }
.bot.active .halo { animation: breathe 2.4s ease-in-out infinite; }
@keyframes breathe {
  0%, 100% { opacity: 0.32; transform: scale(0.97); }
  50% { opacity: 0.9; transform: scale(1.04); }
}

.tip-glow { opacity: 0.45; }
.bot.active .tip-glow { animation: lamp 1.4s ease-in-out infinite; }
.eyes { opacity: 0.9; }
.bot.active .eyes { animation: lamp 1.4s ease-in-out infinite; }

/* Speaking: bars where a mouth would be. Different delays per bar, or it reads as one block
   moving rather than as syllables. */
.mouth rect { animation: talk 0.5s ease-in-out infinite; transform-origin: center 197px; }
.mouth rect:nth-child(2) { animation-delay: 0.08s; }
.mouth rect:nth-child(3) { animation-delay: 0.16s; }
.mouth rect:nth-child(4) { animation-delay: 0.24s; }
.mouth rect:nth-child(5) { animation-delay: 0.32s; }
@keyframes talk {
  0%, 100% { transform: scaleY(0.45); }
  50% { transform: scaleY(1); }
}

.chest { opacity: 0.85; }
.bot.active .chest { animation: lamp 1.4s ease-in-out infinite; }
@keyframes lamp {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 1; }
}

/* Anyone who has told their OS they get motion sick gets a static robot; the phase still reads,
   because the colour carries it without a single frame of animation. */
@media (prefers-reduced-motion: reduce) {
  .body, .halo, .tip-glow, .eyes, .chest, .mouth rect { animation: none; }
}
</style>
