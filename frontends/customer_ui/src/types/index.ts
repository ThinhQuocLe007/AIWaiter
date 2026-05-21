export interface FoodItem {
  id: string
  name: string
  description: string
  price: number // VND
  image: string // URL or path
  categoryId: string
  available: boolean
  preparationTime?: number // minutes
  ingredients?: string // comma-separated list of ingredients
  tasteProfile?: string // flavour summary, e.g. "Chua cay, đậm đà"
  tags?: string[]
  dietType?: string // e.g. "mặn", "chay"
}

export interface Category {
  id: string
  name: string
  icon?: string // emoji or icon name
  order: number
}

export interface CartItem {
  foodItem: FoodItem
  quantity: number
}

export type Screen = 'welcome' | 'menu' | 'confirmation'
