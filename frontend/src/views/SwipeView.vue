<template>
  <div class="swipe-view">
    <van-nav-bar title="资源筛选" :border="false">
      <template #right>
        <span class="pending-count">{{ taskStore.total }} 待筛选</span>
      </template>
    </van-nav-bar>

    <div class="swipe-container">
      <!-- 空状态 -->
      <div v-if="taskStore.isEmpty" class="empty-state">
        <div class="emoji">🎉</div>
        <div class="message">暂无待筛选资源</div>
        <van-button type="primary" size="small" style="margin-top: 20px" @click="refresh">
          刷新
        </van-button>
      </div>

      <!-- 加载状态 -->
      <van-loading v-else-if="taskStore.loading && !taskStore.currentTask" size="40" />

      <!-- 卡片区域 -->
      <template v-else>
        <div class="card-stack">
          <div v-for="(task, index) in visibleTasks" :key="task.id" class="swipe-card"
            :class="{ 'is-current': index === 0 }" :style="getCardStyle(index)" @touchstart="onTouchStart"
            @touchmove="onTouchMove" @touchend="onTouchEnd" @mousedown="onMouseDown">
            <!-- 滑动指示器 -->
            <div class="swipe-indicator confirm" :style="{ opacity: index === 0 ? confirmOpacity : 0 }">
              <van-icon name="success" />
            </div>
            <div class="swipe-indicator ignore" :style="{ opacity: index === 0 ? ignoreOpacity : 0 }">
              <van-icon name="cross" />
            </div>

            <!-- 图片轮播区域 -->
            <div class="image-section">
              <template v-if="getImages(task).length > 0">
                <!-- 图片指示器 (探探风格) -->
                <div class="image-indicators" v-if="getImages(task).length > 1">
                  <div v-for="(img, imgIndex) in getImages(task)" :key="imgIndex" class="indicator-bar"
                    :class="{ active: imgIndex === currentImageIndex }"></div>
                </div>

                <!-- 左右点击切换区域 -->
                <div class="image-tap-left" @click.stop="prevImage"></div>
                <div class="image-tap-right" @click.stop="nextImage"></div>

                <!-- 图片显示 -->
                <img :src="`/previews/${getImages(task)[currentImageIndex] || getImages(task)[0]}`"
                  class="preview-image" alt="预览图" @error="handleImageError">
              </template>
              <div v-else class="preview-image placeholder">
                <van-icon name="photo" size="60" color="#ddd" />
              </div>
            </div>

            <!-- 内容区域 -->
            <div class="card-content">
              <div class="card-title">{{ task.title || '未知资源' }}</div>
              <div class="card-description" v-if="task.description">
                {{ task.description }}
              </div>
              <div class="card-meta">
                <span>{{ formatSize(task.file_size) }}</span>
                <span>{{ formatTime(task.created_at) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 操作按钮 (卡片外部) -->
        <div class="action-buttons" v-if="taskStore.currentTask">
          <button class="action-btn ignore" @click="handleIgnore">
            <van-icon name="cross" size="28" />
          </button>
          <button class="action-btn confirm" @click="handleConfirm">
            <van-icon name="success" size="28" />
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { showToast } from 'vant'
import { useTaskStore } from '../stores/tasks'

const taskStore = useTaskStore()

// 滑动状态
const offsetX = ref(0)
const isDragging = ref(false)
const startX = ref(0)

// 当前图片索引
const currentImageIndex = ref(0)

// 显示的卡片 (最多3张)
const visibleTasks = computed(() => taskStore.pending.slice(0, 3))

// 当任务切换时，重置图片索引
watch(() => taskStore.currentTask?.id, () => {
  currentImageIndex.value = 0
})

// 获取任务的图片列表
function getImages(task) {
  if (task.preview_images && task.preview_images.length > 0) {
    return task.preview_images
  }
  if (task.preview_image) {
    return [task.preview_image]
  }
  return []
}

// 切换上一张图片
function prevImage() {
  const images = getImages(taskStore.currentTask)
  if (images.length > 1 && currentImageIndex.value > 0) {
    currentImageIndex.value--
  }
}

// 切换下一张图片
function nextImage() {
  const images = getImages(taskStore.currentTask)
  if (images.length > 1 && currentImageIndex.value < images.length - 1) {
    currentImageIndex.value++
  }
}

// 图片加载失败处理
function handleImageError(e) {
  e.target.style.display = 'none'
}

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
      transform: `translateX(${offsetX.value}px) rotate(${offsetX.value * 0.03}deg)`,
      zIndex: 10 - index,
      transition: isDragging.value ? 'none' : 'transform 0.3s ease'
    }
  }
  return {
    transform: `scale(${1 - index * 0.05}) translateY(${index * 8}px)`,
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
    await handleConfirm()
  } else if (offsetX.value > threshold) {
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
    currentImageIndex.value = 0
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
    currentImageIndex.value = 0
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
  background: linear-gradient(180deg, #f5f7fa 0%, #e8ecf3 100%);
}

.pending-count {
  font-size: 14px;
  color: var(--primary-color);
  font-weight: 500;
}

.swipe-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16px;
  padding-bottom: calc(60px + env(safe-area-inset-bottom) + 16px);
  /* TabBar 高度 + 安全距离 */
  overflow: hidden;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.empty-state .emoji {
  font-size: 80px;
  margin-bottom: 20px;
}

.empty-state .message {
  font-size: 16px;
  color: #969799;
}

/* 卡片堆叠 */
.card-stack {
  flex: 1;
  position: relative;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding-top: 20px;
}

.swipe-card {
  position: absolute;
  width: 100%;
  max-width: 360px;
  background: #fff;
  border-radius: 20px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
  overflow: hidden;
  touch-action: none;
  user-select: none;
  cursor: grab;
}

.swipe-card:active {
  cursor: grabbing;
}

.swipe-card.is-current {
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
}

/* 滑动指示器 */
.swipe-indicator {
  position: absolute;
  top: 20px;
  width: 60px;
  height: 60px;
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 32px;
  color: white;
  z-index: 20;
  pointer-events: none;
  transition: opacity 0.1s;
}

.swipe-indicator.confirm {
  left: 20px;
  background: linear-gradient(135deg, #07c160 0%, #00a854 100%);
  box-shadow: 0 4px 15px rgba(7, 193, 96, 0.4);
}

.swipe-indicator.ignore {
  right: 20px;
  background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%);
  box-shadow: 0 4px 15px rgba(238, 10, 36, 0.4);
}

/* 图片区域 */
.image-section {
  position: relative;
  width: 100%;
  height: 320px;
  background: #f5f5f5;
}

.preview-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.preview-image.placeholder {
  display: flex;
  justify-content: center;
  align-items: center;
}

/* 探探风格图片指示器 */
.image-indicators {
  position: absolute;
  top: 8px;
  left: 8px;
  right: 8px;
  display: flex;
  gap: 4px;
  z-index: 10;
}

.indicator-bar {
  flex: 1;
  height: 3px;
  background: rgba(255, 255, 255, 0.4);
  border-radius: 2px;
  transition: background 0.2s;
}

.indicator-bar.active {
  background: rgba(255, 255, 255, 0.95);
}

/* 左右点击区域 */
.image-tap-left,
.image-tap-right {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 40%;
  z-index: 5;
}

.image-tap-left {
  left: 0;
  cursor: w-resize;
}

.image-tap-right {
  right: 0;
  cursor: e-resize;
}

/* 内容区域 */
.card-content {
  padding: 16px 20px 20px;
}

.card-title {
  font-size: 18px;
  font-weight: 600;
  line-height: 1.4;
  color: #1a1a1a;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-description {
  margin-top: 8px;
  font-size: 14px;
  color: #666;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  color: #999;
  font-size: 13px;
}

/* 操作按钮 */
.action-buttons {
  display: flex;
  justify-content: center;
  gap: 50px;
  padding: 20px 0;
  margin-top: auto;
}

.action-btn {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  border: none;
  display: flex;
  justify-content: center;
  align-items: center;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.action-btn:active {
  transform: scale(0.92);
}

.action-btn.confirm {
  background: linear-gradient(135deg, #07c160 0%, #00a854 100%);
  color: white;
  box-shadow: 0 6px 20px rgba(7, 193, 96, 0.4);
}

.action-btn.ignore {
  background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%);
  color: white;
  box-shadow: 0 6px 20px rgba(238, 10, 36, 0.4);
}
</style>
