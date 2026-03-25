<template>
  <div class="project-selector">
    <n-select
      v-model:value="currentProjectId"
      :options="projectOptions"
      :loading="loading"
      placeholder="选择项目"
      size="small"
      @update:value="handleProjectChange"
      :consistent-menu-width="false"
      style="min-width: 160px"
    >
      <template #prefix>
        <i class="fas fa-folder text-[#007857]"></i>
      </template>
    </n-select>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { NSelect } from 'naive-ui'
import { getProjects } from '@/api/testProject'

const emit = defineEmits(['change'])

const currentProjectId = ref(null)
const projects = ref([])
const loading = ref(false)

const projectOptions = computed(() => {
  return projects.value.map(p => ({
    label: p.is_default ? `${p.name} (默认)` : p.name,
    value: p.id,
    disabled: !p.is_active
  }))
})

const loadProjects = async () => {
  loading.value = true
  try {
    const res = await getProjects()
    if (res.success) {
      projects.value = res.data
      
      // 从 localStorage 获取上次选择的项目
      const savedProjectId = localStorage.getItem('currentProjectId')
      if (savedProjectId) {
        const savedProject = projects.value.find(p => p.id === parseInt(savedProjectId))
        if (savedProject && savedProject.is_active) {
          currentProjectId.value = savedProject.id
          return
        }
      }
      
      // 如果没有保存的项目或项目已禁用，使用默认项目
      const defaultProject = projects.value.find(p => p.is_default && p.is_active)
      if (defaultProject) {
        currentProjectId.value = defaultProject.id
        localStorage.setItem('currentProjectId', defaultProject.id)
      }
    }
  } catch (error) {
    console.error('加载项目列表失败:', error)
  } finally {
    loading.value = false
  }
}

const syncProjectSelection = (projectId) => {
  const numericProjectId = parseInt(projectId)
  if (!numericProjectId) return
  const matched = projects.value.find(p => p.id === numericProjectId && p.is_active)
  if (!matched) return
  currentProjectId.value = matched.id
  localStorage.setItem('currentProjectId', String(matched.id))
}

const handleProjectChangedEvent = (event) => {
  const nextProjectId = event?.detail?.projectId
  if (!nextProjectId) return
  syncProjectSelection(nextProjectId)
}

const handleStorageChange = (event) => {
  if (event.key !== 'currentProjectId' || !event.newValue) return
  syncProjectSelection(event.newValue)
}

const handleProjectChange = (projectId) => {
  localStorage.setItem('currentProjectId', projectId)
  window.dispatchEvent(new CustomEvent('project-changed', {
    detail: {
      projectId
    }
  }))
  emit('change', projectId)
  // 刷新页面以重新加载数据
  window.location.reload()
}

onMounted(() => {
  loadProjects()
  window.addEventListener('project-changed', handleProjectChangedEvent)
  window.addEventListener('storage', handleStorageChange)
})

onBeforeUnmount(() => {
  window.removeEventListener('project-changed', handleProjectChangedEvent)
  window.removeEventListener('storage', handleStorageChange)
})

// 暴露方法供父组件调用
defineExpose({
  refresh: loadProjects
})
</script>

<style scoped>
.project-selector {
  display: inline-block;
}
</style>
