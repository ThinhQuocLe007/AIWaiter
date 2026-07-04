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
      <p class="subtitle">Robot sẽ giao món đến <strong>Bàn {{ ui.tableId }}</strong></p>

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
import { useUiStore } from '@/stores/ui'
import { createPayment } from '@/data/api'
import { formatPrice } from '@/utils/format'
import TouchButton from '@/components/common/TouchButton.vue'

const router = useRouter()
const cart = useCartStore()
const ui = useUiStore()
const countdown = ref(10)

// The just-confirmed batch (markOrdered moved the draft into "đã gửi bếp" and snapshotted it).
const itemCount = ref(cart.lastOrder?.count ?? cart.totalQuantity)
const totalPrice = ref(cart.lastOrder?.total ?? cart.totalPrice)

let interval: ReturnType<typeof setInterval> | undefined
const paying = ref(false)

// Open the session's gộp payment (every order of this seating, summed server-side) — same flow
// as the cart card's "Thanh toán" button, so the bill always covers voice + manual orders.
async function goToPayment() {
  if (paying.value) return
  paying.value = true
  try {
    const payment = await createPayment(ui.tableId)
    router.push({
      name: 'payment',
      query: {
        amount: String(payment.amount),
        qrUrl: payment.qr_url ?? '',
        paymentId: String(payment.id),
      },
    })
  } catch {
    // Fallback: static QR with this batch's total (no payment id → verify is skipped).
    const qrUrl = `https://img.vietqr.io/image/ICB-123456789-qr_only.png?amount=${totalPrice.value}&addInfo=AI_Waiter_Payment`
    router.push({ name: 'payment', query: { amount: String(totalPrice.value), qrUrl } })
  } finally {
    paying.value = false
  }
}

onMounted(() => {
  interval = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      clearInterval(interval)
      router.push('/') // '/' resolves to the service-choice screen while the table is dining
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
  background: var(--color-bg);
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
  font-family: var(--font-display);
  font-size: 2.75rem;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 0.5rem 0;
}

.subtitle {
  font-size: 1.25rem;
  color: var(--color-text-muted);
  margin: 0 0 1.5rem 0;
}

.summary {
  display: inline-flex;
  align-items: center;
  gap: 0.625rem;
  padding: 0.75rem 1.5rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  font-size: 1.25rem;
  font-weight: 500;
  box-shadow: var(--shadow-sm);
}

.summary .dot {
  color: var(--color-accent);
}

.summary-total {
  color: var(--color-text);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
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
