// Shared API types — mirror the backend pydantic schemas (src/backend/app/schemas.py).
// Dependency-free so any frontend (customer_ui, kiosk, panel) can import them via @shared.

export interface OrderItem {
  id: number
  order_id?: number
  dish_id?: number | null
  name: string
  qty: number
  price: number
  note?: string | null
  status: string
}

export interface Order {
  id: number
  table_id: number
  status: string
  total: number
  created_at: string
  items: OrderItem[]
}

export interface Table {
  id: number
  name: string
  capacity: number
  status: string
  current_order_id?: number | null
  party_size?: number | null
  seated_at?: string | null
}

export interface Robot {
  id: string
  name?: string | null
  status: string
  battery?: number | null
  activity?: string | null
  current_task_id?: number | null
}

// A dispatcher task (go_to_table / deliver / call) handed to a robot. Mirrors TaskOut.
export interface Task {
  id: number
  kind: string
  table_id?: number | null
  order_id?: number | null
  robot_id?: string | null
  status: string
  created_at: string
  updated_at: string
}

// WebSocket events pushed from the backend hub (src/backend/app/ws.py).
export type WsEvent =
  | { type: 'order.created'; order: Order }
  | { type: 'order.updated'; order: Order }
  | { type: 'table.updated'; table: Table }
  | { type: 'robot.updated'; robot: Robot }
  | { type: 'task.created'; task: Task }
  | { type: 'task.updated'; task: Task }
  | { type: 'reset' }
