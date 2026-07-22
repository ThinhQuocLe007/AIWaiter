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

      <TouchButton variant="primary" block :disabled="paying" @click="done">
        {{ paying ? 'Đang xác nhận…' : 'Đã thanh toán xong' }}
      </TouchButton>

      <p v-if="error" class="error">{{ error }}</p>
      <p class="countdown">Tự động quay lại sau {{ countdown }}s</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useCartStore } from '@/stores/cart'
import { createPayment, verifyPayment } from '@/data/api'
import { getStoredTableId } from '@/data/tableSession'
import { formatPrice } from '@/utils/format'
import TouchButton from '@/components/common/TouchButton.vue'

const router = useRouter()
const route = useRoute()
const cart = useCartStore()
const countdown = ref(30)
const paying = ref(false)
const error = ref<string | null>(null)

const paymentId = Number(route.query.paymentId) || 0
const amount = ref(Number(route.query.amount) || 0)
const qrUrl = ref(
  String(route.query.qrUrl || '') ||
    `https://img.vietqr.io/image/ICB-123456789-qr_only.png?amount=${amount.value}&addInfo=AI_Waiter_Payment`,
)
const bankName = ref('VietinBank (ICB)')
const accountNo = ref('123456789')

let interval: ReturnType<typeof setInterval> | undefined

function goHome() {
  clearInterval(interval)
  router.push('/')
}

// Guest confirms the (mock) payment: tell the backend so it records the payment and frees the
// table (→ DA_THANH_TOAN; staff clears it from the panel). Only real money transfer is faked.
async function done() {
  if (paying.value) return
  paying.value = true
  error.value = null
  try {
    // Always settle server-side before clearing anything. We normally arrive with a paymentId in
    // the query, but the voice path (stores/voice.ts) falls back to pushing this screen bare when
    // its createPayment call failed — and a bare screen used to make this button a no-op: the guest
    // saw "paid", while the backend still had the table DANG_PHUC_VU with its robot parked there
    // forever (nothing calls cancel_table_tasks → no task.release). So open the payment now
    // (idempotent, returns the existing row) and verify that. A failure throws and is shown below,
    // with the cart left intact, rather than pretending the bill is settled.
    const id = paymentId || (await createPayment(getStoredTableId())).id
    await verifyPayment(id)
    cart.clearAll() // session settled: draft AND the "đã gửi bếp" list both go
    goHome()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Xác nhận thanh toán thất bại'
    paying.value = false
  }
}

onMounted(() => {
  // Idle timeout just returns to the home screen — it does NOT confirm payment (the guest may
  // have walked away without paying), so the table stays DANG_PHUC_VU until they actually pay.
  interval = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      goHome()
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
  gap: 0.6rem;
}

.title {
  font-family: var(--font-display);
  font-size: 1.9rem;
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
}

.subtitle {
  font-size: 1rem;
  color: var(--color-text-muted);
  margin: 0;
}

.qr-card {
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 0.75rem;
  box-shadow: var(--shadow-md);
  display: inline-block;
}

.qr-image {
  width: 176px;
  height: 176px;
  display: block;
}

.amount-row {
  font-size: 1.6rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--color-text);
}

.info-box {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 0.6rem 1.25rem;
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

.error {
  font-size: 0.875rem;
  color: var(--color-danger, #9b3a35);
  margin: 0;
}
</style>
