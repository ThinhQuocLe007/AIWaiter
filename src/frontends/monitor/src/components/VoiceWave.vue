<template>
  <canvas ref="cv" class="wave" aria-hidden="true"></canvas>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import type { Phase } from '../phase'

const props = defineProps<{ phase: Phase; color: string }>()

/* The one instrument on this screen. It replaces five numeric readouts, so it has to carry the
   difference between "listening", "thinking" and "answering" on shape alone — the label under it
   is a caption, not the message.

   What the shape is NOT: a picture of the actual audio. The microphone is on the Jetson, several
   network hops away; this page never sees a sample. So the wave is driven by the phase plus a
   smoothed random walk, which is honest about what it shows (the robot's STATE, live) and never
   pretends to be a level meter. The random walk is the whole reason it reads as alive rather than
   as a screensaver: a perfectly periodic sine looks like a loading spinner. */

// Per phase: amplitude (0–1 of half-height), how fast the wave travels, how hard the random walk
// modulates it. Listening breathes with "the room"; thinking is small, fast and busy; answering is
// the biggest and most rhythmic, because that is the moment the audience should look at the robot.
const SHAPE: Record<Phase, { amp: number; speed: number; jitter: number }> = {
  idle: { amp: 0.05, speed: 0.5, jitter: 0.0 },
  listening: { amp: 0.58, speed: 1.5, jitter: 0.85 },
  thinking: { amp: 0.2, speed: 3.4, jitter: 0.25 },
  speaking: { amp: 0.8, speed: 2.1, jitter: 0.7 },
  result: { amp: 0.07, speed: 0.5, jitter: 0.0 },
  quiet: { amp: 0.05, speed: 0.5, jitter: 0.0 },
  error: { amp: 0.1, speed: 0.8, jitter: 0.0 },
}

// Three strokes, not one: the two thin off-beat harmonics are what stop the ribbon looking like a
// single mathematical sine. Each has its own wavelength, direction and phase offset.
const LAYERS = [
  { cycles: 2.1, dir: 1, width: 3.0, alpha: 1.0, amp: 1.0, offset: 0 },
  { cycles: 3.4, dir: -0.7, width: 2.0, alpha: 0.45, amp: 0.62, offset: 1.1 },
  { cycles: 5.2, dir: 1.6, width: 1.4, alpha: 0.22, amp: 0.34, offset: 2.4 },
]

const cv = ref<HTMLCanvasElement | null>(null)
let raf = 0
let ro: ResizeObserver | null = null
let last = 0
let clock = 0 // seconds of animation time, advanced by real elapsed time
let amp = 0.05 // eased toward the phase target so a phase change glides instead of snapping
let energy = 0.5 // smoothed random walk in 0..1 — the "is anyone talking" wobble

function resize() {
  const el = cv.value
  if (!el) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const w = el.clientWidth
  const h = el.clientHeight
  if (!w || !h) return
  el.width = Math.round(w * dpr)
  el.height = Math.round(h * dpr)
  const ctx = el.getContext('2d')
  ctx?.setTransform(dpr, 0, 0, dpr, 0, 0)
}

function frame(now: number) {
  raf = requestAnimationFrame(frame)
  const el = cv.value
  const ctx = el?.getContext('2d')
  if (!el || !ctx) return

  // Real elapsed time, capped: a backgrounded tab resumes with a huge delta, and without the cap
  // the wave would jump a full cycle the moment the demo screen is brought back to the front.
  const dt = last ? Math.min((now - last) / 1000, 0.05) : 0.016
  last = now

  const s = SHAPE[props.phase] ?? SHAPE.idle
  clock += dt * s.speed
  amp += (s.amp - amp) * Math.min(dt * 6, 1)
  energy += (Math.random() - energy) * Math.min(dt * 5, 1)

  const w = el.clientWidth
  const h = el.clientHeight
  const cy = h / 2
  const a = amp * (1 - s.jitter + s.jitter * energy) * (h / 2) * 0.86

  ctx.clearRect(0, 0, w, h)
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.strokeStyle = props.color
  ctx.shadowColor = props.color

  // Step in device-independent pixels; 3px is smooth at any width we render at and keeps the
  // per-frame cost flat on the Jetson's browser, which is the weakest machine that shows this.
  const step = 3
  for (const layer of LAYERS) {
    ctx.beginPath()
    for (let x = 0; x <= w; x += step) {
      const u = x / w
      // Taper to zero at both ends so the ribbon floats instead of being cut off by the panel.
      const taper = Math.sin(Math.PI * u) ** 1.5
      const y =
        cy +
        Math.sin(u * layer.cycles * Math.PI * 2 + clock * layer.dir + layer.offset) *
          a *
          layer.amp *
          taper
      if (x === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }
    ctx.globalAlpha = layer.alpha
    ctx.lineWidth = layer.width
    ctx.shadowBlur = layer.width * 4
    ctx.stroke()
  }
  ctx.globalAlpha = 1
  ctx.shadowBlur = 0
}

onMounted(() => {
  resize()
  ro = new ResizeObserver(resize)
  if (cv.value) ro.observe(cv.value)
  raf = requestAnimationFrame(frame)
})

onUnmounted(() => {
  cancelAnimationFrame(raf)
  ro?.disconnect()
})
</script>
