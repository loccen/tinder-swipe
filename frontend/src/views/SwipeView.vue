<template>
  <div class="swipe-view">
    <!-- 顶部状态栏 -->
    <div class="status-bar">
      <div class="logo">
        <span class="logo-icon">◈</span>
        <span class="logo-text">SWIPE</span>
      </div>
      <div class="stats">
        <div class="stat-item">
          <span class="stat-value">{{ taskStore.total }}</span>
          <span class="stat-label">PENDING</span>
        </div>
      </div>
    </div>

    <!-- 扫描线效果 -->
    <div class="scanline"></div>

    <!-- 空状态 -->
    <div v-if="taskStore.isEmpty" class="empty-state">
      <div class="empty-icon">⟐</div>
      <div class="empty-text">NO DATA STREAM</div>
      <button class="cyber-button" @click="refresh">
        <span>REFRESH</span>
      </button>
    </div>

    <!-- 加载状态 -->
    <div v-else-if="taskStore.loading && !taskStore.currentTask" class="loading-state">
      <div class="loader"></div>
      <div class="loading-text">LOADING...</div>
    </div>

    <!-- 主卡片区域 -->
    <div v-else class="card-container" ref="cardContainer">
      <div class="main-card" :style="cardTransform" @touchstart="onTouchStart" @touchmove="onTouchMove"
        @touchend="onTouchEnd" @mousedown="onMouseDown">
        <!-- 决策指示器 -->
        <div class="decision-indicator accept" :class="{ active: decision === 'accept' }">
          <span>DOWNLOAD</span>
        </div>
        <div class="decision-indicator reject" :class="{ active: decision === 'reject' }">
          <span>SKIP</span>
        </div>

        <!-- 图片区域 -->
        <div class="image-container">
          <!-- 图片数量指示器 -->
          <div class="image-counter" v-if="currentImages.length > 1">
            {{ currentImageIndex + 1 }} / {{ currentImages.length }}
          </div>

          <!-- 上下滑动提示 -->
          <div class="swipe-hint up" v-if="currentImageIndex > 0">
            <span>▲</span>
          </div>
          <div class="swipe-hint down" v-if="currentImageIndex < currentImages.length - 1">
            <span>▼</span>
          </div>

          <!-- 图片显示 -->
          <img v-if="currentImages.length > 0" :src="`/previews/${currentImages[currentImageIndex]}`"
            class="preview-image" :style="imageTransform" @error="handleImageError">
          <div v-else class="no-image">
            <span class="no-image-icon">◇</span>
            <span>NO PREVIEW</span>
          </div>

          <!-- 图片缩略图列表 -->
          <div class="thumbnail-strip" v-if="currentImages.length > 1">
            <div v-for="(img, idx) in currentImages.slice(0, 8)" :key="idx" class="thumbnail"
              :class="{ active: idx === currentImageIndex }" @click="currentImageIndex = idx">
              <img :src="`/previews/${img}`" @error="e => e.target.style.display = 'none'">
            </div>
            <div class="thumbnail more" v-if="currentImages.length > 8">
              +{{ currentImages.length - 8 }}
            </div>
          </div>
        </div>

        <!-- 信息区域 -->
        <div class="info-section">
          <div class="title">{{ taskStore.currentTask?.title || 'UNKNOWN' }}</div>
          <div class="description" v-if="taskStore.currentTask?.description">
            {{ taskStore.currentTask.description }}
          </div>
          <div class="meta">
            <span class="meta-item">
              <span class="meta-icon">◉</span>
              {{ formatSize(taskStore.currentTask?.file_size) }}
            </span>
            <span class="meta-item">
              <span class="meta-icon">◷</span>
              {{ formatTime(taskStore.currentTask?.created_at) }}
            </span>
          </div>
        </div>
      </div>

      <!-- 操作提示 -->
      <div class="gesture-hints">
        <div class="hint left">
          <span class="hint-arrow">←</span>
          <span class="hint-text">SKIP</span>
        </div>
        <div class="hint up">
          <span class="hint-arrow">↑↓</span>
          <span class="hint-text">IMAGES</span>
        </div>
        <div class="hint right">
          <span class="hint-text">DOWNLOAD</span>
          <span class="hint-arrow">→</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, onUnmounted } from 'vue'
import { showToast } from 'vant'
import { useTaskStore } from '../stores/tasks'

const taskStore = useTaskStore()
const cardContainer = ref(null)

// 滑动状态
const offsetX = ref(0)
const offsetY = ref(0)
const isDragging = ref(false)
const startX = ref(0)
const startY = ref(0)
const dragDirection = ref(null) // 'horizontal' | 'vertical'

// 当前图片索引
const currentImageIndex = ref(0)

// 当前任务的图片列表
const currentImages = computed(() => {
  const task = taskStore.currentTask
  if (!task) return []
  if (task.preview_images?.length > 0) return task.preview_images
  if (task.preview_image) return [task.preview_image]
  return []
})

// 任务切换时重置图片索引
watch(() => taskStore.currentTask?.id, () => {
  currentImageIndex.value = 0
  offsetX.value = 0
  offsetY.value = 0
})

// 决策状态
const decision = computed(() => {
  if (offsetX.value > 80) return 'accept'
  if (offsetX.value < -80) return 'reject'
  return null
})

// 卡片变换
const cardTransform = computed(() => {
  const rotate = offsetX.value * 0.02
  return {
    transform: `translateX(${offsetX.value}px) rotate(${rotate}deg)`,
    transition: isDragging.value ? 'none' : 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
  }
})

// 图片变换 (垂直滑动)
const imageTransform = computed(() => {
  if (dragDirection.value === 'vertical') {
    return {
      transform: `translateY(${offsetY.value * 0.3}px)`,
      transition: isDragging.value ? 'none' : 'transform 0.2s ease'
    }
  }
  return {}
})

// 触摸开始
function onTouchStart(e) {
  if (e.touches.length !== 1) return
  startX.value = e.touches[0].clientX
  startY.value = e.touches[0].clientY
  isDragging.value = true
  dragDirection.value = null
}

// 触摸移动
function onTouchMove(e) {
  if (!isDragging.value) return

  const x = e.touches[0].clientX
  const y = e.touches[0].clientY
  const dx = x - startX.value
  const dy = y - startY.value

  // 确定滑动方向
  if (!dragDirection.value) {
    if (Math.abs(dx) > 10 || Math.abs(dy) > 10) {
      dragDirection.value = Math.abs(dx) > Math.abs(dy) ? 'horizontal' : 'vertical'
    }
  }

  if (dragDirection.value === 'horizontal') {
    offsetX.value = dx
  } else if (dragDirection.value === 'vertical') {
    offsetY.value = dy
  }
}

// 触摸结束
function onTouchEnd() {
  finishDrag()
}

// 鼠标事件
function onMouseDown(e) {
  startX.value = e.clientX
  startY.value = e.clientY
  isDragging.value = true
  dragDirection.value = null

  const onMouseMove = (e) => {
    if (!isDragging.value) return
    const dx = e.clientX - startX.value
    const dy = e.clientY - startY.value

    if (!dragDirection.value) {
      if (Math.abs(dx) > 10 || Math.abs(dy) > 10) {
        dragDirection.value = Math.abs(dx) > Math.abs(dy) ? 'horizontal' : 'vertical'
      }
    }

    if (dragDirection.value === 'horizontal') {
      offsetX.value = dx
    } else if (dragDirection.value === 'vertical') {
      offsetY.value = dy
    }
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

  // 水平滑动 - 决策
  if (dragDirection.value === 'horizontal') {
    const threshold = 100
    if (offsetX.value > threshold) {
      await handleConfirm()
    } else if (offsetX.value < -threshold) {
      await handleIgnore()
    }
  }

  // 垂直滑动 - 切换图片
  if (dragDirection.value === 'vertical') {
    const threshold = 50
    if (offsetY.value < -threshold && currentImageIndex.value < currentImages.value.length - 1) {
      currentImageIndex.value++
    } else if (offsetY.value > threshold && currentImageIndex.value > 0) {
      currentImageIndex.value--
    }
  }

  offsetX.value = 0
  offsetY.value = 0
  dragDirection.value = null
}

// 确认下载
async function handleConfirm() {
  const task = taskStore.currentTask
  if (!task) return

  try {
    await taskStore.confirm(task.id)
    showToast({ message: 'DOWNLOADING...', icon: 'success' })
    checkLoadMore()
  } catch (error) {
    showToast({ message: 'ERROR', icon: 'fail' })
  }
}

// 忽略任务
async function handleIgnore() {
  const task = taskStore.currentTask
  if (!task) return

  try {
    await taskStore.ignore(task.id)
    showToast({ message: 'SKIPPED', icon: 'clear' })
    checkLoadMore()
  } catch (error) {
    showToast({ message: 'ERROR', icon: 'fail' })
  }
}

function checkLoadMore() {
  if (taskStore.pending.length < 5 && taskStore.hasMore) {
    taskStore.loadPending()
  }
}

function refresh() {
  taskStore.loadPending(true)
}

function handleImageError(e) {
  e.target.style.display = 'none'
}

function formatSize(bytes) {
  if (!bytes) return 'N/A'
  if (bytes >= 1073741824) return (bytes / 1073741824).toFixed(1) + ' GB'
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB'
  return (bytes / 1024).toFixed(1) + ' KB'
}

function formatTime(dateStr) {
  if (!dateStr) return 'N/A'
  const diff = Date.now() - new Date(dateStr).getTime()
  if (diff < 60000) return 'NOW'
  if (diff < 3600000) return Math.floor(diff / 60000) + 'm'
  if (diff < 86400000) return Math.floor(diff / 3600000) + 'h'
  return Math.floor(diff / 86400000) + 'd'
}

onMounted(() => {
  taskStore.loadPending(true)
})
</script>

<style scoped>
/* 全局深色主题 */
.swipe-view {
  height: 100%;
  background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 50%, #0a0a0f 100%);
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

/* 扫描线效果 */
.scanline {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: repeating-linear-gradient(0deg,
      rgba(0, 255, 255, 0.03) 0px,
      rgba(0, 255, 255, 0.03) 1px,
      transparent 1px,
      transparent 3px);
  pointer-events: none;
  z-index: 100;
}

/* 顶部状态栏 */
.status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid rgba(0, 255, 255, 0.1);
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logo-icon {
  font-size: 24px;
  color: #00ffff;
  text-shadow: 0 0 10px #00ffff, 0 0 20px #00ffff;
  animation: pulse 2s infinite;
}

.logo-text {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 4px;
  color: #fff;
  text-shadow: 0 0 10px rgba(255, 255, 255, 0.5);
}

.stats {
  display: flex;
  gap: 20px;
}

.stat-item {
  text-align: right;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #ff00ff;
  text-shadow: 0 0 10px #ff00ff;
}

.stat-label {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.5);
  letter-spacing: 2px;
}

/* 空状态 */
.empty-state,
.loading-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
}

.empty-icon {
  font-size: 80px;
  color: #00ffff;
  text-shadow: 0 0 30px #00ffff;
  animation: float 3s ease-in-out infinite;
}

.empty-text,
.loading-text {
  font-size: 14px;
  letter-spacing: 4px;
  color: rgba(255, 255, 255, 0.5);
}

.cyber-button {
  background: transparent;
  border: 1px solid #00ffff;
  color: #00ffff;
  padding: 12px 32px;
  font-family: inherit;
  font-size: 12px;
  letter-spacing: 3px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: all 0.3s;
}

.cyber-button:hover {
  background: rgba(0, 255, 255, 0.1);
  box-shadow: 0 0 20px rgba(0, 255, 255, 0.3);
}

.loader {
  width: 50px;
  height: 50px;
  border: 2px solid transparent;
  border-top-color: #00ffff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

/* 主卡片区域 */
.card-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16px;
  padding-bottom: calc(70px + env(safe-area-inset-bottom));
  overflow: hidden;
}

.main-card {
  flex: 1;
  background: linear-gradient(145deg, rgba(20, 20, 35, 0.9) 0%, rgba(10, 10, 20, 0.95) 100%);
  border: 1px solid rgba(0, 255, 255, 0.2);
  border-radius: 16px;
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow:
    0 0 30px rgba(0, 255, 255, 0.1),
    inset 0 0 60px rgba(0, 0, 0, 0.5);
  cursor: grab;
  touch-action: none;
}

.main-card:active {
  cursor: grabbing;
}

/* 决策指示器 */
.decision-indicator {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  padding: 12px 20px;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 3px;
  border-radius: 4px;
  opacity: 0;
  transition: opacity 0.2s;
  z-index: 20;
}

.decision-indicator.accept {
  right: 20px;
  background: rgba(0, 255, 100, 0.2);
  border: 2px solid #00ff64;
  color: #00ff64;
  text-shadow: 0 0 10px #00ff64;
}

.decision-indicator.reject {
  left: 20px;
  background: rgba(255, 0, 100, 0.2);
  border: 2px solid #ff0064;
  color: #ff0064;
  text-shadow: 0 0 10px #ff0064;
}

.decision-indicator.active {
  opacity: 1;
}

/* 图片区域 */
.image-container {
  flex: 1;
  position: relative;
  background: #000;
  overflow: hidden;
  min-height: 200px;
}

.image-counter {
  position: absolute;
  top: 16px;
  right: 16px;
  background: rgba(0, 0, 0, 0.7);
  border: 1px solid rgba(0, 255, 255, 0.3);
  color: #00ffff;
  padding: 6px 12px;
  font-size: 12px;
  letter-spacing: 2px;
  border-radius: 4px;
  z-index: 10;
}

.preview-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #000;
}

.no-image {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: rgba(255, 255, 255, 0.3);
}

.no-image-icon {
  font-size: 60px;
  animation: pulse 2s infinite;
}

/* 滑动提示 */
.swipe-hint {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  color: rgba(0, 255, 255, 0.5);
  font-size: 20px;
  animation: bounce 1.5s infinite;
  z-index: 10;
}

.swipe-hint.up {
  top: 16px;
}

.swipe-hint.down {
  bottom: 16px;
}

/* 缩略图条 */
.thumbnail-strip {
  position: absolute;
  bottom: 16px;
  left: 16px;
  right: 16px;
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 8px 0;
  scrollbar-width: none;
}

.thumbnail-strip::-webkit-scrollbar {
  display: none;
}

.thumbnail {
  width: 48px;
  height: 48px;
  flex-shrink: 0;
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s;
}

.thumbnail.active {
  border-color: #00ffff;
  box-shadow: 0 0 10px #00ffff;
}

.thumbnail img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumbnail.more {
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.7);
  color: #00ffff;
  font-size: 12px;
}

/* 信息区域 */
.info-section {
  padding: 20px;
  border-top: 1px solid rgba(0, 255, 255, 0.1);
  background: linear-gradient(180deg, rgba(0, 20, 30, 0.8) 0%, rgba(0, 10, 20, 0.9) 100%);
}

.title {
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  line-height: 1.4;
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-clamp: 2;
  overflow: hidden;
}

.description {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.5;
  margin-bottom: 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-clamp: 2;
  overflow: hidden;
}

.meta {
  display: flex;
  gap: 20px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: rgba(0, 255, 255, 0.7);
}

.meta-icon {
  font-size: 10px;
}

/* 手势提示 */
.gesture-hints {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  margin-top: 8px;
}

.hint {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.3);
  letter-spacing: 2px;
}

.hint-arrow {
  font-size: 16px;
  color: rgba(0, 255, 255, 0.5);
}

/* 动画 */
@keyframes pulse {

  0%,
  100% {
    opacity: 1;
  }

  50% {
    opacity: 0.5;
  }
}

@keyframes float {

  0%,
  100% {
    transform: translateY(0);
  }

  50% {
    transform: translateY(-20px);
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes bounce {

  0%,
  100% {
    transform: translateX(-50%) translateY(0);
  }

  50% {
    transform: translateX(-50%) translateY(-5px);
  }
}
</style>
