<template>
  <div class="confirmation-screen">
    <div
      class="content"
      v-motion
      :initial="{ opacity: 0, scale: 0.8 }"
      :enter="{ opacity: 1, scale: 1, transition: { duration: 500 } }"
    >
      <div class="checkmark">
        <svg viewBox="0 0 52 52" class="checkmark-svg">
          <circle class="checkmark-circle" cx="26" cy="26" r="24" fill="none" />
          <path class="checkmark-check" fill="none" d="M14 27l8 8 16-16" />
        </svg>
      </div>

      <h1 class="title">Đặt món thành công!</h1>
      <p class="subtitle">Robot sẽ giao món đến bàn của bạn</p>

      <div v-if="itemCount > 0" class="summary">
        <span>{{ itemCount }} món</span>
        <span class="dot">•</span>
        <span class="summary-total">{{ formatPrice(totalPrice) }}</span>
      </div>

      <TouchButton variant="primary" block class="pay-btn" @click="goToPayment">
        <i class="ti ti-qrcode" aria-hidden="true"></i>
        Thanh toán ngay
      </TouchButton>

      <p class="countdown">Tự động quay lại sau {{ countdown }}s</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useCartStore } from '@/stores/cart'
import { formatPrice } from '@/utils/format'
import TouchButton from '@/components/common/TouchButton.vue'

const router = useRouter()
const cart = useCartStore()
const countdown = ref(3)

// Snapshot the order totals before the cart is cleared on redirect.
const itemCount = ref(cart.totalQuantity)
const totalPrice = ref(cart.totalPrice)

let interval: ReturnType<typeof setInterval> | undefined

function goToPayment() {
  const qrUrl = `https://img.vietqr.io/image/ICB-123456789-qr_only.png?amount=${totalPrice.value}&addInfo=AI_Waiter_Payment`
  router.push({
    name: 'payment',
    query: { amount: String(totalPrice.value), qrUrl },
  })
}

onMounted(() => {
  interval = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      clearInterval(interval)
      cart.clear()
      router.push('/')
    }
  }, 1000)
})

onUnmounted(() => {
  clearInterval(interval)
})
</script>

<style scoped>
.confirmation-screen {
  width: 1024px;
  height: 600px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #fff8f0 0%, #e9f7f4 100%);
}

.content {
  text-align: center;
}

.checkmark {
  width: 140px;
  height: 140px;
  margin: 0 auto 1.5rem;
}

.checkmark-svg {
  width: 100%;
  height: 100%;
}

.checkmark-circle {
  stroke: var(--color-success);
  stroke-width: 3;
  stroke-dasharray: 151;
  stroke-dashoffset: 151;
  animation: draw-circle 0.6s ease-out forwards;
}

.checkmark-check {
  stroke: var(--color-success);
  stroke-width: 4;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 40;
  stroke-dashoffset: 40;
  animation: draw-check 0.4s 0.5s ease-out forwards;
}

.title {
  font-size: 2.75rem;
  font-weight: 800;
  color: var(--color-text);
  margin: 0 0 0.5rem 0;
}

.subtitle {
  font-size: 1.375rem;
  color: var(--color-text-muted);
  margin: 0 0 1.5rem 0;
}

.summary {
  display: inline-flex;
  align-items: center;
  gap: 0.625rem;
  padding: 0.75rem 1.5rem;
  background: var(--color-surface);
  border-radius: var(--radius-full);
  font-size: 1.25rem;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.summary .dot {
  color: var(--color-border);
}

.summary-total {
  color: var(--color-primary);
  font-weight: 800;
}

.pay-btn {
  margin-top: 0.75rem;
  max-width: 300px;
}

.countdown {
  margin-top: 1rem;
  font-size: 1rem;
  color: var(--color-text-muted);
}

@keyframes draw-circle {
  to {
    stroke-dashoffset: 0;
  }
}

@keyframes draw-check {
  to {
    stroke-dashoffset: 0;
  }
}
</style>
