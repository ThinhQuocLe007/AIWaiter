// Thin REST client for the Orchestrator backend.
// Base URL comes from VITE_API_URL (.env), defaulting to a same-origin relative path.
import type { RawMenuItem } from './menuAdapter'

// '/api' (relative): the browser calls the Vite dev server's own origin and Vite
// proxies '/api/*' to FastAPI:8000 (see vite.config.ts) → no CORS, matches prod
// where FastAPI serves the static build from the same origin.
const API_URL = import.meta.env.VITE_API_URL ?? '/api'

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`)
  if (!res.ok) throw new Error(`GET ${path} → ${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

// GET /menu → raw menu items (same shape as assets/data/menu.json).
export function fetchMenu(): Promise<RawMenuItem[]> {
  return getJson<RawMenuItem[]>('/menu')
}
