<template>
  <div class="service-screen">
    <div
      class="content"
      v-motion
      :initial="{ opacity: 0, y: 40 }"
      :enter="{ opacity: 1, y: 0, transition: { duration: 600 } }"
    >
      <h1 class="title">Bàn {{ ui.tableId }}</h1>
      <p class="subtitle">Bạn muốn làm gì tiếp theo?</p>

      <div class="choices">
        <button class="choice" @click="orderMore">
          <i class="ti ti-tools-kitchen-2" aria-hidden="true"></i>
          <span class="choice-title">Gọi món thêm</span>
          <span class="choice-sub">Thêm món vào đơn của bàn</span>
        </button>

        <button class="choice pay" @click="goToPayment" :disabled="paying">
          <i class="ti ti-qrcode" aria-hidden="true"></i>
          <span class="choice-title">Thanh toán</span>
          <span class="choice-sub">{{ paying ? 'Đang lấy hoá đơn…' : 'Xem hoá đơn & quét mã QR' }}</span>
        </button>
      </div>

      <p v-if="error" class="error">{{ error }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUiStore } from '@/stores/ui'
import { fetchOrder, fetchTable } from '@/data/api'

const router = useRouter()
const ui = useUiStore()

const currentOrderId = ref<number | null>(null)
const paying = ref(false)
const error = ref<string | null>(null)

onMounted(async () => {
  // The router guard only reaches this screen when the table has an active order, but
  // re-read it here so "Thanh toán" can bill the correct total.
  try {
    const table = await fetchTable(ui.tableId)
    currentOrderId.value = table.current_order_id ?? null
  } catch {
    /* non-fatal: payment falls back to a zero-amount QR */
  }
})

function orderMore() {
  router.push('/menu')
}

async function goToPayment() {
  if (paying.value) return
  paying.value = true
  error.value = null
  try {
    let amount = 0
    if (currentOrderId.value) {
      amount = (await fetchOrder(currentOrderId.value)).total
    }
    const qrUrl = `https://img.vietqr.io/image/ICB-123456789-qr_only.png?amount=${amount}&addInfo=AI_Waiter_Payment`
    router.push({ name: 'payment', query: { amount: String(amount), qrUrl } })
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Không lấy được hoá đơn'
  } finally {
    paying.value = false
  }
}
</script>

<style scoped>
.service-screen {
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

.title {
  font-family: var(--font-display);
  font-size: 2.75rem;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 0.5rem;
}

.subtitle {
  font-size: 1.25rem;
  color: var(--color-text-muted);
  margin: 0 0 2.5rem;
}

.choices {
  display: flex;
  gap: 1.5rem;
  justify-content: center;
}

.choice {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  width: 280px;
  padding: 2rem 1.5rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.choice:active {
  transform: scale(0.97);
}

.choice:disabled {
  opacity: 0.6;
  cursor: progress;
}

.choice i {
  font-size: 2.75rem;
  color: var(--color-accent);
}

.choice.pay i {
  color: var(--color-success, var(--color-accent));
}

.choice-title {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--color-text);
}

.choice-sub {
  font-size: 0.95rem;
  color: var(--color-text-muted);
}

.error {
  margin-top: 1.25rem;
  color: var(--color-danger, #9b3a35);
  font-size: 0.95rem;
}
</style>
