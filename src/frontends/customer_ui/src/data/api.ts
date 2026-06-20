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

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`POST ${path} → ${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

// GET /menu → raw menu items (same shape as assets/data/menu.json).
export function fetchMenu(): Promise<RawMenuItem[]> {
  return getJson<RawMenuItem[]>('/menu')
}

// --- Orders -----------------------------------------------------------------
export interface OrderItemPayload {
  name: string
  qty: number
  price: number
  dish_id?: number
  note?: string
}

export interface CreatedOrder {
  id: number
  table_id: number
  status: string
  total: number
  created_at: string
  items: Array<OrderItemPayload & { id: number; status: string }>
}

// POST /orders → persist the cart server-side (total is recomputed by the backend).
export function createOrder(
  tableId: number,
  items: OrderItemPayload[],
): Promise<CreatedOrder> {
  return postJson<CreatedOrder>('/orders', { table_id: tableId, items })
}
