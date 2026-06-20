<template>
  <div class="payment-screen">
    <div
      class="content"
      v-motion
      :initial="{ opacity: 0, scale: 0.8 }"
      :enter="{ opacity: 1, scale: 1, transition: { duration: 500 } }"
    >
      <h1 class="title">Thanh toán đơn hàng</h1>
      <p class="subtitle">Quét mã QR bên dưới để thanh toán</p>

      <div class="qr-card">
        <img :src="qrUrl" alt="VietQR" class="qr-image" />
      </div>

      <div class="amount-row">{{ formatPrice(amount) }}</div>

      <div class="info-box">
        <div class="info-row">
          <span class="info-label">Ngân hàng</span>
          <span class="info-value">{{ bankName }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">Số tài khoản</span>
          <span class="info-value">{{ accountNo }}</span>
        </div>
      </div>

      <TouchButton variant="primary" block @click="done">
        Đã thanh toán xong
      </TouchButton>

      <p class="countdown">Tự động quay lại sau {{ countdown }}s</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useCartStore } from '@/stores/cart'
import { formatPrice } from '@/utils/format'
import TouchButton from '@/components/common/TouchButton.vue'

const router = useRouter()
const route = useRoute()
const cart = useCartStore()
const countdown = ref(30)

const amount = ref(Number(route.query.amount) || 0)
const qrUrl = ref(
  String(route.query.qrUrl || '') ||
    `https://img.vietqr.io/image/ICB-123456789-qr_only.png?amount=${amount.value}&addInfo=AI_Waiter_Payment`,
)
const bankName = ref('VietinBank (ICB)')
const accountNo = ref('123456789')

let interval: ReturnType<typeof setInterval> | undefined

function done() {
  clearInterval(interval)
  cart.clear()
  router.push('/')
}

onMounted(() => {
  interval = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      done()
    }
  }, 1000)
})

onUnmounted(() => {
  clearInterval(interval)
})
</script>

<style scoped>
.payment-screen {
  width: 1024px;
  height: 600px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg);
}

.content {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.title {
  font-family: var(--font-display);
  font-size: 2.5rem;
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
}

.subtitle {
  font-size: 1.125rem;
  color: var(--color-text-muted);
  margin: 0;
}

.qr-card {
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 1rem;
  box-shadow: var(--shadow-md);
  display: inline-block;
}

.qr-image {
  width: 220px;
  height: 220px;
  display: block;
}

.amount-row {
  font-size: 2rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--color-text);
}

.info-box {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 0.75rem 1.5rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  min-width: 280px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.9375rem;
}

.info-label {
  color: var(--color-text-muted);
}

.info-value {
  font-weight: 700;
  color: var(--color-text);
}

.countdown {
  font-size: 0.875rem;
  color: var(--color-text-muted);
  margin: 0;
}
</style>
