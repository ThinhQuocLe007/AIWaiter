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

// --- Tables -----------------------------------------------------------------
// Minimal view of a table row (mirror of backend TableOut) — enough for this
// tablet to decide which screen to show on load.
export interface TableInfo {
  id: number
  name: string
  status: string
  current_order_id?: number | null
}

// GET /tables/{id} → this table's current serving state.
export function fetchTable(tableId: number): Promise<TableInfo> {
  return getJson<TableInfo>(`/tables/${tableId}`)
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

// GET /orders/{id} → the table's active order (used to bill the right total at payment).
export function fetchOrder(orderId: number): Promise<CreatedOrder> {
  return getJson<CreatedOrder>(`/orders/${orderId}`)
}

// --- Payments (mock) --------------------------------------------------------
// Mirror of backend PaymentOut (src/backend/app/schemas.py).
export interface Payment {
  id: number
  order_id: number
  method?: string | null
  amount: number
  status: string
  txn_ref?: string | null
  paid_at?: string | null
}

// POST /payments/{orderId} → confirm a mock payment: records it PAID and flips the table to
// DA_THANH_TOAN so the panel can clear it. (No real transfer — the QR is a visual mock.)
export function payOrder(orderId: number, method = 'VIETQR'): Promise<Payment> {
  return postJson<Payment>(`/payments/${orderId}`, { method })
}
