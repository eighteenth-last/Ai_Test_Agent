<template>
  <div class="execute-case-view">
    <el-card>
      <template #header>
        <h3>执行用例 - AI 智能操作</h3>
        <p style="font-size: 14px; color: #909399; margin-top: 8px">
          使用 Browser-Use 直接执行测试用例，无需生成代码，LLM 实时决策操作网页
        </p>
      </template>
    </el-card>

    <!-- 测试用例列表 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <h3>测试用例列表</h3>
          <el-button size="small" @click="loadTestCases">刷新</el-button>
        </div>
      </template>
      
      <el-table :data="testCases" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="module" label="模块" width="120" />
        <el-table-column prop="title" label="用例名称" width="200" />
        <el-table-column label="步骤">
          <template #default="{ row }">
            <div v-for="(step, index) in row.steps" :key="index" style="margin: 2px 0">
              {{ index + 1 }}. {{ step }}
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="100" />
        <el-table-column prop="case_type" label="用例类型" width="120" />
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="viewDetail(row)">
              查看详情
            </el-button>
            <el-button 
              size="small" 
              type="success" 
              @click="executeCase(row)"
              :loading="executingCases[row.id]"
            >
              🤖 执行用例
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog v-model="dialogVisible" title="测试用例详情" width="800px">
      <el-descriptions :column="1" border v-if="currentCase">
        <el-descriptions-item label="ID">{{ currentCase.id }}</el-descriptions-item>
        <el-descriptions-item label="模块">{{ currentCase.module }}</el-descriptions-item>
        <el-descriptions-item label="用例名称">{{ currentCase.title }}</el-descriptions-item>
        <el-descriptions-item label="前置条件">{{ currentCase.precondition || '无' }}</el-descriptions-item>
        <el-descriptions-item label="测试步骤">
          <div v-for="(step, index) in currentCase.steps" :key="index">
            {{ index + 1 }}. {{ step }}
          </div>
        </el-descriptions-item>
        <el-descriptions-item label="预期结果">{{ currentCase.expected }}</el-descriptions-item>
        <el-descriptions-item label="关键词">{{ currentCase.keywords }}</el-descriptions-item>
        <el-descriptions-item label="优先级">{{ currentCase.priority }}</el-descriptions-item>
        <el-descriptions-item label="用例类型">{{ currentCase.case_type }}</el-descriptions-item>
        <el-descriptions-item label="适用阶段">{{ currentCase.stage }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <!-- 执行用例对话框 (新设计) -->
    <el-dialog 
      v-model="executeDialogVisible" 
      :title="isExecuting ? '正在执行' : '执行用例'" 
      width="1000px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="!isExecuting"
    >
      <!-- 用例信息展示 -->
      <el-card v-if="selectedCase" style="margin-bottom: 20px" shadow="never">
        <template #header>
          <div style="display: flex; align-items: center; justify-content: space-between;">
            <span><strong>测试用例:</strong> {{ selectedCase.title }}</span>
            <el-tag>{{ selectedCase.case_type }}</el-tag>
          </div>
        </template>
        <el-descriptions :column="1" size="small" border>
          <el-descriptions-item label="模块">{{ selectedCase.module }}</el-descriptions-item>
          <el-descriptions-item label="前置条件">{{ selectedCase.precondition || '无' }}</el-descriptions-item>
          <el-descriptions-item label="测试步骤">
            <div v-for="(step, index) in selectedCase.steps" :key="index" style="margin: 2px 0">
              {{ index + 1 }}. {{ step }}
            </div>
          </el-descriptions-item>
          <el-descriptions-item label="预期结果">{{ selectedCase.expected }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-divider />

      <!-- 执行配置 (未开始执行时显示) -->
      <el-card v-if="!isExecuting && !executionResult" shadow="never">
        <template #header>
          <strong>执行配置</strong>
        </template>
        <el-form :model="executeConfig" label-width="120px">
          <el-form-item label="无头模式">
            <el-switch v-model="executeConfig.headless" />
            <span class="tip">关闭后可看到浏览器操作过程</span>
          </el-form-item>
          
          <el-form-item label="最大步数">
            <el-input-number 
              v-model="executeConfig.max_steps" 
              :min="5" 
              :max="100" 
            />
            <span class="tip">防止无限循环</span>
          </el-form-item>
          
          <el-form-item label="视觉能力">
            <el-switch v-model="executeConfig.use_vision" />
            <span class="tip">启用后 LLM 可分析截图（成本略高）</span>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 执行中/执行完成状态显示 -->
      <div v-if="isExecuting || executionResult">
        <!-- 代理交互输出 -->
        <el-card shadow="never">
          <template #header>
            <div style="display: flex; align-items: center; justify-content: space-between;">
              <div style="display: flex; align-items: center;">
                <i class="el-icon-cpu" style="margin-right: 8px" />
                <strong>代理交互</strong>
                <el-tag v-if="isExecuting && !isPaused" type="info" size="small" style="margin-left: 10px">
                  执行中...
                </el-tag>
                <el-tag v-else-if="isPaused" type="warning" size="small" style="margin-left: 10px">
                  已暂停
                </el-tag>
                <el-tag 
                  v-else-if="executionResult"
                  :type="executionResult.status === 'pass' ? 'success' : 'danger'"
                  size="small"
                  style="margin-left: 10px"
                >
                  {{ executionResult.status === 'pass' ? '执行成功' : '执行失败' }}
                </el-tag>
              </div>
              <div v-if="isExecuting">
                <el-button 
                  v-if="!isPaused"
                  size="small" 
                  type="warning" 
                  @click="pauseExecution"
                  :loading="pauseLoading"
                >
                  暂停执行
                </el-button>
                <el-button 
                  v-else
                  size="small" 
                  type="success" 
                  @click="resumeExecution"
                  :loading="resumeLoading"
                >
                  继续执行
                </el-button>
                <el-button 
                  size="small" 
                  type="danger" 
                  @click="stopExecution"
                  :loading="stopLoading"
                >
                  停止执行
                </el-button>
              </div>
            </div>
          </template>

          <!-- 执行过程显示 -->
          <div class="agent-output">
            <div v-if="isExecuting" class="executing-status">
              <el-icon class="is-loading" style="font-size: 24px; margin-bottom: 10px">
                <Loading />
              </el-icon>
              <p>AI 代理正在执行测试...</p>
              <p class="tip">请勿关闭此窗口</p>
            </div>

            <!-- 执行结果 -->
            <div v-else-if="executionResult">
              <el-alert
                :title="executionResult.status === 'pass' ? '✓ 测试执行成功' : '✗ 测试执行失败'"
                :type="executionResult.status === 'pass' ? 'success' : 'error'"
                :closable="false"
                style="margin-bottom: 20px"
              >
                <template #default>
                  <div style="margin-top: 10px">
                    <p><strong>总步数:</strong> {{ executionResult.total_steps }}</p>
                    <p><strong>耗时:</strong> {{ executionResult.duration }} 秒</p>
                    <p v-if="executionResult.final_url"><strong>最终URL:</strong> {{ executionResult.final_url }}</p>
                    <p v-if="executionResult.error_message" style="color: #f56c6c; margin-top: 10px">
                      <strong>错误信息:</strong> {{ executionResult.error_message }}
                    </p>
                  </div>
                </template>
              </el-alert>

              <!-- 执行步骤详情 -->
              <el-collapse v-if="executionResult.history && executionResult.history.steps" accordion>
                <el-collapse-item 
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
                      <el-tag 
                        v-for="(action, idx) in step.actions" 
                        :key="idx"
                        size="small"
                        style="margin: 4px 4px 0 0"
                      >
                        {{ action.action_name }}
                      </el-tag>
                    </p>
                    <p v-if="step.timestamp" class="timestamp">
                      <strong>⏰ 时间:</strong> {{ step.timestamp }}
                    </p>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>
          </div>
        </el-card>

        <!-- 任务输出 (仅执行完成后显示) -->
        <el-card v-if="executionResult" shadow="never" style="margin-top: 20px">
          <template #header>
            <strong>任务输出</strong>
          </template>

          <el-tabs>
            <el-tab-pane label="代理历史 JSON">
              <div class="json-output">
                <pre>{{ JSON.stringify(executionResult.history, null, 2) }}</pre>
              </div>
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </div>

      <!-- 底部按钮 -->
      <template #footer>
        <el-button v-if="!isExecuting && !executionResult" @click="executeDialogVisible = false">
          取消
        </el-button>
        <el-button 
          v-if="!isExecuting && !executionResult" 
          type="primary" 
          @click="confirmExecute"
          :loading="isExecuting"
        >
          开始执行
        </el-button>
        <el-button v-if="executionResult" @click="executeDialogVisible = false">
          关闭
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { testCaseAPI, testCodeAPI } from '@/api'

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

// 加载测试用例列表
const loadTestCases = async () => {
  loading.value = true
  try {
    const result = await testCaseAPI.getList({ limit: 20, offset: 0 })
    if (result.success) {
      testCases.value = result.data
    }
  } catch (error) {
    ElMessage.error('加载测试用例失败')
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
      ElMessage.success('已暂停执行')
    }
  } catch (error) {
    ElMessage.error('暂停失败: ' + (error.message || '未知错误'))
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
      ElMessage.success('已恢复执行')
    }
  } catch (error) {
    ElMessage.error('恢复失败: ' + (error.message || '未知错误'))
  } finally {
    resumeLoading.value = false
  }
}

// 停止执行
const stopExecution = async () => {
  if (!currentTaskId.value) return
  
  try {
    await ElMessageBox.confirm(
      '确定要停止当前测试吗？停止后无法恢复。',
      '确认停止',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    stopLoading.value = true
    const result = await testCodeAPI.stopTask(currentTaskId.value)
    if (result.success) {
      isExecuting.value = false
      isPaused.value = false
      ElMessage.success('已停止执行')
      
      // 创建停止结果
      executionResult.value = {
        status: 'fail',
        error_message: '用户手动停止',
        total_steps: 0,
        duration: 0,
        history: null
      }
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('停止失败: ' + (error.message || '未知错误'))
    }
  } finally {
    stopLoading.value = false
  }
}

// 确认执行
const confirmExecute = async () => {
  const caseId = selectedCase.value.id
  
  // 设置执行状态
  isExecuting.value = true
  isPaused.value = false
  currentTaskId.value = caseId
  executingCases.value[caseId] = true
  
  try {
    ElMessage.info('🤖 AI 正在接管浏览器执行测试...')
    
    const result = await testCodeAPI.executeBrowserUse(
      caseId,
      executeConfig.headless,
      executeConfig.max_steps,
      executeConfig.use_vision
    )
    
    if (result.success) {
      ElMessage.success('执行完成！')
      executionResult.value = result.data
    } else {
      ElMessage.error(result.message || '执行失败')
      
      // 创建错误结果
      executionResult.value = {
        status: 'fail',
        error_message: result.message,
        total_steps: 0,
        duration: 0,
        history: null
      }
    }
  } catch (error) {
    ElMessage.error('执行失败: ' + (error.message || '未知错误'))
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
  padding: 20px;
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
  border-left: 3px solid #409eff;
}

.url-link {
  color: #409eff;
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
