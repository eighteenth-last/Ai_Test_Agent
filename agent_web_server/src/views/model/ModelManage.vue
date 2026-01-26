<template>
  <div class="model-manage-view">
    <!-- 页面标题 -->
    <div class="mb-6">
      <div class="flex items-center gap-3 mb-2">
        <div class="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
          <i class="fas fa-brain text-white text-lg"></i>
        </div>
        <div>
          <h1 class="text-2xl font-bold text-slate-800">模型信息与切换</h1>
          <p class="text-sm text-slate-500">管理 LLM 模型配置，支持多模型切换策略</p>
        </div>
      </div>
    </div>

    <!-- 统计信息卡片 -->
    <div class="grid grid-cols-2 gap-5 mb-6">
      <!-- 当前活动模型 -->
      <div class="stat-card-modern bg-gradient-to-br from-green-50 to-emerald-50 border border-green-100">
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <div class="flex items-center gap-2 mb-1">
              <div class="w-8 h-8 rounded-lg bg-green-500 flex items-center justify-center">
                <i class="fas fa-check-circle text-white text-sm"></i>
              </div>
              <span class="text-sm font-medium text-slate-600">当前活动模型</span>
            </div>
            <p class="text-2xl font-bold text-slate-800 mt-2 truncate">
              {{ activeModel?.model_name || '未激活' }}
            </p>
            <p class="text-xs text-slate-500 mt-1">
              {{ activeModel?.provider ? `供应商: ${activeModel.provider}` : '请激活模型' }}
            </p>
          </div>
          <div class="flex items-center justify-center w-12 h-12 rounded-full bg-green-100">
            <i class="fas fa-robot text-green-600 text-xl"></i>
          </div>
        </div>
      </div>

      <!-- 今日消耗 TOKEN -->
      <div class="stat-card-modern bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-100">
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <div class="flex items-center gap-2 mb-1">
              <div class="w-8 h-8 rounded-lg bg-blue-500 flex items-center justify-center">
                <i class="fas fa-coins text-white text-sm"></i>
              </div>
              <span class="text-sm font-medium text-slate-600">今日消耗 TOKEN</span>
            </div>
            <p class="text-2xl font-bold text-slate-800 mt-2">
              {{ formatNumber(todayTokens) }}
            </p>
            <p class="text-xs text-slate-500 mt-1">
              {{ models.length }} 个模型在线
            </p>
          </div>
          <div class="flex items-center justify-center w-12 h-12 rounded-full bg-blue-100">
            <i class="fas fa-chart-line text-blue-600 text-xl"></i>
          </div>
        </div>
      </div>
    </div>

    <!-- 模型列表 -->
    <div class="bg-white rounded-xl shadow-sm border border-slate-200">
      <div class="p-5 border-b border-slate-200 flex items-center justify-between">
        <div>
          <h2 class="text-lg font-bold text-slate-800">模型配置列表</h2>
          <p class="text-sm text-slate-500 mt-1">管理和切换 AI 模型</p>
        </div>
        <n-space>
          <!-- 自动切换开关 -->
          <div class="flex items-center gap-3 px-4 py-2 rounded-lg border" :class="autoSwitch ? 'bg-purple-50 border-purple-200' : 'bg-slate-50 border-slate-200'">
            <i class="fas fa-sync-alt text-sm" :class="autoSwitch ? 'text-purple-600' : 'text-slate-400'"></i>
            <div class="flex flex-col">
              <span class="text-xs text-slate-500">自动切换模型</span>
              <span class="text-xs text-slate-400">智能负载均衡</span>
            </div>
            <n-switch 
              v-model:value="autoSwitch" 
              @update:value="handleAutoSwitchChange"
              size="small"
            />
          </div>
          <n-button type="primary" @click="openAddModal">
            <template #icon>
              <i class="fas fa-plus"></i>
            </template>
            添加模型
          </n-button>
        </n-space>
      </div>

      <n-spin :show="loading">
        <div class="p-5">
          <div v-if="models.length === 0" class="text-center py-12">
            <i class="fas fa-inbox text-slate-300 text-5xl mb-4"></i>
            <p class="text-slate-500">暂无模型配置</p>
          </div>
          
          <div v-else class="space-y-4">
            <div
              v-for="model in models"
              :key="model.id"
              class="model-card-modern"
              :class="{ 'active': model.is_active === 1 }"
            >
              <!-- 上半部分：模型信息和操作 -->
              <div class="flex items-start justify-between gap-4 mb-4">
                <div class="flex items-start gap-3 flex-1 min-w-0">
                  <!-- 优先级和状态标签 -->
                  <div class="flex flex-col gap-2 flex-shrink-0">
                    <n-tag :type="getPriorityType(model.priority)" size="small" round>
                      P{{ model.priority }}
                    </n-tag>
                    <span v-if="model.is_active === 1" class="status-badge-active">
                      <i class="fas fa-circle text-xs"></i>
                      活动
                    </span>
                  </div>

                  <!-- 模型名称和供应商 -->
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-2">
                      <h3 class="text-lg font-bold text-slate-800 truncate" :title="model.model_name">
                        {{ model.model_name }}
                      </h3>
                    </div>
                    <div class="flex items-center gap-2 text-sm text-slate-500">
                      <span v-if="model.provider" class="px-2 py-0.5 bg-slate-100 text-slate-600 text-xs rounded">
                        {{ model.provider }}
                      </span>
                      <span class="text-slate-400">|</span>
                      <span :class="model.status === 'active' ? 'text-green-600 font-medium' : ''">
                        {{ model.status || 'idle' }}
                      </span>
                    </div>
                  </div>
                </div>

                <!-- 操作按钮 -->
                <n-space class="flex-shrink-0">
                  <n-button
                    v-if="model.is_active !== 1"
                    size="small"
                    type="success"
                    @click="activateModel(model)"
                  >
                    <template #icon>
                      <i class="fas fa-play"></i>
                    </template>
                  </n-button>
                  <n-button
                    size="small"
                    @click="editModel(model)"
                  >
                    <template #icon>
                      <i class="fas fa-edit"></i>
                    </template>
                  </n-button>
                  <n-button
                    size="small"
                    type="error"
                    @click="deleteModel(model)"
                    :disabled="model.is_active === 1"
                  >
                    <template #icon>
                      <i class="fas fa-trash"></i>
                    </template>
                  </n-button>
                </n-space>
              </div>

              <!-- 下半部分：统计信息 -->
              <div class="grid grid-cols-3 gap-4 pt-4 border-t border-slate-200">
                <!-- 利用率 -->
                <div>
                  <span class="text-xs text-slate-500">利用率额度</span>
                  <div class="flex items-center gap-2 mt-2">
                    <div class="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div 
                        class="h-full transition-all duration-300"
                        :class="model.utilization < 10 ? 'bg-red-500' : model.utilization < 30 ? 'bg-orange-500' : 'bg-green-500'"
                        :style="{ width: model.utilization + '%' }"
                      ></div>
                    </div>
                    <span class="text-sm font-semibold text-slate-700 w-10 text-right">{{ model.utilization }}%</span>
                  </div>
                  <p v-if="model.utilization < 10" class="text-xs text-red-500 mt-1">即将触发切换</p>
                </div>
                
                <!-- 今日消耗 -->
                <div>
                  <span class="text-xs text-slate-500">今日消耗</span>
                  <p class="text-base font-semibold text-slate-700 mt-2">
                    {{ formatNumber(model.tokens_used_today || 0) }}
                  </p>
                  <p class="text-xs text-slate-400 mt-1">tokens</p>
                </div>
                
                <!-- API Key -->
                <div>
                  <span class="text-xs text-slate-500">API Key</span>
                  <p class="text-sm font-mono text-slate-600 mt-2 truncate" :title="model.api_key">
                    {{ model.api_key ? '••••' + model.api_key.slice(-8) : '-' }}
                  </p>
                  <p class="text-xs text-slate-400 mt-1">已加密</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </n-spin>

      <!-- 系统日志 -->
      <div class="border-t border-slate-200 bg-slate-50">
        <div class="p-4">
          <div class="flex items-center gap-2 mb-3">
            <i class="fas fa-terminal text-slate-600"></i>
            <span class="font-semibold text-slate-700">系统日志</span>
          </div>
          <div class="bg-slate-900 rounded-lg p-4 font-mono text-sm max-h-32 overflow-y-auto">
            <p v-for="(log, index) in systemLogs" :key="index" :class="`log-line log-${log.type}`">
              {{ log.message }}
            </p>
          </div>
        </div>
      </div>
    </div>
    <!-- 模型列表结束 -->

    <!-- 添加/编辑模型对话框 -->
    <n-modal
      v-model:show="modalVisible"
      preset="card"
      :title="isEditing ? '编辑模型' : '添加模型'"
      style="width: 600px"
    >
      <n-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-placement="left"
        label-width="120"
      >
        <n-form-item label="模型名称" path="model_name">
          <n-input v-model:value="formData.model_name" placeholder="如：DeepSeek V3, GPT-4" />
        </n-form-item>

        <n-form-item label="API Key" path="api_key">
          <n-input
            v-model:value="formData.api_key"
            type="password"
            placeholder="请输入 API Key"
            show-password-on="click"
          />
        </n-form-item>

        <n-form-item label="API 基础URL" path="base_url">
          <n-input v-model:value="formData.base_url" placeholder="如：https://api.deepseek.com/v1" />
        </n-form-item>

        <n-form-item label="模型供应商" path="provider">
          <n-select
            v-model:value="formData.provider"
            :options="providerOptions"
            placeholder="请选择供应商"
          />
        </n-form-item>

        <n-form-item label="优先级" path="priority">
          <n-input-number
            v-model:value="formData.priority"
            :min="1"
            :max="10"
            placeholder="数字越小优先级越高"
          />
        </n-form-item>

        <n-form-item label="利用率百分比" path="utilization">
          <n-input-number
            v-model:value="formData.utilization"
            :min="0"
            :max="100"
            :step="1"
            placeholder="0-100"
          >
            <template #suffix>%</template>
          </n-input-number>
        </n-form-item>
      </n-form>

      <template #footer>
        <n-space justify="end">
          <n-button @click="modalVisible = false">取消</n-button>
          <n-button type="primary" @click="submitForm" :loading="submitting">
            {{ isEditing ? '保存' : '添加' }}
          </n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import {
  NCard, NButton, NGrid, NGi, NStatistic, NSpace, NTag,
  NSpin, NModal, NForm, NFormItem, NInput, NInputNumber, NSelect, NSwitch,
  useMessage, useDialog
} from 'naive-ui'
import { modelAPI } from '@/api'

const message = useMessage()
const dialog = useDialog()

// 数据
const models = ref([])
const loading = ref(false)
const modalVisible = ref(false)
const isEditing = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const autoSwitch = ref(true)

// 系统日志
const systemLogs = ref([
  { type: 'system', message: '[SYSTEM] 检测到 Gemini 2.5 额度不足(低于5%)...' },
  { type: 'progress', message: '[PROGRESS] 正在总结当前对话至指定步数 (Step 15/20)...' },
  { type: 'snapshot', message: '[SNAPSHOT] 测试快照已生成并储存至数据库 Redis.' },
  { type: 'action', message: '[ACTION] 正在自动切换至备用模型：DeepSeek V3...' }
])

// 表单数据
const formData = reactive({
  id: null,
  model_name: '',
  api_key: '',
  base_url: '',
  provider: '',
  priority: 1,
  utilization: 100
})

// 供应商选项
const providerOptions = [
  { label: 'OpenAI', value: 'OpenAI' },
  { label: 'Anthropic', value: 'Anthropic' },
  { label: 'Google (Gemini)', value: 'Google' },
  { label: 'DeepSeek', value: 'DeepSeek' },
  { label: 'Alibaba (通义千问)', value: 'Alibaba' },
  { label: 'Baidu (文心一言)', value: 'Baidu' },
  { label: '其他', value: 'Other' }
]

// 表单验证规则
const formRules = {
  model_name: { required: true, message: '请输入模型名称', trigger: 'blur' },
  api_key: { required: true, message: '请输入 API Key', trigger: 'blur' },
  priority: { required: true, message: '请设置优先级', trigger: 'blur', type: 'number' },
  utilization: { required: true, message: '请设置利用率', trigger: 'blur', type: 'number' }
}

// 计算属性
const activeModel = computed(() => models.value.find(m => m.is_active === 1))
const todayTokens = computed(() => {
  return models.value.reduce((sum, m) => sum + (m.tokens_used_today || 0), 0)
})

// 格式化数字
const formatNumber = (num) => {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M'
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K'
  }
  return num.toString()
}

// 处理自动切换状态变更
const handleAutoSwitchChange = (value) => {
  message.success(`自动切换已${value ? '开启' : '关闭'}`)
  // TODO: 调用后端API保存设置
  console.log('自动切换状态:', value)
}

// 优先级类型
const getPriorityType = (priority) => {
  if (priority === 1) return 'error'
  if (priority === 2) return 'warning'
  if (priority === 3) return 'info'
  return 'default'
}

// 加载模型列表
const loadModels = async () => {
  loading.value = true
  try {
    const result = await modelAPI.getList()
    if (Array.isArray(result)) {
      models.value = result
    } else {
      message.error('获取模型列表失败')
    }
  } catch (error) {
    message.error('获取模型列表失败: ' + (error.message || '未知错误'))
    console.error(error)
  } finally {
    loading.value = false
  }
}

// 打开添加模态框
const openAddModal = () => {
  isEditing.value = false
  resetFormData()
  modalVisible.value = true
}

// 编辑模型
const editModel = (model) => {
  isEditing.value = true
  formData.id = model.id
  formData.model_name = model.model_name
  formData.api_key = model.api_key
  formData.base_url = model.base_url || ''
  formData.provider = model.provider || ''
  formData.priority = model.priority
  formData.utilization = model.utilization
  modalVisible.value = true
}

// 重置表单
const resetFormData = () => {
  formData.id = null
  formData.model_name = ''
  formData.api_key = ''
  formData.base_url = ''
  formData.provider = ''
  formData.priority = 1
  formData.utilization = 100
}

// 提交表单
const submitForm = async () => {
  try {
    await formRef.value?.validate()
  } catch (error) {
    return
  }

  submitting.value = true
  try {
    let result
    if (isEditing.value) {
      result = await modelAPI.update(formData.id, formData)
    } else {
      result = await modelAPI.add(formData)
    }

    if (result.success) {
      message.success(isEditing.value ? '更新成功' : '添加成功')
      modalVisible.value = false
      loadModels()
    } else {
      message.error(result.message || '操作失败')
    }
  } catch (error) {
    message.error('操作失败: ' + (error.message || '未知错误'))
    console.error(error)
  } finally {
    submitting.value = false
  }
}

// 激活模型
const activateModel = async (model) => {
  try {
    const result = await modelAPI.activate(model.id)
    if (result.success) {
      message.success(`模型 ${model.model_name} 已激活`)
      loadModels()
      
      // 添加系统日志
      systemLogs.value.unshift({
        type: 'action',
        message: `[ACTION] 手动切换至模型：${model.model_name}`
      })
    } else {
      message.error(result.message || '激活失败')
    }
  } catch (error) {
    message.error('激活失败: ' + (error.message || '未知错误'))
    console.error(error)
  }
}

// 删除模型
const deleteModel = (model) => {
  if (model.is_active === 1) {
    message.warning('无法删除激活中的模型')
    return
  }

  dialog.warning({
    title: '确认删除',
    content: `确定要删除模型 "${model.model_name}" 吗？`,
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const result = await modelAPI.delete(model.id)
        if (result.success) {
          message.success('删除成功')
          loadModels()
        } else {
          message.error(result.message || '删除失败')
        }
      } catch (error) {
        message.error('删除失败: ' + (error.message || '未知错误'))
        console.error(error)
      }
    }
  })
}

onMounted(() => {
  loadModels()
})
</script>

<style scoped>
.model-manage-view {
  padding: 0;
}

/* 统计卡片 */
.stat-card-modern {
  padding: 1.25rem;
  border-radius: 1rem;
  transition: all 0.3s ease;
}

.stat-card-modern:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
}

/* 模型卡片 */
.model-card-modern {
  padding: 1.5rem;
  background: linear-gradient(to right, #fafafa, #ffffff);
  border: 1px solid #e5e7eb;
  border-radius: 0.75rem;
  transition: all 0.3s ease;
}

.model-card-modern:hover {
  border-color: #007857;
  box-shadow: 0 4px 12px rgba(0, 120, 87, 0.1);
}

.model-card-modern.active {
  background: linear-gradient(to right, #ecfdf5, #f0fdf4);
  border: 2px solid #10b981;
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2);
}

.status-badge-active {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.5rem;
  background: linear-gradient(135deg, #10b981, #059669);
  color: white;
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 9999px;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.8;
  }
}

/* 系统日志 */
.log-line {
  margin-bottom: 0.5rem;
  font-size: 0.75rem;
  line-height: 1.5;
}

.log-system {
  color: #60a5fa;
}

.log-progress {
  color: #fbbf24;
}

.log-snapshot {
  color: #a78bfa;
}

.log-action {
  color: #34d399;
}

/* 自定义滚动条 */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #555;
}
</style>
