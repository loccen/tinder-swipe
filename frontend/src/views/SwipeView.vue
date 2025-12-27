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
      
      <!-- 顶部缩略图 (横向) -->
      <div class="thumb-strip-top" v-if="currentImages.length > 1">
        <div 
          v-for="(img, idx) in currentImages" 
          :key="idx"
          class="thumb-mini"
          :class="{ active: idx === imageIndex }"
          @click="imageIndex = idx"
        >
          <img :src="`/previews/${img}`" @error="handleImageError">
        </div>
      </div>
      
      <!-- 图片进度条 (替代方案，如果缩略图太多) -->
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
      <!-- 图片区域 (左右滑动切换图片) -->
      <div 
        class="image-container"
        @touchstart="onImageTouchStart"
        @touchmove="onImageTouchMove"
        @touchend="onImageTouchEnd"
        @mousedown="onImageMouseDown"
      >
        <div 
          class="image-wrapper"
          :style="imageWrapperStyle"
        >
          <img 
            v-if="currentImages.length > 0"
            :src="`/previews/${currentImages[imageIndex]}`"
            class="preview-image"
            @error="handleImageError"
          >
          <div v-else class="no-image">
            <span class="no-image-icon">◇</span>
            <span>暂无预览图</span>
          </div>
        </div>
        
        <!-- 手势提示 (切图) -->
        <div class="swipe-hint image-hint" v-if="currentImages.length > 1">
          <span>←</span>
          <span>左右滑动切换图片</span>
          <span>→</span>
        </div>
      </div>
    </main>
    
    <!-- 底部信息面板 (左右滑动代表决策) -->
    <footer 
      class="bottom-panel" 
      v-if="taskStore.currentTask"
      @touchstart="onPanelTouchStart"
      @touchmove="onPanelTouchMove"
      @touchend="onPanelTouchEnd"
      @mousedown="onPanelMouseDown"
      :style="panelStyle"
    >
      <!-- 决策反馈角标 -->
      <div class="decision-badge accept" :class="{ visible: panelDecision === 'accept' }">
        下载
      </div>
      <div class="decision-badge reject" :class="{ visible: panelDecision === 'reject' }">
        跳过
      </div>

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
      
      <!-- 决策手势提示 -->
      <div class="panel-hint">
        <span>← 左滑跳过</span>
        <span>右滑下载 →</span>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { showToast } from 'vant'
import { useTaskStore } from '../stores/tasks'

const taskStore = useTaskStore()

// --- 状态变量 ---
const imageIndex = ref(0)

// 图片滑动状态
const imageX = ref(0)
const isImageDragging = ref(false)
let imageStartX = 0

// 面板滑动状态 (决策)
const panelX = ref(0)
const isPanelDragging = ref(false)
let panelStartX = 0

// --- 计算属性 ---
const currentImages = computed(() => {
  const task = taskStore.currentTask
  if (!task) return []
  if (task.preview_images?.length) return task.preview_images
  if (task.preview_image) return [task.preview_image]
  return []
})

const imageWrapperStyle = computed(() => ({
  transform: `translateX(${imageX.value}px)`,
  transition: isImageDragging.value ? 'none' : 'transform 0.3s ease'
}))

const panelStyle = computed(() => ({
  transform: `translateX(${panelX.value}px) rotate(${panelX.value * 0.01}deg)`,
  transition: isPanelDragging.value ? 'none' : 'transform 0.3s ease'
}))

const panelDecision = computed(() => {
  if (panelX.value > 60) return 'accept'
  if (panelX.value < -60) return 'reject'
  return null
})

// --- 监听器 ---
watch(() => taskStore.currentTask?.id, () => {
  imageIndex.value = 0
  imageX.value = 0
  panelX.value = 0
})

// --- 图片手势逻辑 (左右切图) ---
function onImageTouchStart(e) {
  imageStartX = e.touches[0].clientX
  isImageDragging.value = true
}
function onImageTouchMove(e) {
  if (!isImageDragging.value) return
  imageX.value = e.touches[0].clientX - imageStartX
}
function onImageTouchEnd() {
  isImageDragging.value = false
  if (imageX.value < -60 && imageIndex.value < currentImages.value.length - 1) {
    imageIndex.value++
  } else if (imageX.value > 60 && imageIndex.value > 0) {
    imageIndex.value--
  }
  imageX.value = 0
}

// 鼠标兼容
function onImageMouseDown(e) {
  imageStartX = e.clientX
  isImageDragging.value = true
  const move = (me) => { imageX.value = me.clientX - imageStartX }
  const up = () => {
    isImageDragging.value = false
    if (imageX.value < -60 && imageIndex.value < currentImages.value.length - 1) imageIndex.value++
    else if (imageX.value > 60 && imageIndex.value > 0) imageIndex.value--
    imageX.value = 0
    window.removeEventListener('mousemove', move)
    window.removeEventListener('mouseup', up)
  }
  window.addEventListener('mousemove', move)
  window.addEventListener('mouseup', up)
}

// --- 面板手势逻辑 (左右决策) ---
function onPanelTouchStart(e) {
  panelStartX = e.touches[0].clientX
  isPanelDragging.value = true
}
function onPanelTouchMove(e) {
  if (!isPanelDragging.value) return
  panelX.value = e.touches[0].clientX - panelStartX
}
function onPanelTouchEnd() {
  finishPanelDrag()
}

function onPanelMouseDown(e) {
  panelStartX = e.clientX
  isPanelDragging.value = true
  const move = (me) => { panelX.value = me.clientX - panelStartX }
  const up = () => {
    finishPanelDrag()
    window.removeEventListener('mousemove', move)
    window.removeEventListener('mouseup', up)
  }
  window.addEventListener('mousemove', move)
  window.addEventListener('mouseup', up)
}

async function finishPanelDrag() {
  isPanelDragging.value = false
  if (panelX.value > 100) await handleConfirm()
  else if (panelX.value < -100) await handleIgnore()
  panelX.value = 0
}

// --- 操作函数 ---
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

function refresh() { taskStore.loadPending(true) }
function handleImageError(e) { e.target.style.opacity = 0 }

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

.fullscreen-bg {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
  z-index: 0;
}

/* 顶部导航与缩略图 */
.top-bar {
  position: relative;
  z-index: 20;
  padding: 50px 0 12px;
  background: rgba(0, 0, 0, 0.2);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.top-bar-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  margin-bottom: 12px;
}

.logo { font-size: 22px; font-weight: 700; color: #fff; }
.counter {
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(10px);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 20px;
}

.thumb-strip-top {
  display: flex;
  gap: 8px;
  padding: 0 20px;
  overflow-x: auto;
  scrollbar-width: none;
  margin-bottom: 10px;
}
.thumb-strip-top::-webkit-scrollbar { display: none; }

.thumb-mini {
  width: 44px; height: 44px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  border: 2px solid transparent;
  flex-shrink: 0;
  overflow: hidden;
  transition: all 0.2s;
}
.thumb-mini.active { border-color: #fff; background: rgba(255, 255, 255, 0.3); }
.thumb-mini img { width: 100%; height: 100%; object-fit: cover; }

.image-progress { display: flex; gap: 4px; padding: 0 20px; }
.progress-bar {
  height: 2px; flex: 1;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 1px;
}
.progress-bar.active { background: #fff; }

/* 内容区 */
.main-content {
  flex: 1;
  position: relative;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  padding-bottom: 40px;
}

.image-container {
  width: 90%;
  max-width: 340px;
  aspect-ratio: 1/1;
  position: relative;
  touch-action: pan-y;
  cursor: grab;
}
.image-wrapper { width: 100%; height: 100%; }
.preview-image {
  width: 100%; height: 100%;
  object-fit: contain;
  border-radius: 20px;
  background: rgba(0,0,0,0.1);
}

.swipe-hint {
  position: absolute;
  bottom: -40px;
  left: 0; right: 0;
  text-align: center;
  color: rgba(255,255,255,0.4);
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

/* 底部面板 */
.bottom-panel {
  position: absolute;
  bottom: calc(50px + env(safe-area-inset-bottom)); /* 放在导航栏上方 */
  left: 0; right: 0;
  z-index: 30;
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(40px);
  -webkit-backdrop-filter: blur(40px);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  padding: 20px;
  cursor: grab;
  touch-action: pan-y;
}

.bottom-panel:active { cursor: grabbing; }

.info-section { position: relative; }
.title { font-size: 18px; font-weight: 700; color: #fff; margin-bottom: 6px; }
.desc {
  font-size: 13px; color: rgba(255, 255, 255, 0.6);
  line-height: 1.4; margin-bottom: 12px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.meta { display: flex; gap: 16px; font-size: 12px; color: rgba(255, 255, 255, 0.4); }

.panel-hint {
  margin-top: 16px;
  display: flex;
  justify-content: space-between;
  color: rgba(255, 255, 255, 0.3);
  font-size: 11px;
}

/* 决策角标 */
.decision-badge {
  position: absolute;
  top: -40px;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  opacity: 0;
  transition: opacity 0.2s;
}
.decision-badge.accept { right: 20px; background: #22c55e; color: #fff; }
.decision-badge.reject { left: 20px; background: #ef4444; color: #fff; }
.decision-badge.visible { opacity: 1; }

/* 状态 */
.loading-state, .empty-state {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 16px; z-index: 10;
}
.spinner {
  width: 32px; height: 32px;
  border: 2px solid rgba(255,255,255,0.2);
  border-top-color: #fff; border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
