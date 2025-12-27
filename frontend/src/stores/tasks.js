import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api'

export const useTaskStore = defineStore('tasks', () => {
    // 状态
    const pending = ref([])
    const loading = ref(false)
    const total = ref(0)

    // 计算属性
    const hasMore = computed(() => pending.value.length < total.value)
    const isEmpty = computed(() => !loading.value && pending.value.length === 0)

    // 加载待筛选任务
    async function loadPending(refresh = false) {
        if (loading.value) return

        loading.value = true
        try {
            const offset = refresh ? 0 : pending.value.length
            const result = await api.tasks.getPending(20, offset)

            if (refresh) {
                pending.value = result.tasks
            } else {
                pending.value.push(...result.tasks)
            }
            total.value = result.total
        } catch (error) {
            console.error('加载任务失败:', error)
            throw error
        } finally {
            loading.value = false
        }
    }

    // 确认下载
    async function confirm(taskId) {
        const index = pending.value.findIndex(t => t.id === taskId)
        if (index === -1) return

        try {
            await api.tasks.confirm(taskId)
            pending.value.splice(index, 1)
            total.value--
        } catch (error) {
            console.error('确认失败:', error)
            throw error
        }
    }

    // 忽略任务
    async function ignore(taskId) {
        const index = pending.value.findIndex(t => t.id === taskId)
        if (index === -1) return

        try {
            await api.tasks.ignore(taskId)
            pending.value.splice(index, 1)
            total.value--
        } catch (error) {
            console.error('忽略失败:', error)
            throw error
        }
    }

    // 获取当前顶部任务
    const currentTask = computed(() => pending.value[0] || null)

    return {
        pending,
        loading,
        total,
        hasMore,
        isEmpty,
        currentTask,
        loadPending,
        confirm,
        ignore
    }
})
