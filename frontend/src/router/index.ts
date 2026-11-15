import {
  createRouter,
  createWebHistory,
  type RouterHistory,
} from 'vue-router'

import DashboardLayout from '@/layouts/DashboardLayout.vue'

declare module 'vue-router' {
  interface RouteMeta {
    title: string
  }
}

export function createAppRouter(
  history: RouterHistory = createWebHistory(import.meta.env.BASE_URL),
) {
  const router = createRouter({
    history,
    routes: [
      {
        path: '/',
        component: DashboardLayout,
        children: [
          {
            path: '',
            name: 'dashboard',
            component: () => import('@/views/DashboardView.vue'),
            meta: { title: 'Dashboard' },
          },
          {
            path: 'reviews',
            name: 'review-history',
            component: () => import('@/views/ReviewHistoryView.vue'),
            meta: { title: 'Review History' },
          },
          {
            path: 'reviews/:taskId(\\d+)',
            name: 'review-detail',
            component: () => import('@/views/ReviewDetailView.vue'),
            meta: { title: 'Review Detail' },
          },
          {
            path: 'insights',
            name: 'insights',
            component: () => import('@/views/InsightsView.vue'),
            meta: { title: 'Review Insights' },
          },
          {
            path: ':pathMatch(.*)*',
            name: 'not-found',
            component: () => import('@/views/NotFoundView.vue'),
            meta: { title: 'Page not found' },
          },
        ],
      },
    ],
    scrollBehavior: () => ({ top: 0 }),
  })

  router.afterEach((to) => {
    document.title = to.meta.title
      ? `${to.meta.title} · CodeSentinel`
      : 'CodeSentinel'
  })

  return router
}

const router = createAppRouter()

export default router
