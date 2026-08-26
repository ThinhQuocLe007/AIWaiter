<template>
  <!-- Drawn, not photographed. An SVG robot re-colours with the phase (the halo, the antenna and
       the chest lamp all take `currentColor`, which the page sets to the phase colour), stays
       sharp on the hall projector, and can CHANGE ITS FACE — the eyes are what tell the room the
       robot is listening before anyone has read the caption. A photo could do none of that. -->
  <svg
    class="bot"
    :class="[`is-${phase}`, { active: phase === 'listening' || phase === 'speaking' }]"
    viewBox="0 0 260 292"
    role="img"
    :aria-label="`Robot — ${phase}`"
  >
    <defs>
      <linearGradient id="shell" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#f8fafc" />
        <stop offset="55%" stop-color="#dbe3ee" />
        <stop offset="100%" stop-color="#aab6c8" />
      </linearGradient>
      <linearGradient id="visor" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#131c2b" />
        <stop offset="100%" stop-color="#060b14" />
      </linearGradient>
      <radialGradient id="lamp" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="currentColor" stop-opacity="0.95" />
        <stop offset="100%" stop-color="currentColor" stop-opacity="0" />
      </radialGradient>
    </defs>

    <!-- Halo: three rings that only breathe while the robot is actually doing something. A halo
         that pulses forever would stop meaning anything the moment it mattered. -->
    <g class="halo" fill="none" stroke="currentColor">
      <circle cx="130" cy="112" r="88" stroke-width="1.5" opacity="0.35" />
      <circle cx="130" cy="112" r="108" stroke-width="1.2" opacity="0.2" />
      <circle cx="130" cy="112" r="130" stroke-width="1" opacity="0.1" />
    </g>

    <ellipse class="ground" cx="130" cy="277" rx="70" ry="9" fill="#000" opacity="0.45" />

    <g class="body">
      <!-- antenna -->
      <rect x="127" y="18" width="6" height="28" rx="3" fill="#94a3b8" />
      <circle class="tip" cx="130" cy="14" r="9" fill="currentColor" />
      <circle class="tip-glow" cx="130" cy="14" r="22" fill="url(#lamp)" />

      <!-- ears -->
      <rect x="42" y="80" width="16" height="46" rx="8" fill="#94a3b8" />
      <rect x="202" y="80" width="16" height="46" rx="8" fill="#94a3b8" />

      <!-- head -->
      <rect x="56" y="42" width="148" height="118" rx="40" fill="url(#shell)" />
      <rect x="72" y="60" width="116" height="82" rx="34" fill="url(#visor)" />

      <!-- face: the phase is written here first, and in words second -->
      <g class="face" fill="currentColor" stroke="currentColor">
        <template v-if="phase === 'listening'">
          <circle class="eye" cx="104" cy="101" r="12" stroke="none" />
          <circle class="eye" cx="156" cy="101" r="12" stroke="none" />
          <circle class="ping" cx="104" cy="101" r="12" fill="none" stroke-width="2" />
          <circle class="ping ping-2" cx="156" cy="101" r="12" fill="none" stroke-width="2" />
        </template>

        <template v-else-if="phase === 'thinking'">
          <!-- eyes turned up + three dots ticking over: "working on it", not "broken" -->
          <path d="M92 105 q12 -16 24 0" fill="none" stroke-width="6" stroke-linecap="round" />
          <path d="M144 105 q12 -16 24 0" fill="none" stroke-width="6" stroke-linecap="round" />
          <circle class="dot" cx="112" cy="126" r="4" stroke="none" />
          <circle class="dot dot-2" cx="130" cy="126" r="4" stroke="none" />
          <circle class="dot dot-3" cx="148" cy="126" r="4" stroke="none" />
        </template>

        <template v-else-if="phase === 'error'">
          <path d="M95 93 l18 18 M113 93 l-18 18" stroke-width="6" stroke-linecap="round" />
          <path d="M147 93 l18 18 M165 93 l-18 18" stroke-width="6" stroke-linecap="round" />
        </template>

        <template v-else-if="phase === 'speaking' || phase === 'result'">
          <!-- smiling eyes, and while it talks, five bars where a mouth would be -->
          <path d="M92 98 q12 16 24 0" fill="none" stroke-width="6" stroke-linecap="round" />
          <path d="M144 98 q12 16 24 0" fill="none" stroke-width="6" stroke-linecap="round" />
          <g v-if="phase === 'speaking'" class="mouth" stroke="none">
            <rect x="108" y="118" width="6" height="14" rx="3" />
            <rect x="119" y="116" width="6" height="18" rx="3" />
            <rect x="130" y="114" width="6" height="22" rx="3" />
            <rect x="141" y="116" width="6" height="18" rx="3" />
            <rect x="152" y="118" width="6" height="14" rx="3" />
          </g>
        </template>

        <template v-else>
          <!-- idle / quiet: calm capsule eyes that blink now and then -->
          <rect class="eye blink" x="94" y="88" width="20" height="28" rx="10" stroke="none" />
          <rect class="eye blink" x="146" y="88" width="20" height="28" rx="10" stroke="none" />
        </template>
      </g>

      <!-- arms -->
      <rect x="34" y="182" width="20" height="60" rx="10" fill="#b6c2d2" />
      <rect x="206" y="182" width="20" height="60" rx="10" fill="#b6c2d2" />

      <!-- torso -->
      <rect x="116" y="158" width="28" height="20" rx="8" fill="#94a3b8" />
      <rect x="60" y="172" width="140" height="96" rx="34" fill="url(#shell)" />
      <rect x="96" y="196" width="68" height="44" rx="16" fill="url(#visor)" />
      <circle class="chest" cx="130" cy="218" r="8" fill="currentColor" />
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
  /* The one place the phase colour enters the drawing; everything glowing below is currentColor. */
  color: inherit;
  filter: drop-shadow(0 24px 40px rgba(0, 0, 0, 0.55));
}

/* A slow float, always on: a perfectly still robot in the middle of a big screen looks switched
   off, and the demo's first impression happens before anyone presses a button. */
.body {
  animation: float 5s ease-in-out infinite;
  transform-origin: 130px 160px;
}
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-7px); }
}

.halo { opacity: 0.5; transform-origin: 130px 112px; }
.bot.active .halo { animation: breathe 2.4s ease-in-out infinite; }
@keyframes breathe {
  0%, 100% { opacity: 0.35; transform: scale(0.97); }
  50% { opacity: 0.9; transform: scale(1.04); }
}

.tip-glow { opacity: 0.5; }
.bot.active .tip-glow { animation: lamp 1.4s ease-in-out infinite; }
.chest { opacity: 0.9; }
.bot.active .chest { animation: lamp 1.4s ease-in-out infinite; }
@keyframes lamp {
  0%, 100% { opacity: 0.35; }
  50% { opacity: 1; }
}

/* Listening: rings pushing outward from each eye — the visual verb for "come on, talk to me". */
.ping { animation: ping 1.6s ease-out infinite; transform-origin: 104px 101px; }
.ping-2 { transform-origin: 156px 101px; animation-delay: 0.35s; }
@keyframes ping {
  0% { opacity: 0.85; transform: scale(1); }
  100% { opacity: 0; transform: scale(2.1); }
}

.dot { animation: tick 1.1s ease-in-out infinite; }
.dot-2 { animation-delay: 0.15s; }
.dot-3 { animation-delay: 0.3s; }
@keyframes tick {
  0%, 100% { opacity: 0.25; }
  50% { opacity: 1; }
}

/* Speaking: bars where a mouth would be. Different delays per bar, or it reads as one block
   moving rather than as syllables. */
.mouth rect { animation: talk 0.5s ease-in-out infinite; transform-origin: center 125px; }
.mouth rect:nth-child(2) { animation-delay: 0.08s; }
.mouth rect:nth-child(3) { animation-delay: 0.16s; }
.mouth rect:nth-child(4) { animation-delay: 0.24s; }
.mouth rect:nth-child(5) { animation-delay: 0.32s; }
@keyframes talk {
  0%, 100% { transform: scaleY(0.45); }
  50% { transform: scaleY(1); }
}

.blink { animation: blink 5.5s ease-in-out infinite; transform-origin: center 102px; }
.blink:last-of-type { animation-delay: 0.04s; }
@keyframes blink {
  0%, 92%, 100% { transform: scaleY(1); }
  95% { transform: scaleY(0.08); }
}

/* Anyone who has told their OS they get motion sick gets a static robot; the phase still reads,
   because the face and the colour carry it without a single frame of animation. */
@media (prefers-reduced-motion: reduce) {
  .body, .halo, .tip-glow, .chest, .ping, .dot, .mouth rect, .blink { animation: none; }
}
</style>
