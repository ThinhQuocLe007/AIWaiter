import type { Category, DishGroup, FoodItem } from '@/types'

export interface RawMenuItem {
  name: string
  price: string
  diet_type: string
  category: string
  taste_profile: string
  tags: string
  group?: string
  image?: string
  featured_name?: string
}

// Maps the category display name from menu.json to its frontend metadata.
// Must stay in sync with the `category` values in assets/data/menu.json.
const CATEGORY_META: Record<string, { id: string; icon: string; order: number }> = {
  'Ốc & Sò':           { id: 'oc-so',        icon: '🐚', order: 1  },
  'Ốc Hấp':            { id: 'oc-hap',       icon: '🦪', order: 2  },
  'Món Nướng':         { id: 'nuong',        icon: '🍖', order: 3  },
  'Tôm':               { id: 'tom',          icon: '🦐', order: 4  },
  'Chiên & Khai Vị':   { id: 'chien-khai-vi', icon: '🍤', order: 5 },
  'Gỏi & Trộn':        { id: 'goi-tron',     icon: '🥗', order: 6  },
  'Lặt Vặt Ăn Chơi':  { id: 'lat-vat',      icon: '🍢', order: 7  },
  'Khô Lai Rai':       { id: 'kho-lai-rai',  icon: '🐟', order: 8  },
  'Món Lẩu':           { id: 'lau',          icon: '🍲', order: 9  },
  'Món Chính':         { id: 'mon-chinh',    icon: '🍛', order: 10 },
  'Mì - Cháo - Cơm':   { id: 'mi-chao-com',  icon: '🍜', order: 11 },
  'Giải Khát':         { id: 'giai-khat',    icon: '🥤', order: 12 },
}

const DEFAULT_ICON = '🍽️'

function slugify(value: string): string {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '') // strip combining diacritics
    .replace(/đ/g, 'd')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function categoryId(name: string): string {
  return CATEGORY_META[name]?.id ?? slugify(name)
}

function isBestSeller(tags: string): boolean {
  return tags.toLowerCase().includes('best seller')
}

function toFoodItem(raw: RawMenuItem, index: number): FoodItem {
  return {
    id: String(index + 1),
    name: raw.name,
    price: Number(raw.price),
    image: raw.image || undefined,
    categoryId: categoryId(raw.category),
    available: true,
    tasteProfile: raw.taste_profile,
    tags: raw.tags.split(',').map((t) => t.trim()),
    dietType: raw.diet_type,
    group: raw.group,
    featuredName: raw.featured_name,
  }
}

function priceLabel(items: FoodItem[]): string {
  const prices = items.map((i) => i.price)
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const fmt = (n: number) => new Intl.NumberFormat('vi-VN').format(n)
  return min === max ? fmt(min) : `${fmt(min)} – ${fmt(max)}`
}

// Cluster items within one category by their `group` label (falling back to the
// item name, so ungrouped dishes become single-option groups). Preserves the
// order in which groups first appear in the data.
function groupItems(items: FoodItem[]): DishGroup[] {
  const order: string[] = []
  const buckets = new Map<string, FoodItem[]>()
  for (const item of items) {
    const key = item.group ?? item.name
    if (!buckets.has(key)) {
      buckets.set(key, [])
      order.push(key)
    }
    buckets.get(key)!.push(item)
  }
  return order.map((key) => {
    const groupItemsList = buckets.get(key)!
    const first = groupItemsList[0]
    return {
      id: slugify(`${first.categoryId}-${key}`),
      name: key,
      image: groupItemsList.find((i) => i.image)?.image,
      categoryId: first.categoryId,
      items: groupItemsList,
      priceLabel: priceLabel(groupItemsList),
      isBestSeller: groupItemsList.some((i) => isBestSeller((i.tags ?? []).join(','))),
    }
  })
}

export interface AdaptedMenu {
  categories: Category[]
  foodItems: FoodItem[]
  bestSellers: FoodItem[]
  groupsByCategory: Record<string, DishGroup[]>
}

// Turn the raw menu.json payload (now fetched from the backend) into the display-ready
// shapes the store/components consume. Pure: same input → same output, no side effects.
export function adaptMenu(rawItems: RawMenuItem[]): AdaptedMenu {
  const foodItems: FoodItem[] = rawItems.map(toFoodItem)

  // Build the tab list from the categories that actually appear in the data, so any
  // new category added to the menu shows up even before it's listed in CATEGORY_META.
  const presentCategories = [...new Set(rawItems.map((r) => r.category))]
  const categories: Category[] = presentCategories
    .map((name) => ({
      id: categoryId(name),
      name,
      icon: CATEGORY_META[name]?.icon ?? DEFAULT_ICON,
      order: CATEGORY_META[name]?.order ?? 999,
    }))
    .sort((a, b) => a.order - b.order)

  // Dishes flagged "best seller" in their tags drive the Best Seller showcase.
  const bestSellers: FoodItem[] = foodItems.filter((item) =>
    (item.tags ?? []).some((t) => t.toLowerCase() === 'best seller'),
  )

  // categoryId -> ordered dish groups for that category.
  const groupsByCategory: Record<string, DishGroup[]> = categories.reduce(
    (acc, cat) => {
      acc[cat.id] = groupItems(foodItems.filter((i) => i.categoryId === cat.id))
      return acc
    },
    {} as Record<string, DishGroup[]>,
  )

  return { categories, foodItems, bestSellers, groupsByCategory }
}
