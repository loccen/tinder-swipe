<template>
  <div class="dashboard-view">
    <van-nav-bar title="仪表盘" :border="false" />
    
    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <div class="dashboard">
        <!-- 任务统计 -->
        <div class="stat-grid">
          <div class="stat-card">
            <div class="value">{{ dashboardStore.stats.pending_count }}</div>
            <div class="label">待筛选</div>
          </div>
          <div class="stat-card">
            <div class="value">{{ dashboardStore.stats.downloading_count }}</div>
            <div class="label">下载中</div>
          </div>
          <div class="stat-card">
            <div class="value">{{ dashboardStore.stats.completed_count }}</div>
            <div class="label">已完成</div>
          </div>
        </div>
        
        <!-- 下载速度 -->
        <div class="speed-display">
          <div class="speed-value">
            ↓ {{ dashboardStore.formatSpeed(dashboardStore.aria2.download_speed) }}
          </div>
          <div class="speed-label">
            {{ dashboardStore.aria2.active_count }} 个任务下载中 · 
            {{ dashboardStore.aria2.waiting_count }} 个等待中
          </div>
        </div>
        
        <!-- Linode 状态 -->
        <div class="linode-card">
          <div 
            class="status-badge" 
            :class="{ running: dashboardStore.linode.is_running }"
          >
            {{ dashboardStore.linode.is_running ? '运行中' : '未启动' }}
          </div>
          
          <template v-if="dashboardStore.linode.is_running">
            <div class="ip-address">
              {{ dashboardStore.linode.ip_address }}
            </div>
            <div class="cost">
              运行时长: {{ formatUptime(dashboardStore.linode.uptime_minutes) }}
              <br>
              预计费用: ${{ dashboardStore.linode.estimated_cost.toFixed(4) }}
            </div>
          </template>
          <template v-else>
            <div class="ip-address">-</div>
            <div class="cost">代理节点将在确认下载后自动启动</div>
          </template>
        </div>
        
        <!-- 月度费用 -->
        <van-cell-group inset style="margin-bottom: 20px">
          <van-cell title="本月累计费用" :value="'$' + dashboardStore.monthlyCost.toFixed(4)" />
        </van-cell-group>
        
        <!-- 紧急销毁按钮 -->
        <button 
          class="emergency-btn"
          @click="handleEmergencyDestroy"
          :disabled="dashboardStore.destroying"
        >
          <template v-if="dashboardStore.destroying">
            <van-loading size="20" color="#fff" />
          </template>
          <template v-else>
            🚨 紧急销毁所有实例
          </template>
        </button>
      </div>
    </van-pull-refresh>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import { useDashboardStore } from '../stores/dashboard'

const dashboardStore = useDashboardStore()
const refreshing = ref(false)
let refreshTimer = null

// 下拉刷新
async function onRefresh() {
  try {
    await dashboardStore.load()
  } finally {
    refreshing.value = false
  }
}

// 格式化运行时长
function formatUptime(minutes) {
  if (minutes < 60) return `${minutes} 分钟`
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  return `${hours} 小时 ${mins} 分钟`
}

// 紧急销毁
async function handleEmergencyDestroy() {
  try {
    await showConfirmDialog({
      title: '⚠️ 警告',
      message: '此操作将立即销毁所有 Linode 实例，正在进行的下载任务将被中断。确定要继续吗？',
      confirmButtonText: '确认销毁',
      confirmButtonColor: '#ee0a24',
      cancelButtonText: '取消'
    })
    
    const result = await dashboardStore.emergencyDestroy()
    showToast({
      message: result.message,
      icon: 'success'
    })
  } catch (e) {
    // 用户取消或操作失败
    if (e !== 'cancel') {
      showToast({
        message: '操作失败',
        icon: 'fail'
      })
    }
  }
}

// 定时刷新
onMounted(() => {
  dashboardStore.load()
  refreshTimer = setInterval(() => {
    dashboardStore.load()
  }, 10000) // 每 10 秒刷新
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<style scoped>
.dashboard-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
}

.dashboard-view > :last-child {
  flex: 1;
  overflow-y: auto;
}

.dashboard {
  padding: 16px;
  padding-bottom: calc(60px + env(safe-area-inset-bottom));
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  background: rgba(0, 0, 0, 0.2);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 16px;
  text-align: center;
}

.stat-card .value {
  font-size: 28px;
  font-weight: 700;
  color: #fff;
}

.stat-card .label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  margin-top: 4px;
}

.speed-display {
  background: rgba(0, 0, 0, 0.2);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 16px;
}

.speed-display .speed-value {
  font-size: 32px;
  font-weight: 700;
  color: #fff;
}

.speed-display .speed-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
  margin-top: 4px;
}

.linode-card {
  background: rgba(0, 0, 0, 0.25);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 16px;
}

.linode-card .status-badge {
  display: inline-block;
  padding: 4px 12px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
  margin-bottom: 12px;
}

.linode-card .status-badge.running {
  background: rgba(34, 197, 94, 0.3);
  color: #22c55e;
}

.linode-card .ip-address {
  font-size: 20px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 8px;
  font-family: 'JetBrains Mono', monospace;
}

.linode-card .cost {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.6;
}

.emergency-btn {
  width: 100%;
  height: 50px;
  background: rgba(239, 68, 68, 0.8);
  border: none;
  border-radius: 14px;
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 8px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.emergency-btn:hover {
  background: rgba(239, 68, 68, 0.95);
}

.emergency-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
