import { onMounted, onUnmounted } from 'vue'

// Kiosk touch-scroll bridge.
//
// The hardware target is a resistive/capacitive touchscreen driven by Chromium on
// the Jetson. Native touch panning inside `overflow: auto` containers is unreliable
// there (the panel only scrolls when you drag the scrollbar), so we implement
// finger/pointer drag-to-scroll ourselves with momentum. This runs app-wide from a
// single document-level listener, so no scroll container needs to opt in.
//
// It coexists with taps: a gesture only becomes a scroll once it moves past a small
// threshold, and a real drag suppresses the trailing click so buttons still behave.

const DRAG_THRESHOLD = 8 // px of finger travel before a press turns into a scroll
const FRICTION = 0.94 // per-frame velocity decay for the fling
const MIN_VELOCITY = 0.05 // px/ms below which momentum stops

type Axis = 'x' | 'y'

function currentScale(): number {
  const raw = getComputedStyle(document.documentElement).getPropertyValue('--app-scale')
  const scale = parseFloat(raw)
  return Number.isFinite(scale) && scale > 0 ? scale : 1
}

function isScrollable(el: HTMLElement, axis: Axis): boolean {
  const style = getComputedStyle(el)
  if (axis === 'y') {
    const oy = style.overflowY
    return (oy === 'auto' || oy === 'scroll') && el.scrollHeight - el.clientHeight > 1
  }
  const ox = style.overflowX
  return (ox === 'auto' || ox === 'scroll') && el.scrollWidth - el.clientWidth > 1
}

function scrollableAncestor(start: HTMLElement | null, axis: Axis): HTMLElement | null {
  let node: HTMLElement | null = start
  while (node && node !== document.body && node !== document.documentElement) {
    if (isScrollable(node, axis)) return node
    node = node.parentElement
  }
  return null
}

export function useDragScroll() {
  let target: HTMLElement | null = null
  let axis: Axis | null = null
  let dragging = false
  let didDrag = false
  let startX = 0
  let startY = 0
  let lastX = 0
  let lastY = 0
  let lastT = 0
  let velocity = 0
  let momentumId = 0
  let pressEl: HTMLElement | null = null
  let styledEl: HTMLElement | null = null // element whose scroll-behavior we overrode

  function restoreBehavior() {
    if (styledEl) {
      styledEl.style.scrollBehavior = ''
      styledEl = null
    }
  }

  function stopMomentum() {
    if (momentumId) {
      cancelAnimationFrame(momentumId)
      momentumId = 0
    }
    restoreBehavior()
  }

  function onPointerDown(e: PointerEvent) {
    // Ignore secondary mouse buttons; let touch/pen/left-click through.
    if (e.pointerType === 'mouse' && e.button !== 0) return
    stopMomentum()
    target = null
    axis = null
    dragging = false
    didDrag = false
    startX = lastX = e.clientX
    startY = lastY = e.clientY
    lastT = e.timeStamp
    velocity = 0
    // Remember where the press began so the first significant move can pick an axis.
    pressEl = e.target instanceof HTMLElement ? e.target : null
  }

  function onPointerMove(e: PointerEvent) {
    if (pressEl == null) return
    const scale = currentScale()
    const dx = e.clientX - startX
    const dy = e.clientY - startY

    if (!dragging) {
      if (Math.abs(dx) < DRAG_THRESHOLD && Math.abs(dy) < DRAG_THRESHOLD) return
      // Lock the axis to the dominant direction of the opening move, then find the
      // nearest container that can actually scroll that way.
      axis = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y'
      target = scrollableAncestor(pressEl, axis)
      if (!target) {
        // Nothing scrollable this direction — bail out for the rest of the gesture.
        pressEl = null
        return
      }
      dragging = true
      didDrag = true
      // `scroll-behavior: smooth` (used on the best-seller strip) would smooth every
      // per-frame assignment and make the drag feel laggy — force instant while active.
      target.style.scrollBehavior = 'auto'
      styledEl = target
    }

    if (!target || !axis) return
    // Content is rendered inside a scaled stage; divide by the scale so the surface
    // tracks the finger 1:1 on the dev browser (scale === 1 on the kiosk).
    if (axis === 'y') {
      target.scrollTop -= (e.clientY - lastY) / scale
    } else {
      target.scrollLeft -= (e.clientX - lastX) / scale
    }

    const dt = e.timeStamp - lastT
    if (dt > 0) {
      const moved = axis === 'y' ? e.clientY - lastY : e.clientX - lastX
      velocity = moved / scale / dt // px/ms in content space
    }
    lastX = e.clientX
    lastY = e.clientY
    lastT = e.timeStamp
    e.preventDefault()
  }

  function onPointerUp() {
    pressEl = null
    if (!dragging || !target || !axis) {
      dragging = false
      return
    }
    const el = target
    const ax = axis
    dragging = false

    // Fling: keep gliding in the release direction until friction drains the velocity.
    if (Math.abs(velocity) > MIN_VELOCITY) {
      let last = performance.now()
      const step = (now: number) => {
        const dt = now - last
        last = now
        const delta = velocity * dt
        if (ax === 'y') el.scrollTop -= delta
        else el.scrollLeft -= delta
        velocity *= FRICTION
        if (Math.abs(velocity) > MIN_VELOCITY) {
          momentumId = requestAnimationFrame(step)
        } else {
          momentumId = 0
          restoreBehavior() // hand snapping/smooth back to CSS
        }
      }
      momentumId = requestAnimationFrame(step)
    } else {
      restoreBehavior()
    }
  }

  // A gesture that scrolled must not also fire a click on whatever button it started on.
  function onClickCapture(e: MouseEvent) {
    if (didDrag) {
      e.stopPropagation()
      e.preventDefault()
      didDrag = false
    }
  }

  onMounted(() => {
    document.addEventListener('pointerdown', onPointerDown, { passive: true })
    document.addEventListener('pointermove', onPointerMove, { passive: false })
    document.addEventListener('pointerup', onPointerUp, { passive: true })
    document.addEventListener('pointercancel', onPointerUp, { passive: true })
    document.addEventListener('click', onClickCapture, { capture: true })
  })

  onUnmounted(() => {
    stopMomentum()
    document.removeEventListener('pointerdown', onPointerDown)
    document.removeEventListener('pointermove', onPointerMove)
    document.removeEventListener('pointerup', onPointerUp)
    document.removeEventListener('pointercancel', onPointerUp)
    document.removeEventListener('click', onClickCapture, { capture: true })
  })
}
