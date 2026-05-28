import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import DigestDetail from '../views/DigestDetail.vue'
import Settings from '../views/Settings.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home,
    meta: { title: 'Today\'s Digest' }
  },
  {
    path: '/digest/:date',
    name: 'DigestDetail',
    component: DigestDetail,
    meta: { title: 'Digest Detail' },
    props: true
  },
  {
    path: '/settings',
    name: 'Settings',
    component: Settings,
    meta: { title: 'Settings' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} | WYCA` : 'WYCA'
})

export default router
