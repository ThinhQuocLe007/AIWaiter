// Format a VND amount, e.g. 65000 -> "65.000đ"
export function formatPrice(price: number): string {
  return new Intl.NumberFormat('vi-VN').format(price) + 'đ'
}
