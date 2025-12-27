<template>
  <div class="swipe-view">
    <!-- 全屏背景渐变 -->
    <div class="fullscreen-bg"></div>
    
    <!-- 顶部毛玻璃导航 -->
    <header class="top-bar">
      <div class="top-bar-content">
        <span class="logo">Swipe</span>
        <span class="counter" v-if="taskStore.total > 0">
          {{ taskStore.total }} 待筛选
        </span>
      </div>
      
      <!-- 图片进度条 -->
      <div class="image-progress" v-if="currentImages.length > 1">
        <div 
          v-for="(_, idx) in currentImages" 
          :key="idx"
          class="progress-bar"
          :class="{ active: idx === imageIndex }"
        ></div>
      </div>
    </header>
    
    <!-- 空状态 -->
    <div v-if="taskStore.isEmpty" class="empty-state">
      <div class="empty-icon">◇</div>
      <div class="empty-text">暂无待筛选资源</div>
      <button class="refresh-btn" @click="refresh">刷新</button>
    </div>
    
    <!-- 加载状态 -->
    <div v-else-if="taskStore.loading && !taskStore.currentTask" class="loading-state">
      <div class="spinner"></div>
    </div>
    
    <!-- 主内容区 -->
    <main v-else class="main-content">
      <!-- 左侧手势提示 -->
      <div class="gesture-hints">
        <div class="hint-item" :class="{ active: decision === 'reject' }">
          <span class="hint-arrow">←</span>
          <span>跳过</span>
        </div>
        <div class="hint-item right" :class="{ active: decision === 'accept' }">
          <span>下载</span>
          <span class="hint-arrow">→</span>
        </div>
      </div>
      
      <!-- 右侧缩略图 -->
      <div class="thumb-strip" v-if="currentImages.length > 1">
        <div 
          v-for="(img, idx) in currentImages.slice(0, 6)" 
          :key="idx"
          class="thumb"
          :class="{ active: idx === imageIndex }"
          @click="imageIndex = idx"
        >
          <img :src="`/previews/${img}`" @error="e => e.target.style.opacity = 0">
        </div>
        <div class="thumb more" v-if="currentImages.length > 6">
          +{{ currentImages.length - 6 }}
        </div>
      </div>
      
      <!-- 图片区域 -->
      <div 
        class="image-area"
        :style="cardStyle"
        @touchstart="onTouchStart"
        @touchmove="onTouchMove"
        @touchend="onTouchEnd"
        @mousedown="onMouseDown"
      >
        <!-- 决策反馈 -->
        <div class="decision-badge accept" :class="{ visible: decision === 'accept' }">
          下载
        </div>
        <div class="decision-badge reject" :class="{ visible: decision === 'reject' }">
          跳过
        </div>
        
        <!-- 图片显示 -->
        <img 
          v-if="currentImages.length > 0"
          :src="`/previews/${currentImages[imageIndex]}`"
          class="preview-image"
          :style="imageStyle"
          @error="handleImageError"
        >
        <div v-else class="no-image">
          <span class="no-image-icon">◇</span>
          <span>暂无预览图</span>
        </div>
      </div>
    </main>
    
    <!-- 底部信息面板 -->
    <footer class="bottom-panel" v-if="taskStore.currentTask">
      <div class="info-section">
        <h1 class="title">{{ taskStore.currentTask.title || '未知资源' }}</h1>
        <p class="desc" v-if="taskStore.currentTask.description">
          {{ taskStore.currentTask.description }}
        </p>
        <div class="meta">
          <span>📦 {{ formatSize(taskStore.currentTask.file_size) }}</span>
          <span>🕐 {{ formatTime(taskStore.currentTask.created_at) }}</span>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { showToast } from 'vant'
import { useTaskStore } from '../stores/tasks'

const taskStore = useTaskStore()

// 滑动状态
const offsetX = ref(0)
const offsetY = ref(0)
const isDragging = ref(false)
const startX = ref(0)
const startY = ref(0)
const direction = ref(null)

// 图片索引
const imageIndex = ref(0)

// 当前图片列表
const currentImages = computed(() => {
  const task = taskStore.currentTask
  if (!task) return []
  if (task.preview_images?.length) return task.preview_images
  if (task.preview_image) return [task.preview_image]
  return []
})

// 任务切换时重置
watch(() => taskStore.currentTask?.id, () => {
  imageIndex.value = 0
  offsetX.value = 0
  offsetY.value = 0
})

// 决策状态
const decision = computed(() => {
  if (offsetX.value > 60) return 'accept'
  if (offsetX.value < -60) return 'reject'
  return null
})

// 卡片样式
const cardStyle = computed(() => ({
  transform: `translateX(${offsetX.value}px) rotate(${offsetX.value * 0.015}deg)`,
  transition: isDragging.value ? 'none' : 'transform 0.3s ease'
}))

// 图片样式 (垂直滑动)
const imageStyle = computed(() => {
  if (direction.value !== 'vertical') return {}
  return {
    transform: `translateY(${offsetY.value * 0.2}px)`,
    transition: isDragging.value ? 'none' : 'transform 0.2s ease'
  }
})

// 触摸事件
function onTouchStart(e) {
  startX.value = e.touches[0].clientX
  startY.value = e.touches[0].clientY
  isDragging.value = true
  direction.value = null
}

function onTouchMove(e) {
  if (!isDragging.value) return
  const dx = e.touches[0].clientX - startX.value
  const dy = e.touches[0].clientY - startY.value
  
  if (!direction.value && (Math.abs(dx) > 8 || Math.abs(dy) > 8)) {
    direction.value = Math.abs(dx) > Math.abs(dy) ? 'horizontal' : 'vertical'
  }
  
  if (direction.value === 'horizontal') offsetX.value = dx
  if (direction.value === 'vertical') offsetY.value = dy
}

function onTouchEnd() {
  finishDrag()
}

// 鼠标事件
function onMouseDown(e) {
  startX.value = e.clientX
  startY.value = e.clientY
  isDragging.value = true
  direction.value = null
  
  const onMove = (e) => {
    const dx = e.clientX - startX.value
    const dy = e.clientY - startY.value
    
    if (!direction.value && (Math.abs(dx) > 8 || Math.abs(dy) > 8)) {
      direction.value = Math.abs(dx) > Math.abs(dy) ? 'horizontal' : 'vertical'
    }
    
    if (direction.value === 'horizontal') offsetX.value = dx
    if (direction.value === 'vertical') offsetY.value = dy
  }
  
  const onUp = () => {
    finishDrag()
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
  }
  
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

async function finishDrag() {
  isDragging.value = false
  
  // 水平滑动 - 决策
  if (direction.value === 'horizontal') {
    if (offsetX.value > 80) await handleConfirm()
    else if (offsetX.value < -80) await handleIgnore()
  }
  
  // 垂直滑动 - 切换图片
  if (direction.value === 'vertical') {
    if (offsetY.value < -40 && imageIndex.value < currentImages.value.length - 1) {
      imageIndex.value++
    } else if (offsetY.value > 40 && imageIndex.value > 0) {
      imageIndex.value--
    }
  }
  
  offsetX.value = 0
  offsetY.value = 0
  direction.value = null
}

async function handleConfirm() {
  if (!taskStore.currentTask) return
  try {
    await taskStore.confirm(taskStore.currentTask.id)
    showToast({ message: '已添加下载', icon: 'success' })
    if (taskStore.pending.length < 5) taskStore.loadPending()
  } catch (e) {
    showToast({ message: '操作失败', icon: 'fail' })
  }
}

async function handleIgnore() {
  if (!taskStore.currentTask) return
  try {
    await taskStore.ignore(taskStore.currentTask.id)
    showToast({ message: '已跳过', icon: 'clear' })
    if (taskStore.pending.length < 5) taskStore.loadPending()
  } catch (e) {
    showToast({ message: '操作失败', icon: 'fail' })
  }
}

function refresh() {
  taskStore.loadPending(true)
}

function handleImageError(e) {
  e.target.style.opacity = 0
}

function formatSize(bytes) {
  if (!bytes) return '未知'
  if (bytes >= 1e9) return (bytes / 1e9).toFixed(1) + ' GB'
  if (bytes >= 1e6) return (bytes / 1e6).toFixed(1) + ' MB'
  return (bytes / 1e3).toFixed(1) + ' KB'
}

function formatTime(str) {
  if (!str) return '未知'
  const d = Date.now() - new Date(str).getTime()
  if (d < 6e4) return '刚刚'
  if (d < 36e5) return Math.floor(d / 6e4) + ' 分钟前'
  if (d < 864e5) return Math.floor(d / 36e5) + ' 小时前'
  return Math.floor(d / 864e5) + ' 天前'
}

onMounted(() => taskStore.loadPending(true))
</script>

<style scoped>
.swipe-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

/* 全屏渐变背景 */
.fullscreen-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
  z-index: 0;
}

/* 顶部导航 */
.top-bar {
  position: relative;
  z-index: 20;
  padding: 50px 20px 16px;
  background: rgba(0, 0, 0, 0.2);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.top-bar-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.logo {
  font-size: 22px;
  font-weight: 700;
  color: #fff;
  letter-spacing: -0.5px;
}

.counter {
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(10px);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  padding: 6px 14px;
  border-radius: 20px;
}

/* 图片进度条 */
.image-progress {
  display: flex;
  gap: 4px;
  margin-top: 16px;
}

.progress-bar {
  height: 3px;
  flex: 1;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 2px;
  transition: background 0.2s;
}

.progress-bar.active {
  background: #fff;
}

/* 空状态 */
.empty-state, .loading-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  z-index: 10;
}

.empty-icon {
  font-size: 64px;
  color: rgba(255, 255, 255, 0.6);
}

.empty-text {
  color: rgba(255, 255, 255, 0.7);
  font-size: 16px;
}

.refresh-btn {
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #fff;
  padding: 10px 28px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.refresh-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(255, 255, 255, 0.2);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 主内容区 */
.main-content {
  flex: 1;
  position: relative;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

/* 手势提示 */
.gesture-hints {
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  justify-content: space-between;
  padding: 0 16px;
  pointer-events: none;
  z-index: 5;
}

.hint-item {
  display: flex;
  align-items: center;
  gap: 6px;
  color: rgba(255, 255, 255, 0.3);
  font-size: 12px;
  transition: all 0.2s;
}

.hint-item.right {
  flex-direction: row;
}

.hint-item.active {
  color: rgba(255, 255, 255, 0.9);
  transform: scale(1.1);
}

.hint-arrow {
  font-size: 18px;
}

/* 右侧缩略图 */
.thumb-strip {
  position: absolute;
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 15;
}

.thumb {
  width: 44px;
  height: 44px;
  background: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(10px);
  border-radius: 10px;
  border: 2px solid transparent;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s;
}

.thumb.active {
  border-color: #fff;
  background: rgba(255, 255, 255, 0.3);
}

.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumb.more {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 12px;
  font-weight: 500;
}

/* 图片区域 */
.image-area {
  width: 100%;
  max-width: 320px;
  aspect-ratio: 3/4;
  position: relative;
  touch-action: none;
  cursor: grab;
}

.image-area:active {
  cursor: grabbing;
}

.preview-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: 16px;
}

.no-image {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: rgba(255, 255, 255, 0.5);
  background: rgba(0, 0, 0, 0.2);
  border-radius: 16px;
}

.no-image-icon {
  font-size: 48px;
}

/* 决策反馈 */
.decision-badge {
  position: absolute;
  top: 20px;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  opacity: 0;
  transition: opacity 0.15s;
  z-index: 10;
}

.decision-badge.accept {
  right: 20px;
  background: rgba(34, 197, 94, 0.9);
  color: #fff;
}

.decision-badge.reject {
  left: 20px;
  background: rgba(239, 68, 68, 0.9);
  color: #fff;
}

.decision-badge.visible {
  opacity: 1;
}

/* 底部信息面板 */
.bottom-panel {
  position: relative;
  z-index: 20;
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(40px);
  -webkit-backdrop-filter: blur(40px);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  padding-bottom: calc(50px + env(safe-area-inset-bottom));
}

.info-section {
  padding: 20px;
}

.title {
  font-size: 18px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 6px;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-clamp: 2;
  overflow: hidden;
}

.desc {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.4;
  margin-bottom: 10px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-clamp: 2;
  overflow: hidden;
}

.meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
}
</style>
