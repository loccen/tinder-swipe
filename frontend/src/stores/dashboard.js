import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api'

export const useDashboardStore = defineStore('dashboard', () => {
    // 状态
    const stats = ref({
        pending_count: 0,
        confirmed_count: 0,
        downloading_count: 0,
        completed_count: 0,
        error_count: 0
    })

    const linode = ref({
        is_running: false,
        linode_id: null,
        ip_address: null,
        uptime_minutes: 0,
        estimated_cost: 0
    })

    const aria2 = ref({
        download_speed: 0,
        upload_speed: 0,
        active_count: 0,
        waiting_count: 0,
        stopped_count: 0
    })

    const monthlyCost = ref(0)
    const loading = ref(false)
    const destroying = ref(false)
    const checkingProxy = ref(false)
    const proxyIp = ref(null)

    // 加载仪表盘数据
    async function load() {
        loading.value = true
        try {
            const data = await api.dashboard.getData()
            stats.value = data.stats
            linode.value = data.linode
            aria2.value = data.aria2
            monthlyCost.value = data.monthly_cost
        } catch (error) {
            console.error('加载仪表盘失败:', error)
            throw error
        } finally {
            loading.value = false
        }
    }

    // 紧急销毁
    async function emergencyDestroy() {
        destroying.value = true
        try {
            const result = await api.dashboard.emergencyDestroy()
            // 刷新数据
            await load()
            return result
        } catch (error) {
            console.error('紧急销毁失败:', error)
            throw error
        } finally {
            destroying.value = false
        }
    }

    // 检查代理 IP
    async function checkProxyIp() {
        checkingProxy.value = true
        proxyIp.value = null
        try {
            const result = await api.dashboard.checkProxyIp()
            if (result.success) {
                proxyIp.value = result.ip
            } else {
                throw new Error(result.error)
            }
            return result
        } catch (error) {
            console.error('检查代理 IP 失败:', error)
            throw error
        } finally {
            checkingProxy.value = false
        }
    }

    // 格式化速度显示
    function formatSpeed(bytesPerSecond) {
        if (bytesPerSecond >= 1024 * 1024) {
            return (bytesPerSecond / (1024 * 1024)).toFixed(1) + ' MB/s'
        } else if (bytesPerSecond >= 1024) {
            return (bytesPerSecond / 1024).toFixed(1) + ' KB/s'
        } else {
            return bytesPerSecond + ' B/s'
        }
    }

    return {
        stats,
        linode,
        aria2,
        monthlyCost,
        loading,
        destroying,
        checkingProxy,
        proxyIp,
        load,
        emergencyDestroy,
        checkProxyIp,
        formatSpeed
    }
})
