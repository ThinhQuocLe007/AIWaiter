# UI Implementation Instructions for Customer Ordering Interface

---

## Implementation Status — DONE (Version 1)

**Date:** 2026-05-21 · **Location:** `frontends/customer_ui/`

Version 1 of the customer ordering UI is fully implemented and verified.

### What was built
- All V1 features: Welcome (tap-to-start) → Menu (category tabs + food grid + cart drawer) → Confirmation (auto-return after 5s).
- Full file structure under `src/` as specified (components/menu, components/cart, components/common, components/screens, stores, composables, types, data, router, styles).
- Pinia stores: `cart.ts`, `menu.ts` (mock data loader with loading state), `ui.ts` (cart drawer open/close).
- Mock menu: 18 items across 4 categories (Món Chính / Khai Vị / Đồ Uống / Tráng Miệng) in `data/mockMenu.ts`.
- Viewport scaling (`useViewportScale`) so the fixed 1024x600 stage scales to fit any dev window; on the kiosk scale = 1.
- Warm red/orange/cream palette, Poppins font, ≥44px touch targets, no hover-only states, rem-based spacing.

### Packages installed
`primevue`, `@primeuix/themes`, `tailwindcss`, `@tailwindcss/vite`, `@vueuse/core`, `@vueuse/motion`, `vue3-lottie`.

### Deviations from this document (intentional)
1. **Themes package:** used `@primeuix/themes/aura` instead of `@primevue/themes/aura` — the latter is deprecated (PrimeVue 4.5.x). `main.ts` imports `Aura` from `@primeuix/themes`.
2. **CartDrawer positioning:** uses `position: absolute` inside `.menu-screen` instead of `Teleport to body`. Reason: a `position: fixed` element teleported to `body` is positioned against the raw viewport and breaks alignment when the 1024x600 stage is CSS-scaled on a dev machine. Inside the stage it stays aligned at any scale (identical at scale = 1 on the kiosk).
3. **Shared formatter:** added `src/utils/format.ts` (`formatPrice`) since it is used in 5 components, instead of inlining it each time.
4. **`vue3-lottie`** is installed per the package list but not wired — Welcome/Confirmation use emoji + CSS/SVG animations (the doc allows "placeholder OK"). Swap in Lottie JSON later if desired.
5. Removed the create-vue boilerplate (HelloWorld, views/, counter store, default assets).

### Verification (all green)
- `npm run type-check` — pass · `npm run lint` (oxlint + eslint) — pass · `npm run build` — pass (235 modules).
- Automated end-to-end flow with headless Chromium at 1024x600: **9/9 steps pass, 0 JS/console errors** (welcome→menu, category filter, add-to-cart badge, drawer, +/- quantity, remove-on-zero, real-time total, confirm, auto-return + cart clear). Screenshots reviewed for visual correctness.

### Phase 2 hooks left in code
`// TODO: Phase 2` markers in `stores/menu.ts` (replace mock with API fetch), `data/mockMenu.ts`, and `screens/MenuScreen.vue` (POST order to backend + ROS2 publish on confirm).

---

## Context

This is the **customer-facing UI** for a delivery robot in a restaurant. When the robot arrives at a customer's table, the screen displays this interface so the customer can browse the menu and place an order.

The Vue 3 project has been scaffolded at `frontends/customer_ui/` using TypeScript + Vue Router + Pinia + ESLint.

## Hardware Constraints (CRITICAL)

- **Screen**: LCD 7 inch, **1024 x 600 pixels**, landscape orientation
- **Input**: Touch only (no mouse, no keyboard)
- **Viewing distance**: ~30-50cm (customer sitting at table)
- **Environment**: Restaurant lighting (varies from bright to dim)
- **Browser**: Chromium kiosk mode on Jetson Orin Nano (Ubuntu)

### Design Implications

- All touch targets minimum **44x44px** (Apple HIG standard), prefer 56x56px for primary actions
- Font sizes: body minimum 16px, prices/important text 20-24px, headings 28-40px
- No hover states (touch has no hover) - use active/pressed states instead
- High contrast colors for varied lighting conditions
- No tiny icons or thin fonts
- **Lock viewport to 1024x600** - no responsive breakpoints needed, but use the viewport scaling technique for testing on dev machine

## User Flow (Version 1)

```
[Robot arrives at table]
       ↓
[Welcome Screen] ← Tap anywhere to enter
       ↓
[Menu Screen]
  - Top: Category tabs (Appetizers, Main, Drinks, Desserts, etc.)
  - Middle: Grid of food cards
  - Top-right corner: Cart icon with badge (item count)
  - Each card has: image, name, price, [+ Add] button
       ↓
[Tap food card or +] → Item added to cart, badge updates
       ↓
[Tap cart icon] → [Cart Modal/Drawer slides in from right]
  - List of items with +/- quantity controls
  - Real-time total at bottom
  - [Confirm Order] button (large, primary)
       ↓
[Tap Confirm] → [Confirmation Screen]
  - "Order placed! Robot will deliver soon."
  - Animation (checkmark or robot icon)
  - Auto-return to welcome screen after 5 seconds
```

## Features for Version 1

✅ **Include**:
- Welcome screen with tap-to-start
- Category tabs at top of menu
- Food grid with images, name, price
- Quantity +/- controls per item in cart
- Real-time total price calculation
- Confirm order button
- Order confirmation screen

❌ **Skip for now** (Phase 2):
- Voice ordering
- Per-item notes (less spicy, no onions...)
- Payment integration
- Multi-language

## Required Packages

Install these in `frontends/customer_ui/`:

```bash
npm install primevue @primevue/themes
npm install tailwindcss @tailwindcss/vite
npm install @vueuse/core @vueuse/motion
npm install vue3-lottie
```

## Project Structure to Create

Under `frontends/customer_ui/src/`, create this structure:

```
src/
├── assets/
│   ├── images/              # Food placeholder images
│   └── animations/          # Lottie JSON files (welcome, success)
├── components/
│   ├── menu/
│   │   ├── CategoryTabs.vue
│   │   ├── FoodCard.vue
│   │   ├── FoodGrid.vue
│   │   └── CartButton.vue
│   ├── cart/
│   │   ├── CartDrawer.vue
│   │   ├── CartItem.vue
│   │   └── CartSummary.vue
│   ├── common/
│   │   ├── LoadingSkeleton.vue
│   │   └── TouchButton.vue
│   └── screens/
│       ├── WelcomeScreen.vue
│       ├── MenuScreen.vue
│       └── ConfirmationScreen.vue
├── stores/
│   ├── cart.ts              # Pinia store for cart state
│   ├── menu.ts              # Pinia store for menu data
│   └── ui.ts                # Pinia store for UI state (current screen, modals)
├── composables/
│   └── useViewportScale.ts  # Scale UI to design resolution
├── types/
│   └── index.ts             # TypeScript types (FoodItem, CartItem, Category)
├── data/
│   └── mockMenu.ts          # Mock data for development (replace with API later)
├── router/
│   └── index.ts             # Vue Router config
├── styles/
│   └── main.css             # Global styles, Tailwind imports
├── App.vue
└── main.ts
```

## Implementation Details

### 1. `main.ts` - Setup PrimeVue and global styles

```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'
import { MotionPlugin } from '@vueuse/motion'

import App from './App.vue'
import router from './router'
import './styles/main.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(MotionPlugin)
app.use(PrimeVue, {
  theme: {
    preset: Aura,
    options: {
      darkModeSelector: '.dark-mode',
    }
  }
})

app.mount('#app')
```

### 2. `styles/main.css` - Tailwind + global styles

```css
@import "tailwindcss";

:root {
  /* Brand colors - choose warm, appetizing palette */
  --color-primary: #E63946;        /* Vibrant red for CTAs */
  --color-primary-dark: #C1121F;
  --color-accent: #F77F00;         /* Orange accent */
  --color-bg: #FFF8F0;             /* Warm cream background */
  --color-surface: #FFFFFF;
  --color-text: #1D1D1D;
  --color-text-muted: #6B6B6B;
  --color-border: #E5E5E5;
  --color-success: #2A9D8F;
  
  /* Spacing scale in rem */
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-6: 1.5rem;
  --space-8: 2rem;
  --space-12: 3rem;
  
  /* Border radius */
  --radius-sm: 0.5rem;
  --radius-md: 1rem;
  --radius-lg: 1.5rem;
  --radius-full: 9999px;
}

html {
  /* Base font size for rem scaling */
  font-size: 16px;
}

body {
  margin: 0;
  padding: 0;
  width: 1024px;
  height: 600px;
  overflow: hidden;
  font-family: 'Poppins', -apple-system, sans-serif;
  background: var(--color-bg);
  color: var(--color-text);
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  -webkit-touch-callout: none;
}

#app {
  width: 100%;
  height: 100%;
  position: relative;
}

/* Minimum touch target size */
button, [role="button"], a {
  min-height: 2.75rem;
  min-width: 2.75rem;
  cursor: pointer;
  touch-action: manipulation;
}

/* Smooth active state for touch */
button:active, [role="button"]:active {
  transform: scale(0.97);
  transition: transform 0.1s ease;
}

/* Hide scrollbars but allow scrolling */
::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: 3px;
}
```

Add Poppins font in `index.html`:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet">
```

### 3. `types/index.ts` - TypeScript types

```typescript
export interface FoodItem {
  id: string
  name: string
  description: string
  price: number          // VND
  image: string         // URL or path
  categoryId: string
  available: boolean
  preparationTime?: number  // minutes
}

export interface Category {
  id: string
  name: string
  icon?: string         // emoji or icon name
  order: number
}

export interface CartItem {
  foodItem: FoodItem
  quantity: number
}

export type Screen = 'welcome' | 'menu' | 'confirmation'
```

### 4. `data/mockMenu.ts` - Mock data

Create 4-5 categories with 4-6 items each. Use placeholder images from `https://images.unsplash.com/` (food photos). Example:

```typescript
import type { Category, FoodItem } from '@/types'

export const mockCategories: Category[] = [
  { id: 'main', name: 'Món Chính', icon: '🍜', order: 1 },
  { id: 'appetizer', name: 'Khai Vị', icon: '🥗', order: 2 },
  { id: 'drink', name: 'Đồ Uống', icon: '🥤', order: 3 },
  { id: 'dessert', name: 'Tráng Miệng', icon: '🍰', order: 4 },
]

export const mockFoodItems: FoodItem[] = [
  {
    id: 'pho-bo',
    name: 'Phở Bò',
    description: 'Phở bò truyền thống với nước dùng đậm đà',
    price: 65000,
    image: 'https://images.unsplash.com/photo-1582878826629-29b7ad1cdc43?w=400',
    categoryId: 'main',
    available: true,
  },
  // ... add ~20 items total across categories
]
```

### 5. `stores/cart.ts` - Pinia cart store

```typescript
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { CartItem, FoodItem } from '@/types'

export const useCartStore = defineStore('cart', () => {
  const items = ref<CartItem[]>([])
  
  // Computed: total price in VND
  const totalPrice = computed(() =>
    items.value.reduce((sum, item) => sum + item.foodItem.price * item.quantity, 0)
  )
  
  // Computed: total quantity (for badge)
  const totalQuantity = computed(() =>
    items.value.reduce((sum, item) => sum + item.quantity, 0)
  )
  
  // Add item to cart (or increment if exists)
  function addItem(foodItem: FoodItem) {
    const existing = items.value.find(i => i.foodItem.id === foodItem.id)
    if (existing) {
      existing.quantity++
    } else {
      items.value.push({ foodItem, quantity: 1 })
    }
  }
  
  // Increment quantity
  function increment(foodId: string) {
    const item = items.value.find(i => i.foodItem.id === foodId)
    if (item) item.quantity++
  }
  
  // Decrement quantity (remove if zero)
  function decrement(foodId: string) {
    const item = items.value.find(i => i.foodItem.id === foodId)
    if (item) {
      item.quantity--
      if (item.quantity <= 0) {
        items.value = items.value.filter(i => i.foodItem.id !== foodId)
      }
    }
  }
  
  // Clear cart (after order confirmation)
  function clear() {
    items.value = []
  }
  
  return {
    items,
    totalPrice,
    totalQuantity,
    addItem,
    increment,
    decrement,
    clear,
  }
})
```

### 6. `components/screens/WelcomeScreen.vue`

Full-screen welcome with:
- Restaurant logo/name (large, centered)
- Subtitle: "Chạm để bắt đầu đặt món" (Touch to start ordering)
- Animated background (subtle gradient or floating food icons)
- Tap anywhere triggers navigation to menu
- Use `@vueuse/motion` for entry animations
- Include a Lottie animation of a friendly robot waving (placeholder OK)

```vue
<template>
  <div class="welcome-screen" @click="enterMenu">
    <!-- Background decoration -->
    <div class="bg-decoration"></div>
    
    <!-- Main content -->
    <div class="content"
      v-motion
      :initial="{ opacity: 0, y: 50 }"
      :enter="{ opacity: 1, y: 0, transition: { duration: 800 } }"
    >
      <div class="logo">🤖</div>
      <h1 class="title">Nhà Hàng XYZ</h1>
      <p class="subtitle">Chạm vào màn hình để bắt đầu</p>
      
      <!-- Pulsing tap indicator -->
      <div class="tap-indicator">
        <div class="pulse"></div>
        <span>👆</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

function enterMenu() {
  router.push('/menu')
}
</script>

<style scoped>
.welcome-screen {
  width: 1024px;
  height: 600px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #FFF8F0 0%, #FFE5D9 100%);
  position: relative;
  overflow: hidden;
}

.bg-decoration {
  position: absolute;
  inset: 0;
  background-image: 
    radial-gradient(circle at 20% 30%, rgba(230, 57, 70, 0.1) 0%, transparent 50%),
    radial-gradient(circle at 80% 70%, rgba(247, 127, 0, 0.1) 0%, transparent 50%);
}

.content {
  text-align: center;
  z-index: 1;
}

.logo {
  font-size: 8rem;
  margin-bottom: 1rem;
  animation: float 3s ease-in-out infinite;
}

.title {
  font-size: 3.5rem;
  font-weight: 800;
  color: var(--color-text);
  margin: 0 0 0.5rem 0;
  letter-spacing: -0.02em;
}

.subtitle {
  font-size: 1.5rem;
  color: var(--color-text-muted);
  margin: 0 0 3rem 0;
}

.tap-indicator {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 3rem;
}

.pulse {
  position: absolute;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: rgba(230, 57, 70, 0.3);
  animation: pulse 2s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-20px); }
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 0.6; }
  50% { transform: scale(1.5); opacity: 0; }
}
</style>
```

### 7. `components/screens/MenuScreen.vue`

Main menu screen with:
- **Top bar (height: 80px)**:
  - Left: Logo + restaurant name (small)
  - Right: Cart icon button with badge showing total item count
- **Category tabs (height: 60px)**:
  - Horizontal scrollable tabs
  - Active tab has primary color background
  - Each tab has icon + name
- **Food grid (remaining height)**:
  - 3 columns x 2 rows visible (6 cards at once)
  - Scrollable vertically if more items
  - Card size: ~310x210px each
  - Gap: 16px

Layout using CSS Grid:

```vue
<template>
  <div class="menu-screen">
    <!-- Top bar -->
    <header class="top-bar">
      <div class="brand">
        <span class="logo">🤖</span>
        <span class="name">Nhà Hàng XYZ</span>
      </div>
      <CartButton @click="openCart" />
    </header>
    
    <!-- Category tabs -->
    <CategoryTabs 
      :categories="categories"
      :active="activeCategoryId"
      @select="activeCategoryId = $event"
    />
    
    <!-- Food grid -->
    <main class="food-grid-container">
      <FoodGrid :items="filteredItems" />
    </main>
    
    <!-- Cart drawer -->
    <CartDrawer 
      :open="cartOpen"
      @close="cartOpen = false"
      @confirm="confirmOrder"
    />
  </div>
</template>
```

CSS:
```css
.menu-screen {
  width: 1024px;
  height: 600px;
  display: grid;
  grid-template-rows: 80px 60px 1fr;
  background: var(--color-bg);
}

.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1.5rem;
  background: var(--color-surface);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  z-index: 10;
}

.food-grid-container {
  padding: 1rem 1.5rem;
  overflow-y: auto;
}
```

### 8. `components/menu/FoodCard.vue`

Each food card displays:
- Image (top, 50% of card height)
- Name (bold, 18px)
- Description (small, 1 line truncated, optional)
- Bottom row: Price (left) + [+] button (right)

```vue
<template>
  <div class="food-card" @click="handleAdd">
    <div class="image-wrapper">
      <img :src="item.image" :alt="item.name" loading="lazy" />
      <div v-if="quantity > 0" class="quantity-badge">{{ quantity }}</div>
    </div>
    <div class="info">
      <h3 class="name">{{ item.name }}</h3>
      <p class="description">{{ item.description }}</p>
      <div class="footer">
        <span class="price">{{ formatPrice(item.price) }}</span>
        <button class="add-btn" :class="{ added: quantity > 0 }">
          <span v-if="quantity > 0">+</span>
          <span v-else>+ Thêm</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useCartStore } from '@/stores/cart'
import type { FoodItem } from '@/types'

const props = defineProps<{ item: FoodItem }>()
const cart = useCartStore()

const quantity = computed(() => {
  return cart.items.find(i => i.foodItem.id === props.item.id)?.quantity || 0
})

function handleAdd() {
  cart.addItem(props.item)
}

function formatPrice(price: number): string {
  return new Intl.NumberFormat('vi-VN').format(price) + 'đ'
}
</script>

<style scoped>
.food-card {
  background: var(--color-surface);
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  height: 280px;
}

.food-card:active {
  transform: scale(0.98);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}

.image-wrapper {
  position: relative;
  width: 100%;
  height: 140px;
  overflow: hidden;
}

.image-wrapper img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.quantity-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  background: var(--color-primary);
  color: white;
  font-weight: 700;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
}

.info {
  padding: 0.75rem;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.name {
  font-size: 1.125rem;
  font-weight: 700;
  margin: 0 0 0.25rem 0;
  color: var(--color-text);
}

.description {
  font-size: 0.875rem;
  color: var(--color-text-muted);
  margin: 0;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
}

.footer {
  margin-top: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.price {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--color-primary);
}

.add-btn {
  background: var(--color-primary);
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: var(--radius-full);
  font-weight: 600;
  font-size: 0.875rem;
  min-width: 44px;
  min-height: 44px;
}

.add-btn.added {
  background: var(--color-success);
  width: 44px;
  padding: 0;
  font-size: 1.5rem;
}
</style>
```

### 9. `components/cart/CartDrawer.vue`

Slide-in drawer from the right (width: 400px), darkening backdrop behind. Contains:
- Header: "Đơn hàng của bạn" + close button
- List of cart items with +/- controls
- Footer: Total price (large) + "Xác Nhận Đặt Món" button

Use Vue's `<Transition>` for slide animation:

```vue
<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="open" class="backdrop" @click="$emit('close')"></div>
    </Transition>
    <Transition name="slide">
      <aside v-if="open" class="drawer">
        <header class="drawer-header">
          <h2>Đơn hàng của bạn</h2>
          <button class="close-btn" @click="$emit('close')">✕</button>
        </header>
        
        <div v-if="cart.items.length === 0" class="empty">
          <p>Chưa có món nào trong đơn hàng</p>
        </div>
        
        <div v-else class="items">
          <CartItem 
            v-for="item in cart.items" 
            :key="item.foodItem.id"
            :item="item"
          />
        </div>
        
        <footer v-if="cart.items.length > 0" class="drawer-footer">
          <div class="total">
            <span>Tổng cộng:</span>
            <span class="total-price">{{ formatPrice(cart.totalPrice) }}</span>
          </div>
          <button class="confirm-btn" @click="$emit('confirm')">
            Xác Nhận Đặt Món
          </button>
        </footer>
      </aside>
    </Transition>
  </Teleport>
</template>
```

CSS for slide animation:
```css
.slide-enter-active, .slide-leave-active {
  transition: transform 0.3s ease;
}
.slide-enter-from, .slide-leave-to {
  transform: translateX(100%);
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

.drawer {
  position: fixed;
  top: 0;
  right: 0;
  width: 400px;
  height: 600px;
  background: var(--color-surface);
  display: flex;
  flex-direction: column;
  box-shadow: -4px 0 16px rgba(0, 0, 0, 0.15);
  z-index: 100;
}

.backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 99;
}

.confirm-btn {
  width: 100%;
  padding: 1rem;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 1.25rem;
  font-weight: 700;
  min-height: 56px;
}
```

### 10. `components/cart/CartItem.vue`

Each cart item shows:
- Small thumbnail (60x60px) on left
- Name + unit price in middle
- Quantity controls (- 1 +) on right
- Subtotal below quantity controls

```vue
<template>
  <div class="cart-item">
    <img :src="item.foodItem.image" :alt="item.foodItem.name" />
    <div class="info">
      <h4>{{ item.foodItem.name }}</h4>
      <p class="unit-price">{{ formatPrice(item.foodItem.price) }} / phần</p>
    </div>
    <div class="controls">
      <button @click="cart.decrement(item.foodItem.id)" class="qty-btn">−</button>
      <span class="qty">{{ item.quantity }}</span>
      <button @click="cart.increment(item.foodItem.id)" class="qty-btn">+</button>
    </div>
  </div>
</template>
```

Quantity buttons must be **at least 44x44px** for touch.

### 11. `components/screens/ConfirmationScreen.vue`

After order confirmation:
- Large checkmark icon or Lottie success animation
- "Đặt món thành công!" message
- "Robot sẽ giao món đến bàn của bạn"
- Order summary (collapsed)
- Auto-redirect to welcome after 5 seconds with countdown

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useCartStore } from '@/stores/cart'

const router = useRouter()
const cart = useCartStore()
const countdown = ref(5)

onMounted(() => {
  const interval = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      clearInterval(interval)
      cart.clear()
      router.push('/')
    }
  }, 1000)
})
</script>
```

### 12. `router/index.ts`

```typescript
import { createRouter, createWebHashHistory } from 'vue-router'
import WelcomeScreen from '@/components/screens/WelcomeScreen.vue'
import MenuScreen from '@/components/screens/MenuScreen.vue'
import ConfirmationScreen from '@/components/screens/ConfirmationScreen.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'welcome', component: WelcomeScreen },
    { path: '/menu', name: 'menu', component: MenuScreen },
    { path: '/confirmation', name: 'confirmation', component: ConfirmationScreen },
  ]
})

export default router
```

### 13. `App.vue`

```vue
<template>
  <div class="app-container">
    <RouterView v-slot="{ Component }">
      <Transition name="page" mode="out-in">
        <component :is="Component" />
      </Transition>
    </RouterView>
  </div>
</template>

<style>
.app-container {
  width: 1024px;
  height: 600px;
  overflow: hidden;
  position: relative;
}

.page-enter-active, .page-leave-active {
  transition: opacity 0.3s ease;
}
.page-enter-from, .page-leave-to {
  opacity: 0;
}
</style>
```

## Design Direction

**Aesthetic**: Warm, friendly, modern Asian restaurant. Not generic, not corporate.

**Color palette**:
- Primary: Warm red `#E63946` (CTAs, prices)
- Accent: Orange `#F77F00` (highlights, badges)
- Background: Cream `#FFF8F0` (warm, not stark white)
- Text: Near-black `#1D1D1D`

**Typography**: Poppins (already imported). Use weights 400/500/600/700/800.

**Personality**: Friendly emojis for categories (🍜 🥗 🥤 🍰), playful micro-interactions (button press scale, card hover lift), pulsing tap indicator on welcome screen.

**Avoid**: 
- Generic gray/blue corporate colors
- Inter or system fonts
- Flat boring cards without depth
- Tiny touch targets

## Critical Reminders

1. **All code/comments in English** as per project convention
2. **Lock viewport to 1024x600** - do not use responsive breakpoints
3. **Minimum 44px touch targets** for all interactive elements
4. **Test in Chromium** at 1024x600 resolution (DevTools device mode)
5. **No hover-only states** - everything must work with touch
6. **Use rem for spacing/fonts**, not px (px only for borders and the fixed 1024x600 dimensions)
7. **Mock data first** - all menu items from `mockMenu.ts`, will connect to API in next phase
8. **Vietnamese text in UI** is OK (it's a Vietnamese restaurant), but variable names, comments, console.logs in English

## Verification Checklist

Verified 2026-05-21 (headless Chromium @ 1024x600 + type-check/lint/build):

- [x] `npm run dev` starts without errors
- [x] Open `http://localhost:5173` in Chrome DevTools with device size 1024x600
- [x] Welcome screen displays, tap navigates to menu
- [x] Category tabs work (clicking filters food grid)
- [x] Tapping food card or [+] button adds to cart
- [x] Cart icon badge updates with item count
- [x] Tapping cart icon opens drawer
- [x] +/- buttons in cart change quantity
- [x] Removing all of an item removes it from cart
- [x] Total price updates in real-time
- [x] Confirm button navigates to confirmation screen
- [x] Confirmation screen auto-returns to welcome after 5s
- [x] All transitions are smooth (no janky animations) — verified visually via screenshots
- [x] No console errors or warnings

## Phase 2 Preparation (Not Now)

When generating code, structure it so these can be added later without major refactoring:

- Voice ordering (will add `<VoiceButton>` component, integrate Web Speech API)
- WebSocket connection to FastAPI backend (replace mock data)
- ROS2 integration via roslibjs (publish order, subscribe to robot status)
- Per-item notes (modal when tapping card)
- Animations for robot state (listening, thinking, moving)

Leave clear `// TODO: Phase 2` comments where these would integrate.

## Summary

Build a touch-optimized Vue 3 customer ordering UI for a 1024x600 robot screen. Three screens: Welcome → Menu (with category tabs + food grid + cart drawer) → Confirmation. Use Pinia for cart state, PrimeVue components where helpful, Tailwind for layout, warm restaurant aesthetic with red/orange/cream palette. All touch targets ≥44px. Mock data for now, structured for easy API integration later.
