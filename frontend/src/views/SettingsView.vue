<template>
  <div class="settings-view">
    <van-nav-bar title="设置" :border="false" />
    
    <div class="settings-content">
      <!-- 频道管理 -->
      <van-cell-group inset title="监听频道">
        <van-cell 
          v-for="channel in channels" 
          :key="channel.id"
          :title="channel.name || channel.id"
          :label="channel.name ? channel.id : null"
        >
          <template #right-icon>
            <van-button 
              type="danger" 
              size="small" 
              plain
              @click="handleDelete(channel)"
            >
              删除
            </van-button>
          </template>
        </van-cell>
        
        <van-cell v-if="channels.length === 0" title="暂无监听频道" />
      </van-cell-group>
      
      <!-- 添加频道 -->
      <van-cell-group inset title="添加频道" style="margin-top: 20px">
        <van-field 
          v-model="newChannel.id" 
          label="频道 ID"
          placeholder="用户名或 -100xxx 格式的 ID"
        />
        <van-field 
          v-model="newChannel.name" 
          label="显示名称"
          placeholder="可选，用于展示"
        />
        <van-cell>
          <van-button 
            type="primary" 
            block 
            :loading="adding"
            @click="handleAdd"
          >
            添加频道
          </van-button>
        </van-cell>
      </van-cell-group>
      
      <!-- 使用说明 -->
      <van-cell-group inset title="说明" style="margin-top: 20px">
        <van-cell>
          <div class="help-text">
            <p><strong>频道 ID 格式：</strong></p>
            <ul>
              <li>公开频道：直接填用户名，如 <code>movie_channel</code></li>
              <li>私有频道：填 <code>-100</code> + 频道数字 ID，如 <code>-1001234567890</code></li>
            </ul>
            <p><strong>获取私有频道 ID：</strong></p>
            <ol>
              <li>在 Telegram 桌面版打开频道</li>
              <li>复制任意消息的链接</li>
              <li>链接格式 <code>t.me/c/1234567890/123</code></li>
              <li>频道 ID = <code>-100</code> + <code>1234567890</code></li>
            </ol>
            <p style="color: #ff976a">⚠️ 修改后需要重启采集器才能生效</p>
          </div>
        </van-cell>
      </van-cell-group>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { showToast, showConfirmDialog } from 'vant'
import api from '../api'

const channels = ref([])
const loading = ref(false)
const adding = ref(false)

const newChannel = ref({
  id: '',
  name: ''
})

// 加载频道列表
async function loadChannels() {
  loading.value = true
  try {
    const result = await api.settings.getChannels()
    channels.value = result.channels || []
  } catch (error) {
    showToast({ message: '加载失败', icon: 'fail' })
  } finally {
    loading.value = false
  }
}

// 添加频道
async function handleAdd() {
  if (!newChannel.value.id.trim()) {
    showToast('请输入频道 ID')
    return
  }
  
  adding.value = true
  try {
    await api.settings.addChannel({
      id: newChannel.value.id.trim(),
      name: newChannel.value.name.trim() || null
    })
    showToast({ message: '添加成功', icon: 'success' })
    newChannel.value = { id: '', name: '' }
    await loadChannels()
  } catch (error) {
    showToast({ message: error.message, icon: 'fail' })
  } finally {
    adding.value = false
  }
}

// 删除频道
async function handleDelete(channel) {
  try {
    await showConfirmDialog({
      title: '确认删除',
      message: `确定要删除频道 "${channel.name || channel.id}" 吗？`
    })
    
    await api.settings.deleteChannel(channel.id)
    showToast({ message: '删除成功', icon: 'success' })
    await loadChannels()
  } catch (e) {
    if (e !== 'cancel') {
      showToast({ message: '删除失败', icon: 'fail' })
    }
  }
}

onMounted(() => {
  loadChannels()
})
</script>

<style scoped>
.settings-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--background-color);
}

.settings-content {
  flex: 1;
  overflow-y: auto;
  padding-bottom: 20px;
}

.help-text {
  font-size: 13px;
  color: #646566;
  line-height: 1.8;
}

.help-text code {
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
}

.help-text ul, .help-text ol {
  padding-left: 20px;
  margin: 8px 0;
}
</style>
