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
          <p class="text-sm text-slate-500">管理 LLM 模型配置，支持多模型自动切换策略</p>
        </div>
      </div>
    </div>

    <!-- 统计信息卡片 -->
    <div class="grid grid-cols-4 gap-5 mb-6">
      <!-- 当前活动模型 -->
      <div class="stat-card-modern bg-gradient-to-br from-green-50 to-emerald-50 border border-green-100 col-span-2">
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
              {{ activeModel?.provider_display_name || activeModel?.provider ? `供应商: ${activeModel.provider_display_name || activeModel.provider}` : '请激活模型' }}
            </p>
          </div>
          <div class="flex items-center justify-center w-12 h-12 rounded-full bg-green-100">
            <i class="fas fa-robot text-green-600 text-xl"></i>
          </div>
        </div>
      </div>

      <!-- 总消耗 TOKEN -->
      <div class="stat-card-modern bg-gradient-to-br from-purple-50 to-violet-50 border border-purple-100">
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <div class="flex items-center gap-2 mb-1">
              <div class="w-8 h-8 rounded-lg bg-purple-500 flex items-center justify-center">
                <i class="fas fa-database text-white text-sm"></i>
              </div>
              <span class="text-sm font-medium text-slate-600">总消耗 TOKEN</span>
            </div>
            <p class="text-2xl font-bold text-slate-800 mt-2">
              {{ formatNumber(totalTokens) }}
            </p>
            <p class="text-xs text-slate-500 mt-1">
              入 {{ formatNumber(totalInputTokens) }} / 出 {{ formatNumber(totalOutputTokens) }}
            </p>
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
              {{ models.length }} 个模型 · {{ totalRequests }} 次请求
            </p>
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
              <span class="text-xs text-slate-400">限流/失败自动切换</span>
            </div>
            <n-switch 
              v-model:value="autoSwitch" 
              @update:value="handleAutoSwitchChange"
              size="small"
            />
          </div>
          <n-button size="small" @click="resetAllProfiles" :disabled="!autoSwitch">
            <template #icon><i class="fas fa-redo"></i></template>
            重置状态
          </n-button>
          <n-button type="primary" @click="openAddModal">
            <template #icon><i class="fas fa-plus"></i></template>
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
          
          <div v-else class="grid grid-cols-1 gap-5">
            <div
              v-for="model in models"
              :key="model.id"
              class="model-card-modern"
              :class="{ 'active': model.is_active === 1 }"
            >
              <!-- 上半部分：模型信息和操作 -->
              <div class="flex items-start justify-between gap-4 mb-4">
                <div class="flex items-start gap-3 flex-1 min-w-0">
                  <div class="flex flex-col gap-2 flex-shrink-0">
                    <n-tag :type="getPriorityType(model.priority)" size="small" round>
                      P{{ model.priority }}
                    </n-tag>
                    <span v-if="model.is_active === 1" class="status-badge-active">
                      <i class="fas fa-circle text-xs"></i>
                      活动
                    </span>
                    <!-- 自动切换健康状态 -->
                    <span v-if="getProfileStatus(model.id)" class="text-xs px-2 py-0.5 rounded-full"
                      :class="getProfileStatus(model.id).is_cooling_down ? 'bg-red-100 text-red-600' : 'bg-green-100 text-green-600'">
                      {{ getProfileStatus(model.id).is_cooling_down ? `冷却 ${getProfileStatus(model.id).cooldown_remaining}s` : '健康' }}
                    </span>
                  </div>

                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-2">
                      <h3 class="text-lg font-bold text-slate-800 truncate" :title="model.model_name">
                        {{ model.model_name }}
                      </h3>
                    </div>
                    <div class="flex items-center gap-2 text-sm text-slate-500">
                      <span v-if="model.provider_display_name || model.provider" class="px-2 py-0.5 bg-slate-100 text-slate-600 text-xs rounded">
                        {{ model.provider_display_name || model.provider }}
                      </span>
                      <span class="text-slate-400">|</span>
                      <span :class="model.status === 'active' ? 'text-green-600 font-medium' : ''">
                        {{ model.status || 'idle' }}
                      </span>
                      <!-- 失败次数 -->
                      <template v-if="getProfileStatus(model.id)?.failure_count > 0">
                        <span class="text-slate-400">|</span>
                        <span class="text-red-500 text-xs">
                          失败 {{ getProfileStatus(model.id).failure_count }} 次
                          <template v-if="getProfileStatus(model.id).last_failure_reason">
                            ({{ getProfileStatus(model.id).last_failure_reason }})
                          </template>
                        </span>
                      </template>
                    </div>
                  </div>
                </div>

                <n-space class="flex-shrink-0">
                  <n-button
                    v-if="model.is_active !== 1"
                    size="small"
                    type="success"
                    @click="activateModel(model)"
                  >
                    <template #icon><i class="fas fa-play"></i></template>
                  </n-button>
                  <n-button size="small" @click="editModel(model)">
                    <template #icon><i class="fas fa-edit"></i></template>
                  </n-button>
                  <n-button
                    size="small"
                    type="error"
                    @click="deleteModel(model)"
                    :disabled="model.is_active === 1"
                  >
                    <template #icon><i class="fas fa-trash"></i></template>
                  </n-button>
                </n-space>
              </div>

              <!-- 下半部分：统计信息 -->
              <div class="grid grid-cols-4 gap-4 pt-4 border-t border-slate-200">
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
                </div>
                <div>
                  <span class="text-xs text-slate-500">总消耗</span>
                  <p class="text-base font-semibold text-slate-700 mt-2">{{ formatNumber(model.tokens_used_total || 0) }}</p>
                  <p class="text-xs text-slate-400 mt-1">tokens</p>
                </div>
                <div>
                  <span class="text-xs text-slate-500">今日消耗</span>
                  <p class="text-base font-semibold text-slate-700 mt-2">{{ formatNumber(model.tokens_used_today || 0) }}</p>
                  <p class="text-xs text-slate-400 mt-1">tokens</p>
                </div>
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
    </div>

    <!-- 自动切换历史 & Token 统计 -->
    <div class="grid grid-cols-2 gap-5 mt-6">
      <!-- 切换历史 -->
      <div class="bg-white rounded-xl shadow-sm border border-slate-200">
        <div class="p-4 border-b border-slate-200 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <i class="fas fa-history text-purple-500"></i>
            <span class="font-semibold text-slate-700">自动切换历史</span>
          </div>
          <n-tag size="small" :type="autoSwitch ? 'success' : 'default'">
            {{ autoSwitch ? '已开启' : '已关闭' }}
          </n-tag>
        </div>
        <div class="p-4 max-h-64 overflow-y-auto">
          <div v-if="switchHistory.length === 0" class="text-center py-6 text-slate-400 text-sm">
            暂无切换记录
          </div>
          <div v-else class="space-y-3">
            <div v-for="(record, idx) in switchHistory" :key="idx"
              class="flex items-start gap-3 p-3 rounded-lg bg-slate-50 text-sm">
              <i class="fas fa-exchange-alt text-purple-400 mt-0.5"></i>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-1 text-slate-700">
                  <span class="font-medium truncate">{{ record.from_name }}</span>
                  <i class="fas fa-arrow-right text-xs text-slate-400"></i>
                  <span class="font-medium text-green-600 truncate">{{ record.to_name }}</span>
                </div>
                <p class="text-xs text-slate-400 mt-1">{{ record.reason }} · {{ formatTime(record.time) }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Token 来源统计 -->
      <div class="bg-white rounded-xl shadow-sm border border-slate-200">
        <div class="p-4 border-b border-slate-200 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <i class="fas fa-chart-pie text-blue-500"></i>
            <span class="font-semibold text-slate-700">Token 来源统计</span>
          </div>
          <n-button size="tiny" quaternary @click="resetTodayTokens">
            <template #icon><i class="fas fa-redo text-xs"></i></template>
            重置今日
          </n-button>
        </div>
        <div class="p-4">
          <div v-if="sourceStats.length === 0" class="text-center py-6 text-slate-400 text-sm">
            暂无统计数据
          </div>
          <div v-else class="space-y-3">
            <div v-for="stat in sourceStats" :key="stat.source"
              class="flex items-center justify-between p-3 rounded-lg bg-slate-50">
              <div class="flex items-center gap-2">
                <i :class="getSourceIcon(stat.source)" class="text-sm w-5 text-center"></i>
                <span class="text-sm font-medium text-slate-700">{{ getSourceLabel(stat.source) }}</span>
              </div>
              <div class="text-right">
                <span class="text-sm font-semibold text-slate-800">{{ formatNumber(stat.total_tokens) }}</span>
                <span class="text-xs text-slate-400 ml-1">tokens</span>
                <p class="text-xs text-slate-400">{{ stat.count }} 次请求</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 最近 Token 使用日志 -->
    <div class="bg-white rounded-xl shadow-sm border border-slate-200 mt-6">
      <div class="p-4 border-b border-slate-200 flex items-center justify-between gap-4">
        <div class="flex items-center gap-2">
          <i class="fas fa-list-alt text-indigo-500"></i>
          <span class="font-semibold text-slate-700">最近请求日志</span>
        </div>
        <div class="flex items-center gap-3">
          <n-pagination
            v-if="tokenLogs.length > 0"
            v-model:page="tokenLogPage"
            :page-size="tokenLogPageSize"
            :item-count="tokenLogs.length"
            size="small"
          />
          <n-button size="tiny" quaternary @click="loadTokenLogs">
            <template #icon><i class="fas fa-sync text-xs"></i></template>
            刷新
          </n-button>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="bg-slate-50 text-slate-600">
            <tr>
              <th class="px-4 py-3 text-left font-medium">时间</th>
              <th class="px-4 py-3 text-left font-medium">模型</th>
              <th class="px-4 py-3 text-left font-medium">来源</th>
              <th class="px-4 py-3 text-right font-medium">输入</th>
              <th class="px-4 py-3 text-right font-medium">输出</th>
              <th class="px-4 py-3 text-right font-medium">总计</th>
              <th class="px-4 py-3 text-right font-medium">耗时</th>
              <th class="px-4 py-3 text-center font-medium">状态</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-if="tokenLogs.length === 0">
              <td colspan="8" class="px-4 py-8 text-center text-slate-400">暂无日志</td>
            </tr>
            <tr v-for="log in pagedTokenLogs" :key="log.id" class="hover:bg-slate-50">
              <td class="px-4 py-2.5 text-slate-500 whitespace-nowrap">{{ formatTime(log.created_at) }}</td>
              <td class="px-4 py-2.5 text-slate-700 font-medium truncate max-w-[200px]">{{ log.model_name }}</td>
              <td class="px-4 py-2.5">
                <span class="px-2 py-0.5 rounded text-xs" :class="getSourceClass(log.source)">
                  {{ getSourceLabel(log.source) }}
                </span>
              </td>
              <td class="px-4 py-2.5 text-right text-slate-600">{{ formatNumber(log.prompt_tokens) }}</td>
              <td class="px-4 py-2.5 text-right text-slate-600">{{ formatNumber(log.completion_tokens) }}</td>
              <td class="px-4 py-2.5 text-right font-semibold text-slate-800">{{ formatNumber(log.total_tokens) }}</td>
              <td class="px-4 py-2.5 text-right text-slate-500">{{ log.duration_ms ? (log.duration_ms / 1000).toFixed(1) + 's' : '-' }}</td>
              <td class="px-4 py-2.5 text-center">
                <i v-if="log.success" class="fas fa-check-circle text-green-500"></i>
                <n-tooltip v-else>
                  <template #trigger>
                    <i class="fas fa-times-circle text-red-500"></i>
                  </template>
                  {{ log.error_type || '未知错误' }}
                </n-tooltip>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 系统日志 -->
    <div class="bg-white rounded-xl shadow-sm border border-slate-200 mt-6">
      <div class="p-4 border-b border-slate-200">
        <div class="flex items-center gap-2">
          <i class="fas fa-terminal text-slate-600"></i>
          <span class="font-semibold text-slate-700">系统日志</span>
        </div>
      </div>
      <div class="p-4">
        <div class="bg-slate-900 rounded-lg p-4 font-mono text-sm max-h-32 overflow-y-auto">
          <p v-for="(log, index) in systemLogs" :key="index" :class="`log-line log-${log.type}`">
            {{ log.message }}
          </p>
        </div>
      </div>
    </div>

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
          <n-input v-model:value="formData.api_key" type="password" placeholder="请输入 API Key" show-password-on="click" />
        </n-form-item>
        <n-form-item label="API 基础URL" path="base_url">
          <n-input v-model:value="formData.base_url" placeholder="如：https://api.deepseek.com/v1" />
        </n-form-item>
        <n-form-item label="模型供应商" path="provider">
          <n-select v-model:value="formData.provider" :options="providerOptions" placeholder="请选择供应商" />
        </n-form-item>
        <n-form-item label="优先级" path="priority">
          <n-input-number v-model:value="formData.priority" :min="1" :max="10" placeholder="数字越小优先级越高" />
        </n-form-item>
        <n-form-item label="利用率百分比" path="utilization">
          <n-input-number v-model:value="formData.utilization" :min="0" :max="100" :step="1" placeholder="0-100">
            <template #suffix>%</template>
          </n-input-number>
        </n-form-item>
        <n-alert title="配置说明" type="info" class="mt-2" :bordered="false">
          <div class="text-xs text-slate-500">
            <p class="mb-1">1. 请完善填写：模型名称、API Key、API 基础URL、模型供应商。</p>
            <p>2. 供应商选择：请选择模型实际归属的厂商。例如使用中转服务调用 ChatGPT，供应商仍应选择 OpenAI。</p>
          </div>
        </n-alert>
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
import { ref, reactive, onMounted, onUnmounted, computed, watch } from 'vue'
import {
  NCard, NButton, NGrid, NGi, NStatistic, NSpace, NTag,
  NSpin, NModal, NForm, NFormItem, NInput, NInputNumber, NSelect, NSwitch, NAlert, NTooltip, NPagination,
  useMessage, useDialog
} from 'naive-ui'
import { modelAPI, dashboardAPI } from '@/api'

const message = useMessage()
const dialog = useDialog()

const models = ref([])
const loading = ref(false)
const modalVisible = ref(false)
const isEditing = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const autoSwitch = ref(true)

// 自动切换状态
const autoSwitchProfiles = ref([])
const switchHistory = ref([])

// Token 统计
const sourceStats = ref([])
const tokenLogs = ref([])

const tokenLogPageSize = 15
const tokenLogPage = ref(1)
const tokenLogPageCount = computed(() => Math.max(1, Math.ceil(tokenLogs.value.length / tokenLogPageSize)))
const pagedTokenLogs = computed(() => {
  const start = (tokenLogPage.value - 1) * tokenLogPageSize
  return tokenLogs.value.slice(start, start + tokenLogPageSize)
})

watch(
  () => tokenLogs.value.length,
  () => {
    if (tokenLogPage.value > tokenLogPageCount.value) {
      tokenLogPage.value = tokenLogPageCount.value
    }
  }
)

const systemLogs = ref([])
let pollTimer = null

const addSystemLog = (type, msg) => {
  systemLogs.value.unshift({ type, message: msg })
  if (systemLogs.value.length > 50) systemLogs.value.pop()
}

// 表单数据
const formData = reactive({
  id: null, model_name: '', api_key: '', base_url: '', provider: '', priority: 1, utilization: 100
})

const providerOptions = ref([])

const formRules = {
  model_name: { required: true, message: '请输入模型名称', trigger: 'blur' },
  api_key: { required: true, message: '请输入 API Key', trigger: 'blur' },
  priority: { required: true, message: '请设置优先级', trigger: 'blur', type: 'number' },
  utilization: { required: true, message: '请设置利用率', trigger: 'blur', type: 'number' }
}

// 计算属性
const activeModel = computed(() => models.value.find(m => m.is_active === 1))
const totalTokens = computed(() => models.value.reduce((sum, m) => sum + (m.tokens_used_total || 0), 0))
const todayTokens = computed(() => models.value.reduce((sum, m) => sum + (m.tokens_used_today || 0), 0))
const totalInputTokens = computed(() => sourceStats.value.reduce((sum, s) => sum + (s.prompt_tokens || 0), 0))
const totalOutputTokens = computed(() => sourceStats.value.reduce((sum, s) => sum + (s.completion_tokens || 0), 0))
const totalRequests = computed(() => sourceStats.value.reduce((sum, s) => sum + (s.count || 0), 0))

const formatNumber = (num) => {
  if (!num) return '0'
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toString()
}

const formatTime = (timeStr) => {
  if (!timeStr) return ''
  try {
    const d = new Date(timeStr)
    return `${(d.getMonth()+1).toString().padStart(2,'0')}-${d.getDate().toString().padStart(2,'0')} ${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}:${d.getSeconds().toString().padStart(2,'0')}`
  } catch { return timeStr }
}

const getProfileStatus = (modelId) => {
  return autoSwitchProfiles.value.find(p => p.model_id === modelId)
}

const getSourceIcon = (source) => {
  const map = { chat: 'fas fa-comment text-blue-500', browser_use: 'fas fa-globe text-green-500', oneclick: 'fas fa-bolt text-purple-500', api_test: 'fas fa-plug text-orange-500' }
  return map[source] || 'fas fa-circle text-slate-400'
}

const getSourceLabel = (source) => {
  const map = { chat: '对话', browser_use: '浏览器测试', oneclick: '一键测试', api_test: '接口测试' }
  return map[source] || source || '未知'
}

const getSourceClass = (source) => {
  const map = { chat: 'bg-blue-100 text-blue-700', browser_use: 'bg-green-100 text-green-700', oneclick: 'bg-purple-100 text-purple-700', api_test: 'bg-orange-100 text-orange-700' }
  return map[source] || 'bg-slate-100 text-slate-600'
}

const getPriorityType = (priority) => {
  if (priority === 1) return 'error'
  if (priority === 2) return 'warning'
  if (priority === 3) return 'info'
  return 'default'
}

// ===== API 调用 =====

const handleAutoSwitchChange = async (value) => {
  try {
    const result = await modelAPI.toggleAutoSwitch(value)
    if (result.success) {
      message.success(`自动切换已${value ? '开启' : '关闭'}`)
      addSystemLog('action', `[ACTION] 自动切换已${value ? '开启' : '关闭'}`)
    }
  } catch (error) {
    message.error('切换失败: ' + (error.message || ''))
    autoSwitch.value = !value
  }
}

const resetAllProfiles = async () => {
  try {
    const result = await modelAPI.resetAutoSwitch()
    if (result.success) {
      message.success('所有模型状态已重置')
      loadAutoSwitchStatus()
    }
  } catch (error) {
    message.error('重置失败')
  }
}

const resetTodayTokens = async () => {
  try {
    const result = await modelAPI.resetTodayTokens()
    if (result.success) {
      message.success('今日统计已重置')
      loadModels()
    }
  } catch (error) {
    message.error('重置失败')
  }
}

const loadAutoSwitchStatus = async () => {
  try {
    const result = await modelAPI.getAutoSwitchStatus()
    if (result.success) {
      autoSwitch.value = result.data.enabled
      autoSwitchProfiles.value = result.data.profiles || []
      switchHistory.value = (result.data.switch_history || []).reverse()
    }
  } catch (error) {
    console.error('加载自动切换状态失败:', error)
  }
}

const loadTokenStats = async () => {
  try {
    const result = await modelAPI.getTokenStatsSummary()
    if (result.success) {
      sourceStats.value = result.data.by_source || []
    }
  } catch (error) {
    console.error('加载 Token 统计失败:', error)
  }
}

const loadTokenLogs = async () => {
  try {
    const result = await modelAPI.getRecentTokenLogs(30)
    if (result.success) {
      tokenLogs.value = result.data || []
      tokenLogPage.value = 1
    }
  } catch (error) {
    console.error('加载 Token 日志失败:', error)
  }
}

const loadProviders = async () => {
  try {
    const result = await modelAPI.getProviders()
    if (result.success && Array.isArray(result.data)) {
      providerOptions.value = result.data.map(p => ({ label: p.display_name, value: p.code }))
    } else {
      useFallbackProviders()
    }
  } catch (error) {
    useFallbackProviders()
  }
}

const useFallbackProviders = () => {
  providerOptions.value = [
    { label: 'OpenAI', value: 'openai' },
    { label: 'Anthropic', value: 'anthropic' },
    { label: 'Google (Gemini)', value: 'google' },
    { label: 'DeepSeek', value: 'deepseek' },
    { label: 'Alibaba (通义千问)', value: 'alibaba' },
    { label: '其他', value: 'other' }
  ]
}

const loadModels = async () => {
  loading.value = true
  try {
    const result = await modelAPI.getList()
    if (Array.isArray(result)) {
      models.value = result
    }
  } catch (error) {
    message.error('获取模型列表失败')
  } finally {
    loading.value = false
  }
}

const openAddModal = () => {
  isEditing.value = false
  Object.assign(formData, { id: null, model_name: '', api_key: '', base_url: '', provider: '', priority: 1, utilization: 100 })
  modalVisible.value = true
}

const editModel = (model) => {
  isEditing.value = true
  Object.assign(formData, {
    id: model.id, model_name: model.model_name, api_key: model.api_key,
    base_url: model.base_url || '', provider: model.provider || '',
    priority: model.priority, utilization: model.utilization
  })
  modalVisible.value = true
}

const submitForm = async () => {
  try { await formRef.value?.validate() } catch { return }
  submitting.value = true
  try {
    const result = isEditing.value
      ? await modelAPI.update(formData.id, formData)
      : await modelAPI.add(formData)
    if (result.success) {
      message.success(isEditing.value ? '更新成功' : '添加成功')
      modalVisible.value = false
      loadModels()
    } else {
      message.error(result.message || '操作失败')
    }
  } catch (error) {
    message.error('操作失败: ' + (error.message || ''))
  } finally {
    submitting.value = false
  }
}

const activateModel = async (model) => {
  try {
    const result = await modelAPI.activate(model.id)
    if (result.success) {
      message.success(`模型 ${model.model_name} 已激活`)
      loadModels()
      loadAutoSwitchStatus()
      addSystemLog('action', `[ACTION] 手动切换至模型：${model.model_name}`)
    }
  } catch (error) {
    message.error('激活失败: ' + (error.message || ''))
  }
}

const deleteModel = (model) => {
  if (model.is_active === 1) { message.warning('无法删除激活中的模型'); return }
  dialog.warning({
    title: '确认删除',
    content: `确定要删除模型 "${model.model_name}" 吗？`,
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const result = await modelAPI.delete(model.id)
        if (result.success) { message.success('删除成功'); loadModels() }
      } catch (error) {
        message.error('删除失败')
      }
    }
  })
}

// 获取系统日志
const fetchSystemLogs = async () => {
  try {
    const result = await dashboardAPI.getSystemLogs(20)
    if (result.success && Array.isArray(result.data)) {
      systemLogs.value = result.data.map(log => ({
        type: log.level === 'ERROR' ? 'error' : log.level === 'WARNING' ? 'warning' : log.source === 'action' ? 'action' : 'system',
        message: `[${log.created_at}] ${log.message}`
      }))
    }
  } catch (error) { /* ignore */ }
}

// 定时刷新
const pollAll = () => {
  loadAutoSwitchStatus()
  loadTokenStats()
  fetchSystemLogs()
}

onMounted(() => {
  addSystemLog('system', '[SYSTEM] 模型管理控制台已就绪')
  loadProviders()
  loadModels()
  loadAutoSwitchStatus()
  loadTokenStats()
  loadTokenLogs()
  fetchSystemLogs()
  pollTimer = setInterval(pollAll, 5000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.model-manage-view { padding: 0; }

.stat-card-modern {
  padding: 1.25rem;
  border-radius: 1rem;
  transition: all 0.3s ease;
}
.stat-card-modern:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
}

.model-card-modern {
  padding: 1.75rem;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 1rem;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}
.model-card-modern:hover {
  border-color: #007857;
  box-shadow: 0 8px 24px rgba(0, 120, 87, 0.12);
  transform: translateY(-2px);
}
.model-card-modern.active {
  background: linear-gradient(135deg, #ecfdf5 0%, #f0fdf4 100%);
  border: 2px solid #10b981;
  box-shadow: 0 8px 24px rgba(16, 185, 129, 0.2);
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
  0%, 100% { opacity: 1; }
  50% { opacity: 0.8; }
}

.log-line { margin-bottom: 0.5rem; font-size: 0.75rem; line-height: 1.5; }
.log-system { color: #60a5fa; }
.log-progress { color: #fbbf24; }
.log-action { color: #34d399; }
.log-error { color: #f87171; }
.log-warning { color: #fbbf24; }

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #f1f1f1; border-radius: 3px; }
::-webkit-scrollbar-thumb { background: #888; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #555; }
</style>
