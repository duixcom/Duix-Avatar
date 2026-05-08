<template>
  <div class="menu-list">
    <li v-for="(item, index) in state.menuList" :key="index" @click="handleClick(item)">
      <div class="content-body">
        <img class="icon" :src="item.active ? item.onIcon : item.offIcon" />
        <div class="text" :style="item.active ? 'color: #434AF9' : ''">
          {{ t(item.key) }}
        </div>
        <img class="active-icon" v-if="item.active" :src="activeIcon" />
      </div>
    </li>
  </div>
</template>
<script setup>
import { useRouter, useRoute } from 'vue-router'
import { reactive, watch } from 'vue'
import onIcon from '../assets/images/home/menu/onHome.svg'
import activeIcon from '../assets/images/home/menu/active.svg'
import offIcon from '../assets/images/home/menu/offHome.svg'
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
const unRoute = useRoute()
const router = useRouter()
const obj = [
  {
    key: 'common.menu.text',
    onIcon,
    offIcon,
    active: true,
    path: '/home'
  },
  /* {
      name: "账号",
      onIcon,
      offIcon,
      active: true,
      path: "/account",
    }, */
]
const state = reactive({
  menuList: obj
})
watch(
  () => unRoute.path,
  (newPath) => {
    state.menuList.forEach((el) => {
      if (newPath.includes(el.path)) {
        el.active = true
      } else {
        el.active = false
      }
    })
  }
)
const handleClick = (item) => {
  router.push(item.path)
}
</script>
<style lang="less" scoped>
.menu-list {
  width: 76px;
  background: #fff;
  position: fixed;
  left: 0;
  top: 0;
  padding-top: 60px;
  height: 100%;
  li {
    list-style: none;
    display: flex;
    height: 50px;
    cursor: pointer;
    align-items: center;
    justify-content: center;
    margin-top: 20px;
    .content-body {
      position: relative;
      .icon {
        width: 44px;
        height: 44px;
        display: block;
      }
      .active-icon {
        position: absolute;
        display: block;
        top: 8px;
        left: -16px;
      }
      .text {
        text-align: center;
        font-family: PingFang SC, PingFang SC;
        font-weight: 400;
        font-size: 12px;
        color: #9097a5;
        line-height: 14px;
        margin-top: 3px;
      }
    }
  }
}
</style>
