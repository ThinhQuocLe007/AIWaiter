# Hướng Dẫn Source Frontend — RoboDish Customer UI

## Tổng quan

Đây là giao diện màn hình kiosk cho khách đặt món. Ứng dụng được thiết kế cố định **1024 × 600 px** (đúng với màn hình LCD gắn trên robot), sau đó tự co/giãn theo viewport khi chạy trên máy dev hoặc trình duyệt khác kích thước.

**Tech stack:** Vue 3 (Composition API) · Vite · TypeScript · Pinia · Vue Router · Tabler Icons

---

## Luồng điều hướng (3 màn hình)

```
/ (Welcome) ──[chạm màn hình]──> /menu (Menu) ──[xác nhận đơn]──> /confirmation (Xác nhận)
                                                                          │
                                                              [sau 5 giây tự quay về /]
```

---

## Sơ đồ cấu trúc thư mục

```
src/
├── main.ts                        # Khởi động app, đăng ký plugins
├── App.vue                        # Root component, áp viewport scaling
│
├── router/index.ts                # Định nghĩa 3 routes
│
├── types/index.ts                 # Các interface dùng chung
│
├── stores/                        # Trạng thái toàn cục (Pinia)
│   ├── menu.ts                    # Danh sách món + danh mục
│   ├── cart.ts                    # Giỏ hàng
│   ├── ui.ts                      # Trạng thái UI (drawer, modal)
│   └── voice.ts                   # Trợ lý AI giọng nói
│
├── data/
│   └── menuAdapter.ts             # Chuyển menu.json → FoodItem[]
│
├── composables/
│   └── useViewportScale.ts        # Co/giãn giao diện theo màn hình
│
├── utils/
│   └── format.ts                  # formatPrice (VND)
│
├── styles/
│   └── main.css                   # CSS variables, reset, global
│
└── components/
    ├── screens/                   # 3 màn hình chính
    │   ├── WelcomeScreen.vue
    │   ├── MenuScreen.vue
    │   └── ConfirmationScreen.vue
    ├── menu/                      # Các thành phần trong màn menu
    │   ├── CategoryTabs.vue
    │   ├── FoodGrid.vue
    │   ├── FoodCard.vue
    │   ├── FoodDetailModal.vue
    │   └── CartButton.vue
    ├── cart/                      # Giỏ hàng
    │   ├── CartDrawer.vue
    │   ├── CartItem.vue
    │   └── CartSummary.vue
    ├── voice/                     # Trợ lý AI giọng nói
    │   ├── SmartBannerCard.vue
    │   └── VoicePanel.vue
    └── common/                    # Tái sử dụng chung
        ├── TouchButton.vue
        └── LoadingSkeleton.vue
```

---

## Chi tiết từng phần

### `main.ts` — Điểm khởi đầu

Đăng ký toàn bộ plugin cho app:
- **Pinia** — quản lý state
- **Vue Router** — điều hướng 3 màn hình
- **MotionPlugin** (`@vueuse/motion`) — animation vào/ra cho Welcome và Confirmation
- **PrimeVue** — component library (hiện dùng chủ yếu cho theme token)
- **Tabler Icons** (webfont) — tất cả icon `ti-*` trong app

---

### `App.vue` — Root component

- Bọc toàn bộ app trong `<div class="app-container">` cố định 1024×600
- Gọi `useViewportScale()` để tự scale xuống khi chạy trên màn hình nhỏ hơn
- Bọc `<RouterView>` trong `<Transition name="page">` — tạo hiệu ứng fade khi chuyển màn hình

---

### `router/index.ts` — Điều hướng

| Route | Màn hình | Mô tả |
|---|---|---|
| `/` | `WelcomeScreen` | Màn chào, chờ khách chạm |
| `/menu` | `MenuScreen` | Chọn và đặt món |
| `/confirmation` | `ConfirmationScreen` | Xác nhận đặt hàng thành công |

Dùng `createWebHashHistory` (`#/`) để tương thích kiosk không có server-side routing.

---

### `types/index.ts` — Các kiểu dữ liệu

| Interface | Vai trò |
|---|---|
| `FoodItem` | Thông tin 1 món: id, name, price, image, categoryId, tags... |
| `Category` | Danh mục: id, name, icon (emoji), order |
| `CartItem` | 1 dòng trong giỏ: `{ foodItem, quantity }` |
| `Screen` | Union type cho các màn hình (chủ yếu để type-safe) |

---

## Stores (Pinia)

### `stores/menu.ts` — Dữ liệu thực đơn

Quản lý toàn bộ dữ liệu thực đơn và danh mục đang được chọn.

| State / Getter | Vai trò |
|---|---|
| `categories` | Danh sách tất cả danh mục |
| `foodItems` | Danh sách tất cả món ăn |
| `activeCategoryId` | Tab danh mục đang chọn |
| `sortedCategories` | Danh mục đã sắp xếp theo `order` |
| `itemsByActiveCategory` | Món ăn lọc theo tab đang chọn + `available: true` |

| Action | Vai trò |
|---|---|
| `loadMenu()` | Load dữ liệu từ `menuAdapter.ts` (giả lập delay 400ms) |
| `setActiveCategory(id)` | Đổi tab danh mục → grid tự cập nhật |

> **Phase 2:** `loadMenu()` sẽ fetch từ FastAPI backend thay vì import tĩnh.

---

### `stores/cart.ts` — Giỏ hàng

Quản lý toàn bộ logic giỏ hàng. Mọi thao tác thêm/sửa/xóa món đều đi qua đây.

| State / Getter | Vai trò |
|---|---|
| `items` | Mảng `CartItem[]` |
| `totalPrice` | Tổng tiền (VND) |
| `totalQuantity` | Tổng số lượng (cho badge trên nút giỏ) |
| `isEmpty` | Giỏ có trống không |

| Action | Vai trò |
|---|---|
| `addItem(foodItem)` | Thêm mới, hoặc tăng số lượng nếu đã có |
| `increment(foodId)` | Tăng +1 |
| `decrement(foodId)` | Giảm -1, tự xóa khi về 0 |
| `quantityFor(foodId)` | Số lượng của 1 món cụ thể (cho stepper trên card) |
| `clear()` | Xóa toàn bộ giỏ sau khi đặt hàng xong |

---

### `stores/ui.ts` — Trạng thái giao diện

Lưu trạng thái các overlay/modal để component không cần truyền props qua nhiều tầng.

| State | Vai trò |
|---|---|
| `cartOpen` | Giỏ hàng drawer có đang mở không |
| `detailItem` | Món ăn đang được xem chi tiết (null = modal đóng) |

---

### `stores/voice.ts` — Trợ lý AI giọng nói

Quản lý toàn bộ vòng đời của cuộc hội thoại với AI.

**Các trạng thái (`aiState`):**

```
idle ──[openPanel()]──> listening ──[2.2s]──> thinking ──[1.7s]──> speaking
 ▲                           │                    │                    │
 └───────────[stop()]────────┴────────────────────┴────────────────────┘
```

| State | Hiển thị trên UI |
|---|---|
| `idle` | Nút mic "Nói tiếp" |
| `listening` | Sóng âm động + nút "Hủy" |
| `thinking` | Dấu "..." trong chat + nút "Dừng" |
| `speaking` | Bong bóng trả lời + thẻ gợi ý món + nút "Dừng" |

| Action | Vai trò |
|---|---|
| `openPanel()` | Mở panel + bắt đầu lắng nghe ngay |
| `closePanel()` | Đóng panel, reset toàn bộ state |
| `startListening()` | Bắt đầu 1 lượt hội thoại (listening → thinking → speaking) |
| `stop()` | Dừng giữa chừng, về `idle`; nếu đang listening thì hoàn tác lượt mock |
| `confirmRecommendation()` | Thêm món được gợi ý vào giỏ hàng thật |

> **Phase 2:** Thay timer mock bằng Web Speech API (STT) + LLM endpoint + TTS playback. Hàm `stop()` đã có slot để abort stream/TTS.

---

## Data Layer

### `data/menuAdapter.ts` — Bộ chuyển đổi dữ liệu

Import trực tiếp từ `assets/data/menu.json` (file dùng chung với backend Python).

```
menu.json (backend format)          FoodItem[] (frontend format)
─────────────────────────           ────────────────────────────
name          ──────────────────>   name
price: "65000"  ─[Number()]──────>  price: 65000
diet_type     ──────────────────>   dietType
taste_profile ──────────────────>   tasteProfile
tags: "a, b"  ─[split(',')]──────>  tags: ["a", "b"]
category name ─[CATEGORY_META]──>   categoryId
(không có)    ─[index + 1]──────>   id: "1", "2", ...
(không có)    ─[CATEGORY_IMAGE]─>   image: Unsplash URL
```

---

## Components

### Màn hình (screens/)

#### `WelcomeScreen.vue`
Màn hình chào toàn màn hình. Logo nổi (float animation), vòng pulse, chữ "Chạm vào màn hình". Bất kỳ chỗ nào được chạm đều `router.push('/menu')`.

#### `MenuScreen.vue`
Màn hình chính. Layout grid 2 cột (sidebar danh mục 172px + nội dung), header cố định. Điều phối toàn bộ các component menu/cart/voice bên dưới. Gọi `menu.loadMenu()` lần đầu mount.

#### `ConfirmationScreen.vue`
Màn hình xác nhận sau khi đặt. Vẽ checkmark SVG bằng CSS animation (stroke-dashoffset), hiện số món + tổng tiền, đếm ngược 5 giây rồi `cart.clear()` + quay về `/`.

---

### Thực đơn (menu/)

#### `CategoryTabs.vue`
Sidebar trái của MenuScreen. Danh sách danh mục dạng tab dọc. Tab đang active nổi bật, click → `menu.setActiveCategory()`.

#### `FoodGrid.vue`
Grid hiển thị món ăn của danh mục đang chọn. Khi `loading = true` hiện `LoadingSkeleton`. Khi có dữ liệu, render lưới `FoodCard`.

#### `FoodCard.vue`
Thẻ 1 món ăn: ảnh, tên, mô tả ngắn, giá. Hai trạng thái footer:
- **Chưa có trong giỏ:** nút "+ Thêm" (xanh lá, viền)
- **Đã có trong giỏ:** stepper `−  số  +` + badge số lượng trên ảnh

Click vào card → `ui.openDetail()` → mở `FoodDetailModal`.

#### `FoodDetailModal.vue`
Modal giữa màn hình hiện chi tiết món: ảnh lớn, mô tả đầy đủ, thành phần, hương vị, tags, nhãn mặn/chay. Footer có stepper hoặc nút "+ Thêm vào đơn". Backdrop mờ click → đóng modal.

#### `CartButton.vue`
Nút giỏ hàng ở header phải. Hiện badge số lượng khi giỏ có món.

---

### Giỏ hàng (cart/)

#### `CartDrawer.vue`
Bảng giỏ hàng trượt từ phải (hoặc từ trên xuống). Liệt kê các `CartItem`, hiện `CartSummary` ở cuối. Có nút "Xác nhận đơn" → gọi `confirmOrder()` ở MenuScreen.

#### `CartItem.vue`
1 dòng trong giỏ: ảnh nhỏ, tên, giá, stepper tăng/giảm.

#### `CartSummary.vue`
Phần tóm tắt cuối giỏ: tổng số món, tổng tiền.

---

### Trợ lý giọng nói (voice/)

#### `SmartBannerCard.vue`
Banner đỏ-cam nằm trên cùng của grid món ăn. CTA "Nói Chuyện Với AI Ngay" + icon mic nhấp nhô. Click → `voice.openPanel()`.

#### `VoicePanel.vue`
Bottom sheet trượt lên từ dưới khi Voice AI được kích hoạt. 3 vùng:

| Vùng | Nội dung |
|---|---|
| **Header** | Chấm xanh online, tên trợ lý, trạng thái, nút tắt tiếng, nút đóng (X) |
| **Chat** | Bong bóng người dùng (phải), bong bóng AI + avatar robot (trái), thẻ gợi ý món, dấu "..." khi thinking |
| **Footer** | Sóng âm + "Hủy" (listening) / "Dừng" (thinking) / "Nói tiếp" + "Dừng" (speaking) / "Nói tiếp" (idle) |

---

### Dùng chung (common/)

#### `TouchButton.vue`
Nút có variant (`primary`, `secondary`, `ghost`), prop `block` (full-width). Được dùng trong `FoodDetailModal` cho nút "Thêm vào đơn".

#### `LoadingSkeleton.vue`
Shimmer placeholder hiện trong `FoodGrid` khi đang load dữ liệu menu.

---

## Composables & Utils

### `composables/useViewportScale.ts`
Tính `Math.min(viewport.width / 1024, viewport.height / 600)`, gán vào CSS variable `--app-scale`. `App.vue` dùng biến này cho `transform: scale(...)`. Kiosk thật (1024×600) scale = 1, máy dev scale tự fit.

### `utils/format.ts`
Hàm `formatPrice(price: number)` — dùng `Intl.NumberFormat('vi-VN')` để in `65.000đ`.

### `styles/main.css`
CSS variables toàn cục (`--color-primary`, `--color-bg`, `--radius-md`...), CSS reset, và style chung cho `body`, `button`, scrollbar.

---

## Sơ đồ tương tác giữa các phần

```
MenuScreen
│
├── CategoryTabs ──[select]──> menu.setActiveCategory()
│                                      │
├── FoodGrid ──[items]── menu.itemsByActiveCategory
│      └── FoodCard ──[addItem]──> cart.addItem()
│                  └──[click]───> ui.openDetail()
│
├── FoodDetailModal ──[item]── ui.detailItem
│                   └──[add]──> cart.addItem()
│
├── CartButton ──[badge]── cart.totalQuantity
│            └──[click]──> ui.openCart()
│
├── CartDrawer ──[items]── cart.items
│             └──[confirm]──> router.push('/confirmation')
│
├── SmartBannerCard ──[click]──> voice.openPanel()
│
└── VoicePanel ──[state]── voice.aiState / messages / recommendedItem
               └──[Thêm nhanh]──> voice.confirmRecommendation()
                                         └──> cart.addItem()
```

---

## Roadmap Phase 2 (chưa làm)

| Việc cần làm | File liên quan |
|---|---|
| Fetch menu từ FastAPI backend | `stores/menu.ts` → `loadMenu()` |
| POST đơn hàng + publish ROS2 | `screens/MenuScreen.vue` → `confirmOrder()` |
| Tích hợp Web Speech API (STT) | `stores/voice.ts` → `startListening()` |
| Tích hợp LLM endpoint thật | `stores/voice.ts` → replace mock timers |
| TTS playback + abort | `stores/voice.ts` → `stop()` |
| Thêm field `image` vào menu.json | `data/menuAdapter.ts` |
