import rawItems from '../../../../../assets/data/menu.json'
import type { Category, FoodItem } from '@/types'

interface RawMenuItem {
  name: string
  description: string
  price: string
  diet_type: string
  category: string
  ingredients: string
  taste_profile: string
  tags: string
}

// Maps the category display name from menu.json to its frontend metadata.
const CATEGORY_META: Record<string, { id: string; icon: string; order: number }> = {
  'Món Lẩu':          { id: 'lau',          icon: '🍲', order: 1  },
  'Món Lẩu Chay':     { id: 'lau-chay',     icon: '🫕', order: 2  },
  'Món Nướng':        { id: 'nuong',        icon: '🍖', order: 3  },
  'Món Chính Mặn':    { id: 'chinh-man',    icon: '🍜', order: 4  },
  'Món Chính Chay':   { id: 'chinh-chay',   icon: '🌿', order: 5  },
  'Món Khai Vị':      { id: 'khai-vi',      icon: '🥗', order: 6  },
  'Món Khai Vị Chay': { id: 'khai-vi-chay', icon: '🥦', order: 7  },
  'Món Kho':          { id: 'kho',          icon: '🥘', order: 8  },
  'Món Hải Sản':      { id: 'hai-san',      icon: '🦐', order: 9  },
  'Món Nước':         { id: 'nuoc',         icon: '🍜', order: 10 },
  'Cơm & Mì':         { id: 'com-mi',       icon: '🍚', order: 11 },
  'Món Rau':          { id: 'rau',          icon: '🥬', order: 12 },
  'Canh & Sup':       { id: 'canh-sup',     icon: '🍵', order: 13 },
  'Món Canh Chay':    { id: 'canh-chay',    icon: '🥣', order: 14 },
  'Món Đặc Sản':      { id: 'dac-san',      icon: '🌟', order: 15 },
  'Tráng Miệng':      { id: 'trang-mieng',  icon: '🍮', order: 16 },
  'Đồ Uống':          { id: 'do-uong',      icon: '🥤', order: 17 },
}

// One representative Unsplash image per category; items share their category image.
// TODO: add a per-item `image` field to menu.json when the backend is ready.
const CATEGORY_IMAGE: Record<string, string> = {
  'lau':          'https://images.unsplash.com/photo-1569562211093-4ed0d0758f12?w=400',
  'lau-chay':     'https://images.unsplash.com/photo-1547592180-85f173990554?w=400',
  'nuong':        'https://images.unsplash.com/photo-1544025162-d76694265947?w=400',
  'chinh-man':    'https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=400',
  'chinh-chay':   'https://images.unsplash.com/photo-1606923829579-0cb981a83e2e?w=400',
  'khai-vi':      'https://images.unsplash.com/photo-1625938145312-c69b6cd60c1f?w=400',
  'khai-vi-chay': 'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=400',
  'kho':          'https://images.unsplash.com/photo-1467003909585-2f8a72700288?w=400',
  'hai-san':      'https://images.unsplash.com/photo-1565557623262-b51c2513a641?w=400',
  'nuoc':         'https://images.unsplash.com/photo-1582878826629-29b7ad1cdc43?w=400',
  'com-mi':       'https://images.unsplash.com/photo-1603133872878-684f208fb84b?w=400',
  'rau':          'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=400',
  'canh-sup':     'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=400',
  'canh-chay':    'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=400',
  'dac-san':      'https://images.unsplash.com/photo-1553978297-833d24758dbe?w=400',
  'trang-mieng':  'https://images.unsplash.com/photo-1488477181946-6428a0291777?w=400',
  'do-uong':      'https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=400',
}

const FALLBACK_IMAGE = 'https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=400'

function toFoodItem(raw: RawMenuItem, index: number): FoodItem {
  const meta = CATEGORY_META[raw.category]
  const categoryId = meta?.id ?? raw.category.toLowerCase().replace(/\s+/g, '-')
  return {
    id: String(index + 1),
    name: raw.name,
    description: raw.description,
    price: Number(raw.price),
    image: CATEGORY_IMAGE[categoryId] ?? FALLBACK_IMAGE,
    categoryId,
    available: true,
    ingredients: raw.ingredients,
    tasteProfile: raw.taste_profile,
    tags: raw.tags.split(',').map((t) => t.trim()),
    dietType: raw.diet_type,
  }
}

export const adaptedCategories: Category[] = Object.entries(CATEGORY_META)
  .filter(([name]) => (rawItems as RawMenuItem[]).some((r) => r.category === name))
  .map(([name, meta]) => ({ id: meta.id, name, icon: meta.icon, order: meta.order }))

export const adaptedFoodItems: FoodItem[] = (rawItems as RawMenuItem[]).map(toFoodItem)
