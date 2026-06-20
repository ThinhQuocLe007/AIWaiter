// Shared REST client for the Orchestrator backend.
// Base URL defaults to the same-origin '/api' path (proxied to FastAPI by each app's Vite
// config), so there is no CORS and it matches production where FastAPI serves the static build.
import type { Order, Robot, Table } from './types'

const API_URL = import.meta.env.VITE_API_URL ?? '/api'

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`)
  if (!res.ok) throw new Error(`GET ${path} → ${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

async function sendJson<T>(method: string, path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${method} ${path} → ${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

// --- Orders ---------------------------------------------------------------------------
export interface OrderItemPayload {
  name: string
  qty: number
  price: number
  dish_id?: number
  note?: string
}

export function fetchOrders(params?: { table_id?: number; status?: string }): Promise<Order[]> {
  const q = new URLSearchParams()
  if (params?.table_id != null) q.set('table_id', String(params.table_id))
  if (params?.status) q.set('status', params.status)
  const qs = q.toString()
  return getJson<Order[]>(`/orders${qs ? `?${qs}` : ''}`)
}

export function createOrder(tableId: number, items: OrderItemPayload[]): Promise<Order> {
  return sendJson<Order>('POST', '/orders', { table_id: tableId, items })
}

export function updateOrderStatus(orderId: number, status: string): Promise<Order> {
  return sendJson<Order>('PATCH', `/orders/${orderId}`, { status })
}

// --- Tables / seatings ----------------------------------------------------------------
export function fetchTables(): Promise<Table[]> {
  return getJson<Table[]>('/tables')
}

export function fetchTable(tableId: number): Promise<Table> {
  return getJson<Table>(`/tables/${tableId}`)
}

export function createSeating(tableId: number, partySize: number): Promise<Table> {
  return sendJson<Table>('POST', '/seatings', { table_id: tableId, party_size: partySize })
}

export function updateTableStatus(tableId: number, status: string): Promise<Table> {
  return sendJson<Table>('PATCH', `/tables/${tableId}`, { status })
}

// --- Robots ---------------------------------------------------------------------------
export function fetchRobots(): Promise<Robot[]> {
  return getJson<Robot[]>('/robots')
}

// --- Admin / demo ---------------------------------------------------------------------
// Wipe all live state (orders, seatings, tasks), free every table, reset the mock fleet.
export function resetSystem(): Promise<{ status: string; tables_freed: number }> {
  return sendJson('POST', '/admin/reset', {})
}
