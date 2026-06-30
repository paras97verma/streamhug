import { createRouter, createWebHistory } from 'vue-router';

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
    meta: { requiresLayout: true }
  },
  {
    path: '/search',
    name: 'search',
    component: () => import('@/views/HomeView.vue'),
    meta: { requiresLayout: true }
  },
  {
    path: '/movie/:id',
    name: 'media-detail',
    component: () => import('@/views/MediaView.vue'),
    meta: { requiresLayout: true }
  },
  {
    path: '/play/:id',
    name: 'player',
    component: () => import('@/views/PlayerView.vue'),
    meta: { requiresLayout: false }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { requiresLayout: true }
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) {
      return savedPosition;
    } else {
      return { top: 0 };
    }
  }
});

export default router;
