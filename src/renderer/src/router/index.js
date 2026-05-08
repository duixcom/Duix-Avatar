import { createRouter, createWebHashHistory } from 'vue-router'
import home from '@renderer/views/home/index.vue'
import account from '@renderer/views/account/index.vue'
import VideoEditView from '@renderer/views/video-edit/VideoEditView.vue'
import SettingsView from '@renderer/views/settings/index.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'root',
      redirect: '/home'
    },
    {
      path: '/home',
      name: 'home',
      component: home
    },
    {
      path: '/video/edit',
      name: 'videoEdit',
      component: VideoEditView
    },
    {
      path: '/account',
      name: 'account',
      component: account
    },
    {
      path: '/settings',
      name: 'settings',
      component: SettingsView
    },
  ]
})

export default router
