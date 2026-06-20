import { createRouter, createWebHashHistory } from 'vue-router'
import WelcomeScreen from '@/components/screens/WelcomeScreen.vue'
import ServiceChoiceScreen from '@/components/screens/ServiceChoiceScreen.vue'
import MenuScreen from '@/components/screens/MenuScreen.vue'
import ConfirmationScreen from '@/components/screens/ConfirmationScreen.vue'
import PaymentScreen from '@/components/screens/PaymentScreen.vue'
import { fetchTable } from '@/data/api'
import { getStoredTableId } from '@/data/tableSession'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'welcome', component: WelcomeScreen },
    { path: '/service', name: 'service', component: ServiceChoiceScreen },
    { path: '/menu', name: 'menu', component: MenuScreen },
    { path: '/confirmation', name: 'confirmation', component: ConfirmationScreen },
    { path: '/payment', name: 'payment', component: PaymentScreen },
  ],
})

// The home screen depends on the table's state: a freshly seated table (no order yet) gets the
// Welcome screen; a table already dining (has an active order) goes straight to the service
// choice ("order more / pay"). Decided here so it also applies after every redirect back to '/'.
router.beforeEach(async (to) => {
  if (to.name !== 'welcome') return true
  try {
    const table = await fetchTable(getStoredTableId())
    if (table.status === 'DANG_PHUC_VU' && table.current_order_id) {
      return { name: 'service' }
    }
  } catch {
    /* backend unreachable: fall through to the Welcome screen */
  }
  return true
})

export default router
