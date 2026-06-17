import { createRouter, createWebHashHistory } from 'vue-router'
import WelcomeScreen from '@/components/screens/WelcomeScreen.vue'
import MenuScreen from '@/components/screens/MenuScreen.vue'
import ConfirmationScreen from '@/components/screens/ConfirmationScreen.vue'
import PaymentScreen from '@/components/screens/PaymentScreen.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'welcome', component: WelcomeScreen },
    { path: '/menu', name: 'menu', component: MenuScreen },
    { path: '/confirmation', name: 'confirmation', component: ConfirmationScreen },
    { path: '/payment', name: 'payment', component: PaymentScreen },
  ],
})

export default router
