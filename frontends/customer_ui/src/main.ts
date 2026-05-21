import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'
import { MotionPlugin } from '@vueuse/motion'

import App from './App.vue'
import router from './router'
import './styles/main.css'
import '@tabler/icons-webfont/dist/tabler-icons.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(MotionPlugin)
app.use(PrimeVue, {
  theme: {
    preset: Aura,
    options: {
      darkModeSelector: '.dark-mode',
    },
  },
})

app.mount('#app')
