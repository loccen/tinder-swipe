<template>
  <div class="app-container">
    <router-view v-slot="{ Component }">
      <keep-alive>
        <component :is="Component" />
      </keep-alive>
    </router-view>
    
    <van-tabbar v-model="activeTab" route>
      <van-tabbar-item to="/" icon="like-o">筛选</van-tabbar-item>
      <van-tabbar-item to="/dashboard" icon="bar-chart-o">仪表盘</van-tabbar-item>
      <van-tabbar-item to="/history" icon="clock-o">历史</van-tabbar-item>
      <van-tabbar-item to="/settings" icon="setting-o">设置</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const activeTab = ref(0)
</script>

<style scoped>
.app-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.app-container > :first-child {
  flex: 1;
  overflow: hidden;
}
</style>
