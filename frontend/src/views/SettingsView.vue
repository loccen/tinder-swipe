<template>
  <div class="settings-view">
    <van-nav-bar title="设置" :border="false" />

    <!-- 顶层提示：状态生效反馈 -->
    <van-notice-bar left-icon="info-o" text="修改后约 30 秒自动生效，无需手动重启采集器。" background="rgba(255, 255, 255, 0.1)"
      color="#fff" />

    <div class="settings-content">
      <!-- 频道管理 -->
      <div class="section-title">监听频道</div>
      <van-cell-group inset>
        <van-cell v-for="channel in channels" :key="channel.id">
          <template #title>
            <div class="channel-title">
              <span class="status-dot"></span>
              {{ channel.name || channel.id }}
            </div>
          </template>
          <template #label v-if="channel.name">
            {{ channel.id }}
          </template>
          <template #right-icon>
            <div class="action-btns">
              <van-icon name="edit" class="edit-icon" @click="handleEdit(channel)" />
              <van-button type="danger" size="small" plain round @click="handleDelete(channel)">
                删除
              </van-button>
            </div>
          </template>
        </van-cell>

        <!-- 空状态设计 -->
        <van-empty v-if="channels.length === 0" image="network" description="暂无监听频道，请在下方添加" />
      </van-cell-group>

      <!-- 添加频道 -->
      <div class="section-title">添加频道</div>
      <van-cell-group inset>
        <van-field v-model="newChannel.id" label="频道 ID" placeholder="粘贴链接或输入 ID" @input="handleIdInput" />
        <van-field v-model="newChannel.name" label="显示名称" placeholder="可选，用于展示" />
        <van-cell>
          <van-button type="primary" block round :loading="adding" @click="handleAdd">
            添加频道
          </van-button>
        </van-cell>
      </van-cell-group>

      <!-- 使用说明：改为收纳折叠面板 -->
      <div class="section-title">使用说明</div>
      <van-collapse v-model="activeNames" inset>
        <van-collapse-item title="如何获取频道 ID？" name="1">
          <div class="help-text">
            <p><strong>频道 ID 格式：</strong></p>
            <ul>
              <li>公开频道：直接填用户名，如 <code>movie_channel</code></li>
              <li>私有频道：填 <code>-100</code> + 频道数字 ID，如 <code>-1001234567890</code></li>
            </ul>
            <p><strong>获取私有频道 ID：</strong></p>
            <ol>
              <li>在 Telegram 桌面版中右键点击频道消息</li>
              <li>选择“复制消息链接”，链接格式如 <code>t.me/c/1234567890/123</code></li>
              <li>直接将该链接粘贴到上方的“频道 ID”框，系统将自动解析。</li>
            </ol>
          </div>
        </van-collapse-item>
      </van-collapse>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, h } from 'vue'
import { showToast, showConfirmDialog, Dialog, Field } from 'vant'
import api from '../api'

const channels = ref([])
const loading = ref(false)
const adding = ref(false)
const activeNames = ref([])

const newChannel = ref({
  id: '',
  name: ''
})

// 自动解析 ID 逻辑
function handleIdInput(val) {
  // 识别 t.me/c/1234567890/123 格式
  const regex = /t\.me\/c\/(\d+)/
  const match = val.match(regex)
  if (match && match[1]) {
    newChannel.value.id = `-100${match[1]}`
    showToast('已自动解析频道 ID')
  }
}

// 编辑频道名称
async function handleEdit(channel) {
  const newName = ref(channel.name || '')
  Dialog.confirm({
    title: '编辑名称',
    message: () => h(Field, {
      modelValue: newName.value,
      'onUpdate:modelValue': (val) => { newName.value = val },
      placeholder: '请输入新的显示名称',
      autofocus: true
    }),
  }).then(async () => {
    try {
      await api.settings.addChannel({
        id: channel.id,
        name: newName.value.trim() || null
      })
      showToast({ message: '修改成功', icon: 'success' })
      await loadChannels()
    } catch (error) {
      showToast({ message: '修改失败', icon: 'fail' })
    }
  }).catch(() => { })
}

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
  background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
}

.settings-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  padding-bottom: calc(80px + env(safe-area-inset-bottom));
}

.section-title {
  margin: 24px 16px 12px;
  color: rgba(255, 255, 255, 0.6);
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.channel-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  background: #22c55e;
  border-radius: 50%;
  box-shadow: 0 0 8px #22c55e;
}

.action-btns {
  display: flex;
  align-items: center;
  gap: 12px;
}

.edit-icon {
  font-size: 18px;
  color: rgba(255, 255, 255, 0.4);
  cursor: pointer;
}

.help-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.8;
  text-align: left;
  /* 修正对齐 */
}

.help-text p {
  color: rgba(255, 255, 255, 0.5);
  margin-bottom: 4px;
}

.help-text strong {
  color: #fff;
}

.help-text code {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  padding: 2px 8px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
}

.help-text ul,
.help-text ol {
  padding-left: 18px;
  margin: 12px 0;
  color: rgba(255, 255, 255, 0.6);
}

:deep(.van-collapse-item__content) {
  background: transparent !important;
  color: inherit !important;
  padding: 12px 16px;
}

:deep(.van-notice-bar) {
  margin-top: 1px;
}
</style>
