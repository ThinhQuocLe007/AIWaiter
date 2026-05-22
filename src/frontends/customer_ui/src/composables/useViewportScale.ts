import { onMounted, onUnmounted } from 'vue'

// The hardware target is a fixed 1024x600 LCD. On a dev machine the browser
// window rarely matches that exactly, so we scale the 1024x600 stage to fit the
// current viewport while preserving aspect ratio. On the kiosk the scale is 1.
const DESIGN_WIDTH = 1024
const DESIGN_HEIGHT = 600

export function useViewportScale() {
  function applyScale() {
    const scale = Math.min(
      window.innerWidth / DESIGN_WIDTH,
      window.innerHeight / DESIGN_HEIGHT,
    )
    document.documentElement.style.setProperty('--app-scale', String(scale))
  }

  onMounted(() => {
    applyScale()
    window.addEventListener('resize', applyScale)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', applyScale)
  })
}
