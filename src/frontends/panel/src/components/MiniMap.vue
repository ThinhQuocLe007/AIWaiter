<template>
  <aside
    ref="panelEl"
    class="minimap"
    :class="{ dragging }"
    :style="panelStyle"
  >
    <div
      class="minimap-title"
      @pointerdown="onDragStart"
      @pointermove="onDragMove"
      @pointerup="onDragEnd"
      @pointercancel="onDragEnd"
    >
      <span>🗺 Bản đồ</span>
      <span class="minimap-sub">{{ robots.length }} robot</span>
    </div>
    <p v-if="!layout" class="minimap-empty">Đang tải…</p>
    <svg
      v-else
      class="minimap-svg"
      :viewBox="`0 0 ${layout.map.height} ${layout.map.width}`"
      preserveAspectRatio="xMidYMid meet"
    >
      <!-- Real SLAM map as the backdrop, rotated 90° counter-clockwise so the dock sits at
           the bottom. The overlays below are positioned with project(), which applies the
           same rotation, so they stay aligned with the walls. -->
      <image
        :href="imageUrl"
        x="0"
        y="0"
        :width="layout.map.width"
        :height="layout.map.height"
        :transform="`translate(0 ${layout.map.width}) rotate(-90)`"
      />

      <!-- Dock -->
      <g class="dock">
        <rect :x="dockPt.x - 7" :y="dockPt.y - 5" width="14" height="10" rx="2" />
        <text :x="dockPt.x" :y="dockPt.y" class="dock-label">DOCK</text>
      </g>

      <!-- Tables -->
      <g v-for="t in tablePts" :key="t.id" class="table" :class="tableClass(t.id)">
        <rect
          :x="t.x - tablePx / 2"
          :y="t.y - tablePx / 2"
          :width="tablePx"
          :height="tablePx"
          rx="1.5"
        />
        <text :x="t.x" :y="t.y" class="table-label">{{ t.id }}</text>
      </g>

      <!-- Robots -->
      <g
        v-for="r in robotPoses"
        :key="r.id"
        class="robot"
        :class="r.status"
        :transform="`translate(${r.x} ${r.y})`"
      >
        <title>{{ r.label }}</title>
        <circle class="robot-halo" r="8" />
        <circle class="robot-dot" r="4.5" />
      </g>
    </svg>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Layout, Robot, Table } from '@shared/types'

const props = defineProps<{ layout: Layout | null; robots: Robot[]; tables: Table[] }>()

// ---- Drag the whole HUD card around the screen (grab the title bar) ----
const panelEl = ref<HTMLElement | null>(null)
const pos = ref<{ left: number; top: number } | null>(null) // null = default corner anchor
const dragging = ref(false)
let grabOffset = { x: 0, y: 0 } // pointer position relative to the card's top-left corner

// Once dragged, switch from the right/bottom anchor to absolute left/top.
const panelStyle = computed(() =>
  pos.value
    ? { left: `${pos.value.left}px`, top: `${pos.value.top}px`, right: 'auto', bottom: 'auto' }
    : {},
)

function onDragStart(e: PointerEvent) {
  if (!panelEl.value) return
  const rect = panelEl.value.getBoundingClientRect()
  grabOffset = { x: e.clientX - rect.left, y: e.clientY - rect.top }
  dragging.value = true
  ;(e.currentTarget as Element).setPointerCapture(e.pointerId)
  e.preventDefault()
}
function onDragMove(e: PointerEvent) {
  if (!dragging.value || !panelEl.value) return
  const rect = panelEl.value.getBoundingClientRect()
  // Keep the card fully inside the viewport.
  const maxLeft = window.innerWidth - rect.width
  const maxTop = window.innerHeight - rect.height
  pos.value = {
    left: Math.min(Math.max(0, e.clientX - grabOffset.x), Math.max(0, maxLeft)),
    top: Math.min(Math.max(0, e.clientY - grabOffset.y), Math.max(0, maxTop)),
  }
}
function onDragEnd(e: PointerEvent) {
  dragging.value = false
  ;(e.currentTarget as Element).releasePointerCapture?.(e.pointerId)
}

const API_BASE = import.meta.env.VITE_API_URL ?? '/api'
const imageUrl = computed(() => (props.layout ? `${API_BASE}${props.layout.map.image_url}` : ''))

// A table's footprint in image pixels (metres / resolution).
const tablePx = computed(() =>
  props.layout ? props.layout.tables[0]?.w / props.layout.map.resolution || 14 : 14,
)

// Map frame (metres, y-up) → SVG point, with a 90° counter-clockwise rotation so the dock
// ends up at the bottom. First map to image pixels (y-down, per restaurant.yaml), then rotate
// (ox, oy) → (oy, width - ox) — matching the <image> transform above.
function project(x: number, y: number): { x: number; y: number } {
  if (!props.layout) return { x: 0, y: 0 }
  const m = props.layout.map
  const ox = (x - m.origin_x) / m.resolution
  const oy = m.height - (y - m.origin_y) / m.resolution
  return { x: oy, y: m.width - ox }
}

const dockPt = computed(() => project(props.layout?.dock.x ?? 0, props.layout?.dock.y ?? 0))
const tablePts = computed(() =>
  (props.layout?.tables ?? []).map((t) => ({ id: t.id, ...project(t.x, t.y) })),
)

// Tables that are occupied / paid get a different fill so the map reads at a glance.
function tableClass(id: number): string {
  const t = props.tables.find((tb) => tb.id === id)
  if (!t || t.status === 'TRONG') return 'free'
  if (t.status === 'DA_THANH_TOAN') return 'paid'
  return 'occupied'
}

// Resolve each robot's draw position; fall back to the dock until it sends its first pose.
const robotPoses = computed(() =>
  props.robots.map((r) => {
    const wx = r.x ?? props.layout?.dock.x ?? 0
    const wy = r.y ?? props.layout?.dock.y ?? 0
    const name = r.name ?? r.id
    const batt = r.battery != null ? ` · ${Math.round(r.battery)}%` : ''
    const p = project(wx, wy)
    return { id: r.id, status: r.status, x: p.x, y: p.y, label: `${name}${batt}` }
  }),
)
</script>

<style scoped>
/* The title bar is the drag handle for moving the whole HUD card. */
.minimap-title {
  cursor: grab;
  touch-action: none; /* let pointer drag move the card instead of scrolling on touch */
  user-select: none;
}
.minimap.dragging {
  cursor: grabbing;
}
.minimap.dragging .minimap-title {
  cursor: grabbing;
}
</style>
