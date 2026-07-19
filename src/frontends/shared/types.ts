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
  x?: number | null // live world-frame pose (for the minimap)
  y?: number | null
  current_task_id?: number | null
}

// Floor-plan geometry + SLAM map metadata for the panel minimap (map frame, metres).
// Mirrors GET /layout. Frame→pixel: px = (x-origin_x)/resolution, py = height-(y-origin_y)/resolution.
export interface MapMeta {
  image_url: string // PNG of the SLAM map, relative to the API base
  width: number // image size in pixels
  height: number
  resolution: number // metres per pixel
  origin_x: number // map-frame coords of the image's bottom-left corner
  origin_y: number
}
export interface LayoutTable {
  id: number
  x: number
  y: number
  w: number
  h: number
}
export interface Layout {
  map: MapMeta
  tables: LayoutTable[]
  dock: { x: number; y: number }
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

// A UI action the agent emits for the customer tablet (src/backend/app/routers/voice.py).
export interface UiAction {
  type: 'ui'
  action: 'open_menu' | 'open_payment'
}

// One line of the agent's live cart draft, mirrored to the tablet with each voice.reply so the
// web cart can stay in sync with what the guest ordered by voice. Names are official menu names
// (the agent's validator strips off-menu items).
export interface VoiceCartItem {
  name: string
  quantity: number
  note?: string | null
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
  // Voice mirror (role=customer): what the robot heard / replied for a given table. The tablet
  // filters by its own table_id and shows the live conversation + follows any UI action.
  | { type: 'voice.progress'; table_id: number }
  | { type: 'voice.heard'; table_id: number; text: string }
  | {
      type: 'voice.reply'
      table_id: number
      text: string
      action: UiAction | null
      stage?: string
      // The agent's cart draft after this turn; null/undefined when the turn didn't touch it.
      cart?: VoiceCartItem[] | null
      // True only on the turn the order was sent to the kitchen (confirm_order ran).
      confirmed?: boolean | null
    }
