export interface FoodItem {
  id: string
  name: string
  price: number // VND
  image?: string // URL or path; optional — text-first when absent
  categoryId: string
  available: boolean
  preparationTime?: number // minutes
  tasteProfile?: string // flavour summary, e.g. "Chua cay, đậm đà"
  tags?: string[]
  dietType?: string // e.g. "mặn", "chay"
  group?: string // optional cluster label, e.g. "Cơm Chiên" — variants sharing one image/header
  featuredName?: string // full name shown in the Best Seller showcase, e.g. "Ốc Hương Trứng Muối"
}

export interface Category {
  id: string
  name: string
  icon?: string // emoji or icon name
  order: number
}

// A cluster of one or more menu items shown under a single image + header.
// Single dishes become a group with one item; variant families
// (e.g. "Cơm Chiên" → Tỏi / Hải Sản / Dương Châu) group their options.
export interface DishGroup {
  id: string
  name: string // group label, or the dish name when standalone
  image?: string // representative image (optional; text-first when absent)
  categoryId: string
  items: FoodItem[] // one or more options
  priceLabel: string // "90.000" or "90.000 – 99.000"
  isBestSeller: boolean
}

export interface CartItem {
  foodItem: FoodItem
  quantity: number
}

export type Screen = 'welcome' | 'menu' | 'confirmation'
