<template>
  <div class="swipe-view">
    <!-- 顶部栏 -->
    <header class="header">
      <h1 class="title">Swipe</h1>
      <div class="counter" v-if="taskStore.total > 0">
        {{ taskStore.total }}
      </div>
    </header>

    <!-- 空状态 -->
    <div v-if="taskStore.isEmpty" class="empty-state">
      <div class="empty-icon">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="7 10 12 15 17 10" />
          <line x1="12" y1="15" x2="12" y2="3" />
        </svg>
      </div>
      <p class="empty-text">暂无待筛选资源</p>
      <button class="refresh-btn" @click="refresh">
        刷新
      </button>
    </div>

    <!-- 加载状态 -->
    <div v-else-if="taskStore.loading && !taskStore.currentTask" class="loading-state">
      <div class="spinner"></div>
    </div>

    <!-- 主卡片 -->
    <div v-else class="card-area">
      <div class="card" :style="cardStyle" @touchstart="onTouchStart" @touchmove="onTouchMove" @touchend="onTouchEnd"
        @mousedown="onMouseDown">
        <!-- 决策反馈 -->
        <div class="feedback accept" :class="{ visible: decision === 'accept' }">
          下载
        </div>
        <div class="feedback reject" :class="{ visible: decision === 'reject' }">
          跳过
        </div>

        <!-- 图片区 -->
        <div class="image-area">
          <template v-if="currentImages.length > 0">
            <!-- 图片 -->
            <img :src="`/previews/${currentImages[imageIndex]}`" class="image" :style="imageStyle"
              @error="e => e.target.src = ''">

            <!-- 图片计数 -->
            <div class="image-count" v-if="currentImages.length > 1">
              {{ imageIndex + 1 }} / {{ currentImages.length }}
            </div>

            <!-- 上下切换按钮 -->
            <button class="nav-btn prev" v-if="imageIndex > 0" @click.stop="imageIndex--">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="18 15 12 9 6 15" />
              </svg>
            </button>
            <button class="nav-btn next" v-if="imageIndex < currentImages.length - 1" @click.stop="imageIndex++">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
          </template>

          <div v-else class="no-image">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <polyline points="21 15 16 10 5 21" />
            </svg>
          </div>
        </div>

        <!-- 缩略图 -->
        <div class="thumbnails" v-if="currentImages.length > 1">
          <div v-for="(img, idx) in currentImages.slice(0, 10)" :key="idx" class="thumb"
            :class="{ active: idx === imageIndex }" @click.stop="imageIndex = idx">
            <img :src="`/previews/${img}`" @error="e => e.target.style.opacity = 0">
          </div>
          <div class="thumb more" v-if="currentImages.length > 10">
            +{{ currentImages.length - 10 }}
          </div>
        </div>

        <!-- 信息区 -->
        <div class="info">
          <h2 class="info-title">{{ taskStore.currentTask?.title || '未知' }}</h2>
          <p class="info-desc" v-if="taskStore.currentTask?.description">
            {{ taskStore.currentTask.description }}
          </p>
          <div class="info-meta">
            <span>{{ formatSize(taskStore.currentTask?.file_size) }}</span>
            <span>{{ formatTime(taskStore.currentTask?.created_at) }}</span>
          </div>
        </div>
      </div>

      <!-- 操作提示 -->
      <div class="hints">
        <span>← 跳过</span>
        <span>↑↓ 切图</span>
        <span>下载 →</span>
      </div>
    </div>
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

// 图片样式
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

  if (direction.value === 'horizontal') {
    if (offsetX.value > 80) await handleConfirm()
    else if (offsetX.value < -80) await handleIgnore()
  }

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
    showToast('已添加下载')
    if (taskStore.pending.length < 5) taskStore.loadPending()
  } catch (e) {
    showToast('操作失败')
  }
}

async function handleIgnore() {
  if (!taskStore.currentTask) return
  try {
    await taskStore.ignore(taskStore.currentTask.id)
    showToast('已跳过')
    if (taskStore.pending.length < 5) taskStore.loadPending()
  } catch (e) {
    showToast('操作失败')
  }
}

function refresh() {
  taskStore.loadPending(true)
}

function formatSize(bytes) {
  if (!bytes) return '--'
  if (bytes >= 1e9) return (bytes / 1e9).toFixed(1) + ' GB'
  if (bytes >= 1e6) return (bytes / 1e6).toFixed(1) + ' MB'
  return (bytes / 1e3).toFixed(1) + ' KB'
}

function formatTime(str) {
  if (!str) return '--'
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
  background: var(--bg-primary);
}

/* 顶部栏 */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}

.title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.counter {
  background: var(--accent);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 12px;
}

/* 空状态 */
.empty-state,
.loading-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.empty-icon {
  color: var(--text-muted);
}

.empty-text {
  color: var(--text-secondary);
  font-size: 15px;
}

.refresh-btn {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  color: var(--text-primary);
  padding: 10px 24px;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
}

.refresh-btn:hover {
  background: var(--bg-tertiary);
}

.spinner {
  width: 32px;
  height: 32px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* 卡片区域 */
.card-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16px;
  padding-bottom: calc(60px + env(safe-area-inset-bottom) + 16px);
  overflow: hidden;
}

.card {
  flex: 1;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 16px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  position: relative;
  touch-action: none;
  cursor: grab;
}

.card:active {
  cursor: grabbing;
}

/* 决策反馈 */
.feedback {
  position: absolute;
  top: 20px;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  opacity: 0;
  transition: opacity 0.15s;
  z-index: 10;
}

.feedback.accept {
  right: 20px;
  background: rgba(34, 197, 94, 0.15);
  color: var(--success);
  border: 1px solid var(--success);
}

.feedback.reject {
  left: 20px;
  background: rgba(239, 68, 68, 0.15);
  color: var(--danger);
  border: 1px solid var(--danger);
}

.feedback.visible {
  opacity: 1;
}

/* 图片区 */
.image-area {
  flex: 1;
  position: relative;
  background: #0a0a0a;
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.no-image {
  color: var(--text-muted);
}

.image-count {
  position: absolute;
  top: 12px;
  right: 12px;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 4px;
}

/* 上下按钮 */
.nav-btn {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.5);
  border: none;
  color: #fff;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s;
}

.nav-btn:hover {
  background: rgba(0, 0, 0, 0.7);
}

.nav-btn.prev {
  top: 12px;
}

.nav-btn.next {
  bottom: 12px;
}

/* 缩略图 */
.thumbnails {
  display: flex;
  gap: 6px;
  padding: 12px 16px;
  background: var(--bg-tertiary);
  overflow-x: auto;
  scrollbar-width: none;
}

.thumbnails::-webkit-scrollbar {
  display: none;
}

.thumb {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  border-radius: 6px;
  overflow: hidden;
  border: 2px solid transparent;
  cursor: pointer;
  transition: border-color 0.2s;
}

.thumb.active {
  border-color: var(--accent);
}

.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumb.more {
  background: var(--bg-elevated);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  font-size: 12px;
}

/* 信息区 */
.info {
  padding: 16px;
  border-top: 1px solid var(--border);
}

.info-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
  margin-bottom: 6px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-clamp: 2;
  overflow: hidden;
}

.info-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin-bottom: 10px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-clamp: 2;
  overflow: hidden;
}

.info-meta {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: var(--text-muted);
}

/* 操作提示 */
.hints {
  display: flex;
  justify-content: space-between;
  padding: 12px 20px;
  font-size: 12px;
  color: var(--text-muted);
}
</style>
