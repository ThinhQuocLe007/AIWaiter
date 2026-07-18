// Find menu dishes mentioned in an AI reply, so the voice panel can show tappable
// dish cards (image + price + add-to-cart) under the message. The TTS reads only the
// reply text; prices/images live here on screen instead.
import type { DishGroup, FoodItem } from '@/types'

// Lowercase but KEEP diacritics: the agent writes proper Vietnamese and is instructed to
// use exact menu names, and stripping would collide words ("chào" greeting ↔ "cháo" dish).
function normalize(s: string): string {
  return s.toLowerCase().normalize('NFC').trim()
}

const isWordChar = (ch: string | undefined) => ch !== undefined && /[\p{L}\p{N}]/u.test(ch)

interface Candidate {
  name: string // normalized
  item: FoodItem
}

interface Span {
  start: number
  end: number
  item: FoodItem
}

// Build the candidate list once per menu load: every item name, plus every group name
// mapped to a representative item (first of the group — its featured variant).
export function buildDishIndex(
  foodItems: FoodItem[],
  groupsByCategory: Record<string, DishGroup[]>,
): Candidate[] {
  const candidates: Candidate[] = foodItems.map((item) => ({ name: normalize(item.name), item }))
  for (const groups of Object.values(groupsByCategory)) {
    for (const g of groups) {
      const repr = g.items[0]
      if (!repr) continue
      const n = normalize(g.name)
      // Skip group names identical to an item name (already covered).
      if (!candidates.some((c) => c.name === n)) {
        // Carry the group's image onto the representative if it has none of its own.
        candidates.push({ name: n, item: repr.image ? repr : { ...repr, image: g.image } })
      }
    }
  }
  // Longest first so "Ốc Bươu Nhồi Thịt" claims its span before "Ốc Bươu".
  return candidates.sort((a, b) => b.name.length - a.name.length)
}

// Dishes mentioned in `text`, in order of appearance. Longer names win overlapping
// spans; each dish appears once; capped so the chat stays scannable.
export function matchDishes(text: string, candidates: Candidate[], limit = 4): FoodItem[] {
  const haystack = normalize(text)
  const claimed: Span[] = []
  for (const c of candidates) {
    if (c.name.length < 3) continue
    let from = 0
    for (;;) {
      const start = haystack.indexOf(c.name, from)
      if (start === -1) break
      const end = start + c.name.length
      from = end
      // Whole-word match only ("com" must not hit "combo").
      if (isWordChar(haystack[start - 1]) || isWordChar(haystack[end])) continue
      if (claimed.some((s) => start < s.end && end > s.start)) continue
      claimed.push({ start, end, item: c.item })
    }
  }
  claimed.sort((a, b) => a.start - b.start)
  const seen = new Set<string>()
  const result: FoodItem[] = []
  for (const s of claimed) {
    if (seen.has(s.item.id)) continue
    seen.add(s.item.id)
    result.push(s.item)
    if (result.length >= limit) break
  }
  return result
}
