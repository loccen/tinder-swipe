import { createRouter, createWebHistory } from 'vue-router'

const routes = [
    {
        path: '/',
        name: 'swipe',
        component: () => import('../views/SwipeView.vue'),
        meta: { title: '筛选' }
    },
    {
        path: '/dashboard',
        name: 'dashboard',
        component: () => import('../views/DashboardView.vue'),
        meta: { title: '仪表盘' }
    },
    {
        path: '/history',
        name: 'history',
        component: () => import('../views/HistoryView.vue'),
        meta: { title: '历史' }
    },
    {
        path: '/settings',
        name: 'settings',
        component: () => import('../views/SettingsView.vue'),
        meta: { title: '设置' }
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

router.beforeEach((to, from, next) => {
    document.title = to.meta.title ? `${to.meta.title} - PikPak Swipe` : 'PikPak Swipe'
    next()
})

export default router
