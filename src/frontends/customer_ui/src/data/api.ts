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

// --- Voice ------------------------------------------------------------------
// POST /voice/listen → ask this table's voice device (the Jetson/laptop mic loop) to capture one
// utterance. The browser does NOT record audio; the mic lives on the device. status is 'no_device'
// when no microphone is connected for this table (the panel then shows the assistant is offline).
export interface ListenResult {
  status: 'ok' | 'no_device'
}

export function startVoiceListen(tableId: number): Promise<ListenResult> {
  return postJson<ListenResult>('/voice/listen', { table_id: tableId })
}

// POST /voice/cancel → kill the whole in-flight voice turn on this table's device (the "Hủy"/
// "Dừng" button): drops an armed capture, stops consuming the agent's reply stream and cuts the
// robot's TTS mid-sentence.
export function cancelVoiceListen(tableId: number): Promise<ListenResult> {
  return postJson<ListenResult>('/voice/cancel', { table_id: tableId })
}

// POST /voice/mute → mute/unmute the robot's speaker for this table. Muting cuts the sentence
// currently playing; the agent's replies keep arriving as text bubbles either way.
export function setVoiceMuted(tableId: number, muted: boolean): Promise<ListenResult> {
  return postJson<ListenResult>('/voice/mute', { table_id: tableId, muted })
}

// POST /voice/new-chat → wipe the agent's conversation memory for this table (fresh LLM thread;
// the visit/bill continues). 'agent_unreachable' when the LLM service is down.
export interface NewChatResult {
  status: 'ok' | 'agent_unreachable'
}

export function newVoiceChat(tableId: number): Promise<NewChatResult> {
  return postJson<NewChatResult>('/voice/new-chat', { table_id: tableId })
}

// POST /voice/cart → push this tablet's cart draft to the agent, so the guest's manual +/− is
// part of the ONE cart both sides share. Always the whole draft (a replace, not a delta).
// Without it the agent keeps its own stale copy: it would replay it over the guest's edit on the
// next voice turn, and confirm_order would send the stale quantities to the kitchen.
export interface CartSyncItem {
  name: string
  quantity: number
  note?: string | null
}

export function syncCartToAgent(
  tableId: number,
  items: CartSyncItem[],
): Promise<NewChatResult> {
  return postJson<NewChatResult>('/voice/cart', { table_id: tableId, items })
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

// --- Payments (mock, gộp theo phiên) ----------------------------------------
// Mirror of backend PaymentOut (src/backend/app/schemas.py). The bill is per-session: the sum
// of every order in the table's active session, paid once.
export interface Payment {
  id: number
  session_id: number
  method?: string | null
  amount: number
  status: string
  txn_ref?: string | null
  qr_url?: string | null
  paid_at?: string | null
}

// POST /payments → open (or refresh) the gộp payment for this table's active session. Returns the
// running total + QR; status is PENDING until verified.
export function createPayment(tableId: number, method = 'VIETQR'): Promise<Payment> {
  return postJson<Payment>('/payments', { table_id: tableId, method })
}

// POST /payments/{id}/verify → confirm the (mock) payment: records it PAID, closes the session
// and flips the table to DA_THANH_TOAN so the panel can clear it. (No real transfer.)
export function verifyPayment(paymentId: number): Promise<Payment> {
  return postJson<Payment>(`/payments/${paymentId}/verify`, {})
}
