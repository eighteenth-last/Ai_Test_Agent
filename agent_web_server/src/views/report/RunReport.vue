<template>
  <div class="run-report-view">
    <!-- 页面说明 -->
    <n-card>
      <template #header>
        <div class="flex items-center gap-2">
          <i class="fas fa-file-alt text-xl text-primary"></i>
          <span class="text-lg font-bold">测试报告管理</span>
        </div>
      </template>
      <p class="text-gray-500">
        查看和管理所有测试执行的报告，包括执行结果、日志详情等
      </p>
    </n-card>

    <!-- 筛选区域 -->
    <n-card style="margin-top: 20px">
      <n-space vertical :size="12">
        <n-space align="center" :size="16" :wrap="false">
          <!-- 状态筛选 -->
          <div class="filter-item">
            <span class="filter-label">状态</span>
            <n-select 
              v-model:value="filters.status" 
              :options="statusOptions"
              clearable
              placeholder="全部"
              style="width: 140px"
            />
          </div>

          <!-- 测试名称搜索 -->
          <div class="filter-item" style="flex: 1; min-width: 280px; max-width: 400px;">
            <span class="filter-label">测试名称</span>
            <n-input 
              v-model:value="filters.search" 
              placeholder="搜索测试用例名称"
              clearable
            >
              <template #prefix>
                <i class="fas fa-search text-gray-400"></i>
              </template>
            </n-input>
          </div>

          <!-- 日期范围 -->
          <div class="filter-item">
            <span class="filter-label">日期范围</span>
            <n-date-picker
              v-model:value="filters.dateRange"
              type="daterange"
              clearable
              start-placeholder="Start Date"
              end-placeholder="End Date"
              style="width: 320px"
            />
          </div>
        </n-space>
      </n-space>
    </n-card>

    <!-- 报告列表 -->
    <n-card style="margin-top: 20px">
      <template #header>
        <span class="font-bold">报告列表</span>
      </template>

      <n-data-table
        :columns="columns"
        :data="reports"
        :loading="loading"
        :row-key="row => row.id"
        striped
      />

      <!-- 分页 -->
      <div style="margin-top: 20px; display: flex; justify-content: flex-end;">
        <n-pagination
          v-model:page="currentPage"
          v-model:page-size="pageSize"
          :item-count="total"
          :page-sizes="[10, 20, 50]"
          show-size-picker
          @update:page="loadReports"
          @update:page-size="handlePageSizeChange"
        />
      </div>
    </n-card>

    <!-- 报告详情对话框 -->
    <n-modal 
      v-model:show="detailDialogVisible" 
      preset="card" 
      title="测试报告详情" 
      style="width: 900px"
    >
      <n-spin :show="detailLoading">
        <div v-if="currentReport">
          <!-- 基本信息 -->
          <n-card size="small" style="margin-bottom: 20px">
            <template #header>
              <div class="flex items-center justify-between">
                <span><strong>基本信息</strong></span>
                <n-tag :type="currentReport.status === 'pass' ? 'success' : 'error'">
                  {{ currentReport.status === 'pass' ? '通过' : '失败' }}
                </n-tag>
              </div>
            </template>
            <n-descriptions :column="2" label-placement="left" bordered>
              <n-descriptions-item label="报告ID">{{ currentReport.id }}</n-descriptions-item>
              <n-descriptions-item label="测试用例">{{ currentReport.case_name }}</n-descriptions-item>
              <n-descriptions-item label="执行时间">{{ currentReport.created_at }}</n-descriptions-item>
              <n-descriptions-item label="耗时">{{ currentReport.duration }} 秒</n-descriptions-item>
              <n-descriptions-item label="总步数">{{ currentReport.total_steps }}</n-descriptions-item>
              <n-descriptions-item label="最终URL">
                <a v-if="currentReport.final_url" :href="currentReport.final_url" target="_blank" class="url-link">
                  {{ currentReport.final_url }}
                </a>
                <span v-else class="text-gray-400">-</span>
              </n-descriptions-item>
            </n-descriptions>
          </n-card>

          <!-- 错误信息 (如果有) -->
          <n-alert 
            v-if="currentReport.error_message" 
            title="错误信息" 
            type="error" 
            style="margin-bottom: 20px"
          >
            {{ currentReport.error_message }}
          </n-alert>

          <!-- 执行步骤详情 -->
          <n-card v-if="currentReport.history" size="small" style="margin-bottom: 20px">
            <template #header>
              <strong>执行步骤详情</strong>
            </template>
            <n-collapse accordion>
              <n-collapse-item 
                v-for="(step, index) in (currentReport.history.steps || [])" 
                :key="index"
                :title="`步骤 ${step.step_number || (index + 1)} - ${step.title || step.url || '执行中'}`"
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
                      {{ action.action_name || action }}
                    </n-tag>
                  </p>
                  <p v-if="step.timestamp" class="timestamp">
                    <strong>⏰ 时间:</strong> {{ step.timestamp }}
                  </p>
                </div>
              </n-collapse-item>
            </n-collapse>
          </n-card>

          <!-- 原始数据 -->
          <n-card size="small">
            <template #header>
              <strong>原始数据</strong>
            </template>
            <n-tabs type="line">
              <n-tab-pane name="history" tab="执行历史 JSON">
                <div class="json-output">
                  <pre v-if="currentReport.execution_log">{{ formatExecutionLog(currentReport.execution_log) }}</pre>
                  <n-empty v-else description="暂无执行历史数据" size="small">
                    <template #icon>
                      <i class="fas fa-info-circle text-slate-400"></i>
                    </template>
                  </n-empty>
                </div>
              </n-tab-pane>
              <n-tab-pane name="raw" tab="完整报告 JSON">
                <div class="json-output">
                  <pre>{{ JSON.stringify(currentReport, null, 2) }}</pre>
                </div>
              </n-tab-pane>
            </n-tabs>
          </n-card>
        </div>
      </n-spin>
      
      <template #footer>
        <n-space justify="end">
          <n-button type="primary" @click="downloadReport">
            <template #icon>
              <i class="fas fa-download"></i>
            </template>
            下载报告
          </n-button>
          <n-button @click="detailDialogVisible = false">关闭</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, h, reactive } from 'vue'
import { 
  NCard, NButton, NDataTable, NModal, NDescriptions, NDescriptionsItem, 
  NTag, NForm, NFormItem, NInput, NSelect, NDatePicker, NSpace,
  NAlert, NCollapse, NCollapseItem, NTabs, NTabPane, NSpin, NPagination, NEmpty,
  useMessage
} from 'naive-ui'
import { testReportAPI } from '@/api'
import { useLazyLoad } from '@/composables/useLazyLoad'

const message = useMessage()

// 格式化日期
const formatDate = (timestamp) => {
  if (!timestamp) return null
  const date = new Date(timestamp)
  return date.toISOString().split('T')[0]
}

// 包装 API 调用以适配 useLazyLoad 并处理数据转换
const fetchReportsWrapper = async (params) => {
  // 处理日期范围
  const apiParams = { ...params }
  if (apiParams.dateRange && apiParams.dateRange.length === 2) {
    apiParams.start_date = formatDate(apiParams.dateRange[0])
    apiParams.end_date = formatDate(apiParams.dateRange[1])
    delete apiParams.dateRange
  }

  const result = await testReportAPI.getList(apiParams)
  
  if (result.success) {
    // 解析 summary 字段并提取状态信息
    const list = (result.data || []).map(report => {
      let summary = {}
      try {
        summary = typeof report.summary === 'string' ? JSON.parse(report.summary) : report.summary
      } catch (e) {
        console.error('Failed to parse summary:', e)
      }
      
      // 判断状态：优先 summary.status，其次根据 pass/fail 数量推导
      let status = 'fail'
      if (summary.status) {
        if (summary.status === '通过' || summary.status === 'pass') {
          status = 'pass'
        } else if (summary.status === '失败' || summary.status === 'fail') {
          status = 'fail'
        }
      } else if (summary.total !== undefined) {
        if (summary.fail === 0 && summary.total > 0) {
          status = 'pass'
        } else {
          status = 'fail'
        }
      }
      
      // 获取总步数，优先使用数据库字段，其次从 summary，最后从 execution_log 提取
      let totalSteps = report.total_steps || summary.total_steps || 0
      if (!totalSteps && report.execution_log) {
        try {
          const logData = typeof report.execution_log === 'string' 
            ? JSON.parse(report.execution_log) 
            : report.execution_log
          
          if (logData) {
            if (logData.steps && Array.isArray(logData.steps)) {
              totalSteps = logData.steps.length
            } else if (logData.total_steps) {
              totalSteps = logData.total_steps
            } else if (logData.step_count) {
              totalSteps = logData.step_count
            }
          }
        } catch (e) {
          console.error('Failed to parse execution_log for steps:', e)
        }
      }
      
      return {
        ...report,
        status: status,
        duration: summary.duration || 0,
        total_steps: totalSteps,
        case_name: report.title || '-',
        case_type: report.case_type || '功能测试',
        execution_mode: report.execution_mode || summary.execution_mode || '单量'
      }
    })

    return {
      success: true,
      data: list,
      total: result.total
    }
  }
  return result
}

// 筛选条件
const filters = reactive({
  status: null,
  search: '',
  dateRange: null
})

// 使用懒加载
const {
  data: reports,
  loading,
  currentPage,
  pageSize,
  total,
  refresh,
  goToPage,
  changePageSize: handlePageSizeChange
} = useLazyLoad({
  fetchFunction: fetchReportsWrapper,
  pageSize: 10,
  filters,
  autoLoad: true,
  debounceDelay: 500
})

const loadReports = (page) => {
  if (typeof page === 'number') {
    goToPage(page)
  } else {
    refresh()
  }
}

// 状态选项
const statusOptions = [
  { label: '全部', value: null },
  { label: '通过', value: 'pass' },
  { label: '失败', value: 'fail' }
]

// 详情对话框
const detailDialogVisible = ref(false)
const detailLoading = ref(false)
const currentReport = ref(null)

// 状态类型映射
const getStatusType = (status) => {
  return status === 'pass' ? 'success' : 'error'
}

// 格式化状态
const formatStatus = (status) => {
  return status === 'pass' ? '通过' : '失败'
}

// 格式化执行日志
const formatExecutionLog = (log) => {
  if (!log) return '暂无数据'
  
  try {
    // 如果是 JSON 字符串，尝试解析
    const parsed = typeof log === 'string' ? JSON.parse(log) : log
    return JSON.stringify(parsed, null, 2)
  } catch (e) {
    // 如果不是 JSON，直接返回
    return log
  }
}

// 表格列定义
const columns = [
  { title: 'ID', key: 'id', width: 80 },
  { title: '测试用例', key: 'case_name', width: 350, ellipsis: { tooltip: true } },
  { 
    title: '测试类型', 
    key: 'case_type', 
    width: 120,
    render(row) {
      const type = row.case_type || '功能测试'
      const typeMap = {
        '功能测试': 'info',
        '接口测试': 'warning',
        '单元测试': 'success',
        '性能测试': 'error',
        '安全测试': 'error'
      }
      return h(NTag, { type: typeMap[type] || 'default', size: 'small' }, 
        { default: () => type }
      )
    }
  },
  { 
    title: '执行模式', 
    key: 'execution_mode', 
    width: 100,
    render(row) {
      const mode = row.execution_mode || '单量'
      return h(NTag, { type: mode === '批量' ? 'warning' : 'default', size: 'small' }, 
        { default: () => mode }
      )
    }
  },
  { 
    title: '状态', 
    key: 'status', 
    width: 100,
    render(row) {
      return h(NTag, { type: getStatusType(row.status), size: 'small' }, 
        { default: () => formatStatus(row.status) }
      )
    }
  },
  { 
    title: '执行时间', 
    key: 'created_at', 
    width: 200,
    render(row) {
      if (!row.created_at) return '-'
      try {
        const date = new Date(row.created_at)
        return date.toLocaleString()
      } catch (e) {
        return row.created_at
      }
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 220,
    fixed: 'right',
    render(row) {
      return h(NSpace, {}, {
        default: () => [
          h(NButton, { size: 'small', type: 'primary', onClick: () => viewDetail(row) }, 
            { default: () => '查看详情' }
          ),
          h(NButton, { size: 'small', type: 'info', onClick: () => downloadSingleReport(row) }, 
            { default: () => '下载' }
          ),
          h(NButton, { size: 'small', type: 'error', onClick: () => deleteReport(row) }, 
            { default: () => '删除' }
          )
        ]
      })
    }
  }
]

// 查看详情
const viewDetail = async (row) => {
  detailDialogVisible.value = true
  detailLoading.value = true
  
  try {
    const result = await testReportAPI.getById(row.id)
    if (result.success) {
      const data = result.data
      
      // 解析 summary 字段
      let summary = {}
      try {
        summary = typeof data.summary === 'string' ? JSON.parse(data.summary) : data.summary
      } catch (e) {
        console.error('Failed to parse summary:', e)
      }
      
      // 获取总步数，优先使用数据库字段，其次从 summary，最后从 execution_log 提取
      let totalSteps = data.total_steps || summary.total_steps || 0
      if (!totalSteps && data.execution_log) {
        try {
          const logData = typeof data.execution_log === 'string' ? JSON.parse(data.execution_log) : data.execution_log
          // 尝试从不同可能的字段中获取步数
          if (logData.steps && Array.isArray(logData.steps)) {
            totalSteps = logData.steps.length
          } else if (logData.total_steps) {
            totalSteps = logData.total_steps
          } else if (logData.step_count) {
            totalSteps = logData.step_count
          }
        } catch (e) {
          console.error('Failed to parse execution_log:', e)
        }
      }
      
      // 判断状态：优先 summary.status，其次根据 pass/fail 数量推导
      let status = 'fail'
      if (summary.status) {
        if (summary.status === '通过' || summary.status === 'pass') {
          status = 'pass'
        } else if (summary.status === '失败' || summary.status === 'fail') {
          status = 'fail'
        }
      } else if (summary.total !== undefined) {
        if (summary.fail === 0 && summary.total > 0) {
          status = 'pass'
        } else {
          status = 'fail'
        }
      }
      
      currentReport.value = {
        ...data,
        status: status,
        duration: summary.duration || 0,
        total_steps: totalSteps,
        case_name: data.title || '-'
      }
    } else {
      message.error('获取报告详情失败')
    }
  } catch (error) {
    message.error('获取报告详情失败')
    console.error(error)
  } finally {
    detailLoading.value = false
  }
}

// 下载报告
const downloadReport = () => {
  if (!currentReport.value) return
  
  const dataStr = JSON.stringify(currentReport.value, null, 2)
  const blob = new Blob([dataStr], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `test_report_${currentReport.value.id}.json`
  link.click()
  URL.revokeObjectURL(url)
  
  message.success('报告下载成功')
}

// 下载单个报告
const downloadSingleReport = async (row) => {
  try {
    const result = await testReportAPI.getById(row.id)
    if (result.success) {
      const dataStr = JSON.stringify(result.data, null, 2)
      const blob = new Blob([dataStr], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `test_report_${row.id}.json`
      link.click()
      URL.revokeObjectURL(url)
      
      message.success('报告下载成功')
    }
  } catch (error) {
    message.error('下载失败')
    console.error(error)
  }
}

// 删除报告
const deleteReport = async (row) => {
  try {
    const result = await testReportAPI.delete(row.id)
    if (result.success) {
      message.success('删除成功')
      loadReports()
    } else {
      message.error(result.message || '删除失败')
    }
  } catch (error) {
    message.error('删除失败')
    console.error(error)
  }
}


</script>

<style scoped>
.run-report-view {
  padding: 0;
}

.text-primary {
  color: #007857;
}

/* 筛选区域样式 */
.filter-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-label {
  font-size: 14px;
  color: #333;
  font-weight: 500;
  white-space: nowrap;
  min-width: 70px;
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
