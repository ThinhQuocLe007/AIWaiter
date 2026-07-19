// Find menu dishes mentioned in an AI reply, so the voice panel can show tappable
// dish cards (image + price + add-to-cart) under the message. The TTS reads only the
// reply text; prices/images live here on screen instead.
//
// A mention of a variant family ("lẩu", "ốc hương") returns the whole DishGroup, so
// the panel can show one representative image with every option's own price — images
// are per-family, prices are per-dish.
import type { DishGroup, FoodItem } from '@/types'

export type DishMatch = { kind: 'item'; item: FoodItem } | { kind: 'group'; group: DishGroup }

// Lowercase but KEEP diacritics: the agent writes proper Vietnamese and is instructed to
// use exact menu names, and stripping would collide words ("chào" greeting ↔ "cháo" dish).
function normalize(s: string): string {
  return s.toLowerCase().normalize('NFC').trim()
}

const isWordChar = (ch: string | undefined) => ch !== undefined && /[\p{L}\p{N}]/u.test(ch)

interface Candidate {
  name: string // normalized
  item?: FoodItem // exact dish mention
  group?: DishGroup // multi-option family mention
}

interface Span {
  start: number
  end: number
  candidate: Candidate
}

// Build the candidate list once per menu load: every item name, plus every group name.
// Multi-option groups match as the group itself; single-option groups fall back to
// their only item (carrying the group image if the item has none).
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
      if (candidates.some((c) => c.name === n)) continue
      if (g.items.length > 1) {
        candidates.push({ name: n, group: g })
      } else {
        candidates.push({ name: n, item: repr.image ? repr : { ...repr, image: g.image } })
      }
    }
  }
  // Longest first so "Ốc Bươu Nhồi Thịt" claims its span before "Ốc Bươu".
  return candidates.sort((a, b) => b.name.length - a.name.length)
}

// Dishes and dish families mentioned in `text`, in order of appearance. Longer names win
// overlapping spans; a matched group swallows its members' individual mentions (the group
// card already lists every option). Every mention gets a card: when the agent reads back a
// 5-dish cart, hiding the 5th would contradict the text right above it. Callers may still
// pass a `limit` for tighter surfaces.
export function matchDishes(
  text: string,
  candidates: Candidate[],
  limit = Number.POSITIVE_INFINITY,
): DishMatch[] {
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
      claimed.push({ start, end, candidate: c })
    }
  }
  claimed.sort((a, b) => a.start - b.start)

  // Items covered by a matched group: skip their standalone cards regardless of order.
  const groupedItemIds = new Set<string>()
  for (const s of claimed) {
    if (s.candidate.group) for (const it of s.candidate.group.items) groupedItemIds.add(it.id)
  }

  const seen = new Set<string>()
  const result: DishMatch[] = []
  for (const s of claimed) {
    const { item, group } = s.candidate
    if (group) {
      if (seen.has(group.id)) continue
      seen.add(group.id)
      result.push({ kind: 'group', group })
    } else if (item) {
      if (seen.has(item.id) || groupedItemIds.has(item.id)) continue
      seen.add(item.id)
      result.push({ kind: 'item', item })
    }
    if (result.length >= limit) break
  }
  return result
}
