import axios from 'axios'

const api = axios.create({
    baseURL: '/api',
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json'
    }
})

// 响应拦截器
api.interceptors.response.use(
    response => response.data,
    error => {
        const message = error.response?.data?.detail || error.message || '请求失败'
        console.error('API Error:', message)
        return Promise.reject(new Error(message))
    }
)

export default {
    // 任务相关
    tasks: {
        /**
         * 获取待筛选任务列表
         */
        getPending(limit = 20, offset = 0) {
            return api.get('/tasks/pending', { params: { limit, offset } })
        },

        /**
         * 获取任务详情
         */
        get(taskId) {
            return api.get(`/tasks/${taskId}`)
        },

        /**
         * 执行任务操作 (confirm/ignore)
         */
        action(taskId, action) {
            return api.post(`/tasks/${taskId}/action`, { action })
        },

        /**
         * 确认下载 (左滑)
         */
        confirm(taskId) {
            return this.action(taskId, 'confirm')
        },

        /**
         * 忽略任务 (右滑)
         */
        ignore(taskId) {
            return this.action(taskId, 'ignore')
        },

        /**
         * 获取任务列表 (按状态过滤)
         */
        list(status, limit = 20, offset = 0) {
            return api.get('/tasks', { params: { status, limit, offset } })
        }
    },

    // 仪表盘相关
    dashboard: {
        /**
         * 获取仪表盘数据
         */
        getData() {
            return api.get('/dashboard')
        },

        /**
         * 紧急销毁所有实例
         */
        emergencyDestroy() {
            return api.post('/dashboard/emergency-destroy')
        }
    },

    // 设置相关
    settings: {
        /**
         * 获取监听频道列表
         */
        getChannels() {
            return api.get('/settings/channels')
        },

        /**
         * 更新频道列表
         */
        updateChannels(channels) {
            return api.put('/settings/channels', { channels })
        },

        /**
         * 添加频道
         */
        addChannel(channel) {
            return api.post('/settings/channels', channel)
        },

        /**
         * 删除频道
         */
        deleteChannel(channelId) {
            return api.delete(`/settings/channels/${encodeURIComponent(channelId)}`)
        }
    }
}
