<template>
  <div class="swipe-view">
    <van-nav-bar 
      title="资源筛选" 
      :border="false"
    >
      <template #right>
        <span class="pending-count">{{ taskStore.total }} 待筛选</span>
      </template>
    </van-nav-bar>
    
    <div class="card-container" ref="containerRef">
      <!-- 空状态 -->
      <div v-if="taskStore.isEmpty" class="empty-state">
        <div class="emoji">🎉</div>
        <div class="message">暂无待筛选资源</div>
        <van-button 
          type="primary" 
          size="small" 
          style="margin-top: 20px"
          @click="refresh"
        >
          刷新
        </van-button>
      </div>
      
      <!-- 加载状态 -->
      <van-loading v-else-if="taskStore.loading && !taskStore.currentTask" size="40" />
      
      <!-- 卡片堆栈 -->
      <template v-else>
        <div
          v-for="(task, index) in visibleTasks"
          :key="task.id"
          class="resource-card"
          :style="getCardStyle(index)"
          @touchstart="onTouchStart"
          @touchmove="onTouchMove"
          @touchend="onTouchEnd"
          @mousedown="onMouseDown"
        >
          <!-- 确认指示器 -->
          <div class="swipe-indicator left" :style="{ opacity: confirmOpacity }">✓</div>
          <!-- 忽略指示器 -->
          <div class="swipe-indicator right" :style="{ opacity: ignoreOpacity }">✗</div>
          
          <!-- 预览图 -->
          <img 
            v-if="task.preview_image"
            :src="`/previews/${task.preview_image}`"
            class="preview-image"
            alt="预览图"
          >
          <div v-else class="preview-image placeholder">
            <van-icon name="photo" size="60" color="#ddd" />
          </div>
          
          <!-- 内容 -->
          <div class="card-content">
            <div class="card-title">{{ task.title || '未知资源' }}</div>
            <div class="card-meta">
              <span>{{ formatSize(task.file_size) }}</span>
              <span>{{ formatTime(task.created_at) }}</span>
            </div>
          </div>
        </div>
      </template>
    </div>
    
    <!-- 操作按钮 -->
    <div class="action-buttons" v-if="taskStore.currentTask">
      <button class="action-btn ignore" @click="handleIgnore">
        <van-icon name="cross" />
      </button>
      <button class="action-btn confirm" @click="handleConfirm">
        <van-icon name="success" />
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { showToast } from 'vant'
import { useTaskStore } from '../stores/tasks'

const taskStore = useTaskStore()
const containerRef = ref(null)

// 滑动状态
const offsetX = ref(0)
const isDragging = ref(false)
const startX = ref(0)

// 显示的卡片 (最多3张)
const visibleTasks = computed(() => taskStore.pending.slice(0, 3))

// 滑动指示器透明度
const confirmOpacity = computed(() => {
  if (offsetX.value > 0) return 0
  return Math.min(Math.abs(offsetX.value) / 100, 1)
})

const ignoreOpacity = computed(() => {
  if (offsetX.value < 0) return 0
  return Math.min(offsetX.value / 100, 1)
})

// 卡片样式
function getCardStyle(index) {
  if (index === 0) {
    return {
      transform: `translateX(${offsetX.value}px) rotate(${offsetX.value * 0.05}deg)`,
      zIndex: 10 - index,
      transition: isDragging.value ? 'none' : 'transform 0.3s ease'
    }
  }
  return {
    transform: `scale(${1 - index * 0.05}) translateY(${index * 10}px)`,
    zIndex: 10 - index,
    opacity: 1 - index * 0.2
  }
}

// 触摸事件
function onTouchStart(e) {
  if (e.touches.length === 1) {
    startX.value = e.touches[0].clientX
    isDragging.value = true
  }
}

function onTouchMove(e) {
  if (!isDragging.value) return
  const x = e.touches[0].clientX
  offsetX.value = x - startX.value
}

function onTouchEnd() {
  finishDrag()
}

// 鼠标事件 (PC 支持)
function onMouseDown(e) {
  startX.value = e.clientX
  isDragging.value = true
  
  const onMouseMove = (e) => {
    if (!isDragging.value) return
    offsetX.value = e.clientX - startX.value
  }
  
  const onMouseUp = () => {
    finishDrag()
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  }
  
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
}

// 完成滑动
async function finishDrag() {
  isDragging.value = false
  
  const threshold = 100
  
  if (offsetX.value < -threshold) {
    // 左滑 - 确认
    await handleConfirm()
  } else if (offsetX.value > threshold) {
    // 右滑 - 忽略
    await handleIgnore()
  }
  
  offsetX.value = 0
}

// 确认下载
async function handleConfirm() {
  const task = taskStore.currentTask
  if (!task) return
  
  try {
    await taskStore.confirm(task.id)
    showToast({ message: '已确认下载', icon: 'success' })
    checkLoadMore()
  } catch (error) {
    showToast({ message: '操作失败', icon: 'fail' })
  }
}

// 忽略任务
async function handleIgnore() {
  const task = taskStore.currentTask
  if (!task) return
  
  try {
    await taskStore.ignore(task.id)
    showToast({ message: '已忽略', icon: 'clear' })
    checkLoadMore()
  } catch (error) {
    showToast({ message: '操作失败', icon: 'fail' })
  }
}

// 检查是否需要加载更多
function checkLoadMore() {
  if (taskStore.pending.length < 5 && taskStore.hasMore) {
    taskStore.loadPending()
  }
}

// 刷新
async function refresh() {
  await taskStore.loadPending(true)
}

// 格式化文件大小
function formatSize(bytes) {
  if (!bytes) return '未知'
  if (bytes >= 1024 * 1024 * 1024) {
    return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB'
  } else if (bytes >= 1024 * 1024) {
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  } else {
    return (bytes / 1024).toFixed(1) + ' KB'
  }
}

// 格式化时间
function formatTime(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date
  
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + ' 分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + ' 小时前'
  return Math.floor(diff / 86400000) + ' 天前'
}

// 初始化
onMounted(() => {
  taskStore.loadPending(true)
})
</script>

<style scoped>
.swipe-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--background-color);
}

.pending-count {
  font-size: 14px;
  color: var(--primary-color);
}

.preview-image.placeholder {
  display: flex;
  justify-content: center;
  align-items: center;
  background: #f5f5f5;
}
</style>
