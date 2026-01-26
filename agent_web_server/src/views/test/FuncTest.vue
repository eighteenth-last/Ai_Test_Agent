<template>
  <div class="execute-case-view">
    <!-- 页面说明 -->
    <n-card>
      <template #header>
        <div class="flex items-center gap-2">
          <i class="fas fa-robot text-xl text-primary"></i>
          <span class="text-lg font-bold">执行用例 - AI 智能操作</span>
        </div>
      </template>
      <p class="text-gray-500">
        使用 Browser-Use 直接执行测试用例，无需生成代码，LLM 实时决策操作网页
      </p>
    </n-card>

    <!-- 测试用例列表 -->
    <n-card style="margin-top: 20px">
      <template #header>
        <span class="font-bold">测试用例列表</span>
      </template>

      <n-data-table
        :columns="columns"
        :data="testCases"
        :loading="loading"
        :row-key="row => row.id"
        striped
      />
    </n-card>

    <!-- 详情对话框 -->
    <n-modal v-model:show="dialogVisible" preset="card" title="测试用例详情" style="width: 800px">
      <n-descriptions v-if="currentCase" :column="1" label-placement="left" bordered>
        <n-descriptions-item label="ID">{{ currentCase.id }}</n-descriptions-item>
        <n-descriptions-item label="模块">{{ currentCase.module }}</n-descriptions-item>
        <n-descriptions-item label="用例名称">{{ currentCase.title }}</n-descriptions-item>
        <n-descriptions-item label="前置条件">{{ currentCase.precondition || '无' }}</n-descriptions-item>
        <n-descriptions-item label="测试步骤">
          <div v-for="(step, index) in currentCase.steps" :key="index">
            {{ index + 1 }}. {{ step }}
          </div>
        </n-descriptions-item>
        <n-descriptions-item label="预期结果">{{ currentCase.expected }}</n-descriptions-item>
        <n-descriptions-item label="关键词">{{ currentCase.keywords }}</n-descriptions-item>
        <n-descriptions-item label="优先级">{{ formatPriority(currentCase.priority) }}</n-descriptions-item>
        <n-descriptions-item label="用例类型">{{ currentCase.case_type }}</n-descriptions-item>
        <n-descriptions-item label="适用阶段">{{ currentCase.stage }}</n-descriptions-item>
      </n-descriptions>
    </n-modal>

    <!-- 执行用例对话框 -->
    <n-modal 
      v-model:show="executeDialogVisible" 
      preset="card" 
      :title="isExecuting ? '正在执行' : '执行用例'" 
      style="width: 1000px"
      :mask-closable="!isExecuting"
      :closable="!isExecuting"
    >
      <!-- 用例信息展示 -->
      <n-card v-if="selectedCase" size="small" style="margin-bottom: 20px">
        <template #header>
          <div class="flex items-center justify-between">
            <span><strong>测试用例:</strong> {{ selectedCase.title }}</span>
            <n-tag>{{ selectedCase.case_type }}</n-tag>
          </div>
        </template>
        <n-descriptions :column="1" size="small" label-placement="left" bordered>
          <n-descriptions-item label="模块">{{ selectedCase.module }}</n-descriptions-item>
          <n-descriptions-item label="前置条件">{{ selectedCase.precondition || '无' }}</n-descriptions-item>
          <n-descriptions-item label="测试步骤">
            <div v-for="(step, index) in selectedCase.steps" :key="index" style="margin: 2px 0">
              {{ index + 1 }}. {{ step }}
            </div>
          </n-descriptions-item>
          <n-descriptions-item label="预期结果">{{ selectedCase.expected }}</n-descriptions-item>
        </n-descriptions>
      </n-card>

      <n-divider />

      <!-- 执行配置 (未开始执行时显示) -->
      <n-card v-if="!isExecuting && !executionResult" size="small">
        <template #header>
          <strong>执行配置</strong>
        </template>
        <n-form :model="executeConfig" label-placement="left" label-width="120">
          <n-form-item label="无头模式">
            <n-switch v-model:value="executeConfig.headless" />
            <span class="tip">关闭后可看到浏览器操作过程</span>
          </n-form-item>
          
          <n-form-item label="最大步数">
            <n-input-number 
              v-model:value="executeConfig.max_steps" 
              :min="5" 
              :max="100" 
            />
            <span class="tip">防止无限循环</span>
          </n-form-item>
          
          <n-form-item label="视觉能力">
            <n-switch v-model:value="executeConfig.use_vision" />
            <span class="tip">启用后 LLM 可分析截图（成本略高）</span>
          </n-form-item>
        </n-form>
      </n-card>

      <!-- 执行中/执行完成状态显示 -->
      <div v-if="isExecuting || executionResult">
        <n-card size="small">
          <template #header>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <i class="fas fa-microchip"></i>
                <strong>代理交互</strong>
                <n-tag v-if="isExecuting && !isPaused" type="info" size="small">执行中...</n-tag>
                <n-tag v-else-if="isPaused" type="warning" size="small">已暂停</n-tag>
                <n-tag 
                  v-else-if="executionResult"
                  :type="executionResult.status === 'pass' ? 'success' : 'error'"
                  size="small"
                >
                  {{ executionResult.status === 'pass' ? '执行成功' : '执行失败' }}
                </n-tag>
              </div>
              <n-space v-if="isExecuting">
                <n-button 
                  v-if="!isPaused"
                  size="small" 
                  type="warning" 
                  @click="pauseExecution"
                  :loading="pauseLoading"
                >
                  暂停执行
                </n-button>
                <n-button 
                  v-else
                  size="small" 
                  type="success" 
                  @click="resumeExecution"
                  :loading="resumeLoading"
                >
                  继续执行
                </n-button>
                <n-button 
                  size="small" 
                  type="error" 
                  @click="stopExecution"
                  :loading="stopLoading"
                >
                  停止执行
                </n-button>
              </n-space>
            </div>
          </template>

          <!-- 执行过程显示 -->
          <div class="agent-output">
            <div v-if="isExecuting" class="executing-status">
              <n-spin size="large" />
              <p class="mt-4">AI 代理正在执行测试...</p>
              <p class="tip">请勿关闭此窗口</p>
            </div>

            <!-- 执行结果 -->
            <div v-else-if="executionResult">
              <n-alert
                :title="executionResult.status === 'pass' ? '✓ 测试执行成功' : '✗ 测试执行失败'"
                :type="executionResult.status === 'pass' ? 'success' : 'error'"
                style="margin-bottom: 20px"
              >
                <div class="mt-2">
                  <p><strong>总步数:</strong> {{ executionResult.total_steps }}</p>
                  <p><strong>耗时:</strong> {{ executionResult.duration }} 秒</p>
                  <p v-if="executionResult.final_url"><strong>最终URL:</strong> {{ executionResult.final_url }}</p>
                  <p v-if="executionResult.error_message" class="text-red-500 mt-2">
                    <strong>错误信息:</strong> {{ executionResult.error_message }}
                  </p>
                </div>
              </n-alert>

              <!-- 执行步骤详情 -->
              <n-collapse v-if="executionResult.history && executionResult.history.steps" accordion>
                <n-collapse-item 
                  v-for="(step, index) in executionResult.history.steps" 
                  :key="index"
                  :title="`步骤 ${step.step_number} - ${step.title || step.url || '执行中'}`"
                  :name="index"
                >
                  <div class="step-detail">
                    <p v-if="step.thinking">
                      <strong>💭 AI 思考:</strong><br/>
                      <span class="thinking-text">{{ step.thinking }}</span>
                    </p>
                    <p v-if="step.url">
                      <strong>🌐 页面:</strong> 
                      <a :href="step.url" target="_blank" class="url-link">{{ step.url }}</a>
                    </p>
                    <p v-if="step.actions && step.actions.length > 0">
                      <strong>⚡ 执行动作:</strong><br/>
                      <n-tag 
                        v-for="(action, idx) in step.actions" 
                        :key="idx"
                        size="small"
                        style="margin: 4px 4px 0 0"
                      >
                        {{ action.action_name }}
                      </n-tag>
                    </p>
                    <p v-if="step.timestamp" class="timestamp">
                      <strong>⏰ 时间:</strong> {{ step.timestamp }}
                    </p>
                  </div>
                </n-collapse-item>
              </n-collapse>
            </div>
          </div>
        </n-card>

        <!-- 任务输出 JSON -->
        <n-card v-if="executionResult" size="small" style="margin-top: 20px">
          <template #header>
            <strong>任务输出</strong>
          </template>
          <n-tabs type="line">
            <n-tab-pane name="history" tab="代理历史 JSON">
              <div class="json-output">
                <pre>{{ JSON.stringify(executionResult.history, null, 2) }}</pre>
              </div>
            </n-tab-pane>
          </n-tabs>
        </n-card>
      </div>

      <!-- 底部按钮 -->
      <template #footer>
        <n-space justify="end">
          <n-button v-if="!isExecuting && !executionResult" @click="executeDialogVisible = false">
            取消
          </n-button>
          <n-button 
            v-if="!isExecuting && !executionResult" 
            type="primary" 
            @click="confirmExecute"
            :loading="isExecuting"
          >
            <template #icon>
              <i class="fas fa-play"></i>
            </template>
            开始执行
          </n-button>
          <n-button v-if="executionResult" @click="executeDialogVisible = false">
            关闭
          </n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, h, reactive, onMounted } from 'vue'
import { 
  NCard, NButton, NDataTable, NModal, NDescriptions, NDescriptionsItem, 
  NTag, NForm, NFormItem, NSwitch, NInputNumber, NSpace, NDivider,
  NAlert, NCollapse, NCollapseItem, NTabs, NTabPane, NSpin,
  useMessage, useDialog
} from 'naive-ui'
import { testCaseAPI, testCodeAPI } from '@/api'

const message = useMessage()
const dialog = useDialog()

const testCases = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const currentCase = ref(null)
const executingCases = ref({})
const executeDialogVisible = ref(false)
const selectedCase = ref(null)
const isExecuting = ref(false)
const executionResult = ref(null)
const isPaused = ref(false)
const pauseLoading = ref(false)
const resumeLoading = ref(false)
const stopLoading = ref(false)
const currentTaskId = ref(null)

const executeConfig = reactive({
  headless: true,
  max_steps: 20,
  use_vision: false
})

// 优先级类型映射
const getPriorityType = (priority) => {
  const typeMap = { '1': 'error', '2': 'warning', '3': 'info', '4': 'default' }
  return typeMap[String(priority)] || 'default'
}

// 格式化优先级
const formatPriority = (priority) => {
  if (/^[1-4]$/.test(String(priority))) {
    return `${priority}级`
  }
  return priority
}

// 表格列定义
const columns = [
  { title: 'ID', key: 'id', width: 80 },
  { title: '模块', key: 'module', width: 120 },
  { title: '用例名称', key: 'title', width: 200, ellipsis: { tooltip: true } },
  { 
    title: '步骤', 
    key: 'steps',
    render(row) {
      return h('div', {}, row.steps?.map((step, index) => 
        h('div', { style: 'margin: 2px 0; font-size: 12px;' }, `${index + 1}. ${step}`)
      ))
    }
  },
  { 
    title: '优先级', 
    key: 'priority', 
    width: 100,
    render(row) {
      return h(NTag, { type: getPriorityType(row.priority), size: 'small' }, 
        { default: () => formatPriority(row.priority) }
      )
    }
  },
  { title: '用例类型', key: 'case_type', width: 100 },
  {
    title: '操作',
    key: 'actions',
    width: 200,
    fixed: 'right',
    render(row) {
      return h(NSpace, {}, {
        default: () => [
          h(NButton, { size: 'small', type: 'primary', onClick: () => viewDetail(row) }, 
            { default: () => '查看详情' }
          ),
          h(NButton, { 
            size: 'small', 
            type: 'success', 
            onClick: () => executeCase(row),
            loading: executingCases.value[row.id]
          }, { 
            default: () => '🤖 执行用例' 
          })
        ]
      })
    }
  }
]

// 加载测试用例列表
const loadTestCases = async () => {
  loading.value = true
  try {
    const result = await testCaseAPI.getList({ limit: 20, offset: 0 })
    if (result.success) {
      testCases.value = result.data
    }
  } catch (error) {
    message.error('加载测试用例失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// 查看详情
const viewDetail = (row) => {
  currentCase.value = row
  dialogVisible.value = true
}

// 执行用例 - 显示执行对话框
const executeCase = (testCase) => {
  selectedCase.value = testCase
  executionResult.value = null
  isExecuting.value = false
  executeDialogVisible.value = true
}

// 暂停执行
const pauseExecution = async () => {
  if (!currentTaskId.value) return
  
  pauseLoading.value = true
  try {
    const result = await testCodeAPI.pauseTask(currentTaskId.value)
    if (result.success) {
      isPaused.value = true
      message.success('已暂停执行')
    }
  } catch (error) {
    message.error('暂停失败: ' + (error.message || '未知错误'))
  } finally {
    pauseLoading.value = false
  }
}

// 恢复执行
const resumeExecution = async () => {
  if (!currentTaskId.value) return
  
  resumeLoading.value = true
  try {
    const result = await testCodeAPI.resumeTask(currentTaskId.value)
    if (result.success) {
      isPaused.value = false
      message.success('已恢复执行')
    }
  } catch (error) {
    message.error('恢复失败: ' + (error.message || '未知错误'))
  } finally {
    resumeLoading.value = false
  }
}

// 停止执行
const stopExecution = async () => {
  if (!currentTaskId.value) return
  
  dialog.warning({
    title: '确认停止',
    content: '确定要停止当前测试吗？停止后无法恢复。',
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      stopLoading.value = true
      try {
        const result = await testCodeAPI.stopTask(currentTaskId.value)
        if (result.success) {
          isExecuting.value = false
          isPaused.value = false
          message.success('已停止执行')
          
          executionResult.value = {
            status: 'fail',
            error_message: '用户手动停止',
            total_steps: 0,
            duration: 0,
            history: null
          }
        }
      } catch (error) {
        message.error('停止失败: ' + (error.message || '未知错误'))
      } finally {
        stopLoading.value = false
      }
    }
  })
}

// 确认执行
const confirmExecute = async () => {
  const caseId = selectedCase.value.id
  
  isExecuting.value = true
  isPaused.value = false
  currentTaskId.value = caseId
  executingCases.value[caseId] = true
  
  try {
    message.info('🤖 AI 正在接管浏览器执行测试...')
    
    const result = await testCodeAPI.executeBrowserUse(
      caseId,
      executeConfig.headless,
      executeConfig.max_steps,
      executeConfig.use_vision
    )
    
    if (result.success) {
      message.success('执行完成！')
      executionResult.value = result.data
    } else {
      message.error(result.message || '执行失败')
      
      executionResult.value = {
        status: 'fail',
        error_message: result.message,
        total_steps: 0,
        duration: 0,
        history: null
      }
    }
  } catch (error) {
    message.error('执行失败: ' + (error.message || '未知错误'))
    console.error(error)
    
    executionResult.value = {
      status: 'fail',
      error_message: error.message || '未知错误',
      total_steps: 0,
      duration: 0,
      history: null
    }
  } finally {
    isExecuting.value = false
    isPaused.value = false
    currentTaskId.value = null
    executingCases.value[caseId] = false
  }
}

onMounted(() => {
  loadTestCases()
})
</script>

<style scoped>
.execute-case-view {
  padding: 0;
}

.text-primary {
  color: #007857;
}

.tip {
  margin-left: 10px;
  font-size: 12px;
  color: #909399;
}

.agent-output {
  min-height: 200px;
}

.executing-status {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #606266;
}

.step-detail {
  padding: 12px;
  background-color: #f5f7fa;
  border-radius: 4px;
}

.step-detail p {
  margin: 8px 0;
  line-height: 1.6;
}

.thinking-text {
  color: #606266;
  background-color: #fff;
  padding: 8px 12px;
  border-radius: 4px;
  display: block;
  margin-top: 4px;
  border-left: 3px solid #007857;
}

.url-link {
  color: #007857;
  text-decoration: none;
}

.url-link:hover {
  text-decoration: underline;
}

.timestamp {
  font-size: 12px;
  color: #909399;
}

.json-output {
  max-height: 400px;
  overflow: auto;
  background-color: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
}

.json-output pre {
  margin: 0;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.5;
  color: #303133;
}
</style>
