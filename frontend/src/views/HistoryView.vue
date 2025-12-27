<template>
  <div class="history-view">
    <van-nav-bar title="历史记录" :border="false" />
    
    <van-tabs v-model:active="activeTab" sticky>
      <van-tab title="已确认" name="CONFIRMED" />
      <van-tab title="下载中" name="DOWNLOADING" />
      <van-tab title="已完成" name="COMPLETE" />
      <van-tab title="已忽略" name="IGNORED" />
    </van-tabs>
    
    <div class="history-list">
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
        <van-empty v-if="!loading && tasks.length === 0" description="暂无记录" />
        
        <van-cell-group v-else inset>
          <van-cell 
            v-for="task in tasks" 
            :key="task.id"
            :title="task.title || '未知资源'"
            :label="formatTime(task.created_at)"
          >
            <template #right-icon>
              <van-tag 
                :type="getTagType(task.status)"
                size="medium"
              >
                {{ getStatusText(task.status) }}
              </van-tag>
            </template>
          </van-cell>
        </van-cell-group>
        
        <van-loading v-if="loading" style="padding: 20px; text-align: center" />
        
        <div 
          v-if="hasMore && !loading" 
          class="load-more"
          @click="loadMore"
        >
          点击加载更多
        </div>
      </van-pull-refresh>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import api from '../api'

const activeTab = ref('CONFIRMED')
const tasks = ref([])
const loading = ref(false)
const refreshing = ref(false)
const total = ref(0)

const hasMore = computed(() => tasks.value.length < total.value)

// 监听 tab 切换
watch(activeTab, () => {
  tasks.value = []
  loadTasks(true)
})

// 加载任务
async function loadTasks(refresh = false) {
  if (loading.value) return
  
  loading.value = true
  try {
    const offset = refresh ? 0 : tasks.value.length
    const result = await api.tasks.list(activeTab.value, 20, offset)
    
    if (refresh) {
      tasks.value = result.tasks
    } else {
      tasks.value.push(...result.tasks)
    }
    total.value = result.total
  } catch (error) {
    console.error('加载失败:', error)
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

// 下拉刷新
function onRefresh() {
  loadTasks(true)
}

// 加载更多
function loadMore() {
  loadTasks()
}

// 状态文本
function getStatusText(status) {
  const map = {
    PENDING: '待筛选',
    CONFIRMED: '已确认',
    DOWNLOADING: '下载中',
    COMPLETE: '已完成',
    IGNORED: '已忽略',
    ERROR: '失败'
  }
  return map[status] || status
}

// 标签类型
function getTagType(status) {
  const map = {
    PENDING: 'default',
    CONFIRMED: 'primary',
    DOWNLOADING: 'warning',
    COMPLETE: 'success',
    IGNORED: 'default',
    ERROR: 'danger'
  }
  return map[status] || 'default'
}

// 格式化时间
function formatTime(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString()
}

// 初始化
onMounted(() => {
  loadTasks(true)
})
</script>

<script>
import { computed } from 'vue'
</script>

<style scoped>
.history-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
}

:deep(.van-tabs__nav) {
  background: rgba(0, 0, 0, 0.2) !important;
  backdrop-filter: blur(20px);
}

:deep(.van-tab) {
  color: rgba(255, 255, 255, 0.6) !important;
}

:deep(.van-tab--active) {
  color: #fff !important;
}

:deep(.van-tabs__line) {
  background: #fff !important;
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  padding-bottom: calc(60px + env(safe-area-inset-bottom));
}

:deep(.van-empty__description) {
  color: rgba(255, 255, 255, 0.6) !important;
}

.load-more {
  text-align: center;
  padding: 20px;
  color: rgba(255, 255, 255, 0.8);
  cursor: pointer;
  font-size: 14px;
}

.load-more:hover {
  color: #fff;
}
</style>
