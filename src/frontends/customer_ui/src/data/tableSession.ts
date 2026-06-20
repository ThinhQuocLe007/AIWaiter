// Which table this tablet currently orders for, persisted in localStorage. One physical demo
// tablet can stand in for many tables, so the operator can switch it from the menu and have the
// choice survive reloads. Shared by the ui store (display + POST /orders) and the router guard
// (which home screen to show), so both always agree.

const TABLE_KEY = 'robodish.tableId'
const FALLBACK = Number(import.meta.env.VITE_TABLE_ID ?? 1) || 1

export function getStoredTableId(): number {
  const stored = Number(localStorage.getItem(TABLE_KEY))
  return Number.isInteger(stored) && stored >= 1 ? stored : FALLBACK
}

export function storeTableId(id: number): void {
  localStorage.setItem(TABLE_KEY, String(id))
}
