<template>
  <div class="security-test">
    <!-- 顶部操作区 -->
    <div class="glass-card p-5 mb-5">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-3">
          <i class="fas fa-shield-halved text-xl text-[#007857]"></i>
          <span class="text-lg font-bold text-slate-700">安全测试</span>
        </div>
        <n-button v-if="running" type="error" size="small" @click="handleStop">
          <template #icon><i class="fas fa-stop"></i></template>
          停止扫描
        </n-button>
      </div>

      <!-- 扫描类型 Tab -->
      <n-tabs v-model:value="activeTab" type="segment" animated>
        <n-tab-pane name="web_scan" tab="Web 扫描">
          <div class="mt-4 space-y-3">
            <n-input v-model:value="form.target" placeholder="目标 URL（仅限内网地址，如 http://localhost:8080）" />
            <div class="flex gap-3">
              <n-checkbox v-model:checked="form.deepScan">深度扫描</n-checkbox>
              <n-checkbox v-model:checked="form.sqlmapVerify">sqlmap 二次验证</n-checkbox>
            </div>
          </div>
        </n-tab-pane>

        <n-tab-pane name="api_attack" tab="API 攻击">
          <div class="mt-4 space-y-3">
            <n-input v-model:value="form.target" placeholder="API Base URL（如 http://localhost:8080）" />
            <n-input v-model:value="form.specVersionId" placeholder="接口文件版本 ID（可选，从接口文件管理获取）" />
            <n-input v-model:value="form.authToken" placeholder="Authorization Token（可选）" />
          </div>
        </n-tab-pane>

        <n-tab-pane name="dependency_scan" tab="依赖扫描">
          <div class="mt-4 space-y-3">
            <n-input v-model:value="form.target" placeholder="项目路径或描述" />
            <n-input v-model:value="form.pythonReq" placeholder="requirements.txt 路径（可选）" />
            <n-input v-model:value="form.nodeDir" placeholder="Node.js 项目目录（可选）" />
            <n-input v-model:value="form.trivyTarget" placeholder="Trivy 扫描目标（可选，如 Dockerfile 路径）" />
          </div>
        </n-tab-pane>

        <n-tab-pane name="baseline_check" tab="基线检测">
          <div class="mt-4 space-y-3">
            <n-input v-model:value="form.target" placeholder="目标 URL（仅限内网地址，如 http://localhost:8080）" />
            <p class="text-xs text-slate-400">检查安全响应头、Cookie 安全属性、HTTPS、信息泄露、敏感路径等</p>
          </div>
        </n-tab-pane>
      </n-tabs>

      <div class="mt-4 flex justify-end">
        <n-button type="primary" :loading="starting" :disabled="running" @click="handleRun">
          <template #icon><i class="fas fa-play"></i></template>
          开始扫描
        </n-button>
      </div>
    </div>

    <!-- 安全测试用例任务列表 -->
    <div class="glass-card p-5 mb-5">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-3">
          <i class="fas fa-clipboard-check text-[#007857]"></i>
          <span class="font-bold text-slate-700">安全测试用例任务</span>
          <n-tag size="small" :bordered="false">{{ caseStats.all }} 条</n-tag>
        </div>
        <n-button size="small" quaternary @click="loadSecurityCases">
          <template #icon><i class="fas fa-refresh"></i></template>
          刷新
        </n-button>
      </div>

      <!-- 状态筛选 -->
      <div class="flex items-center gap-2 mb-4">
        <n-button
          v-for="f in caseFilters" :key="f.value"
          :type="caseFilterStatus === f.value ? 'primary' : 'default'"
          size="small"
          :secondary="caseFilterStatus === f.value"
          @click="caseFilterStatus = f.value; loadSecurityCases()"
        >
          {{ f.label }}
          <n-badge :value="f.count" :max="999" :offset="[8, -4]" :type="f.badgeType" />
        </n-button>
        <div class="flex-1"></div>
        <n-input v-model:value="caseSearch" placeholder="搜索用例..." size="small" style="width: 200px" clearable @clear="loadSecurityCases" @keyup.enter="loadSecurityCases">
          <template #prefix><i class="fas fa-search text-slate-400"></i></template>
        </n-input>
      </div>

      <!-- 用例表格 -->
      <n-data-table
        :columns="caseColumns"
        :data="securityCases"
        :loading="casesLoading"
        :pagination="casePagination"
        size="small"
        striped
        @update:page="handleCasePageChange"
      />
    </div>

    <!-- 执行中状态 -->
    <div v-if="running" class="glass-card p-5 mb-5">
      <div class="flex items-center gap-3 mb-3">
        <n-spin size="small" />
        <span class="font-bold text-slate-700">扫描进行中...</span>
        <n-tag :type="stageTagType" size="small">{{ stageLabel }}</n-tag>
      </div>
      <n-progress type="line" :percentage="currentProgress" :indicator-placement="'inside'" processing />
      <div class="mt-2 text-xs text-slate-400">
        当前漏洞数: {{ currentVulnCount }} | 任务 ID: {{ currentTaskId }}
      </div>
    </div>

    <!-- 结果展示 -->
    <div v-if="result" class="space-y-5">
      <!-- 风险评分卡片 -->
      <div class="glass-card p-5">
        <div class="flex items-center justify-between mb-4">
          <span class="font-bold text-slate-700">风险评估</span>
          <n-tag :type="riskTagType" size="large">
            {{ result.risk_level }} 级 · {{ result.risk_score }} 分
          </n-tag>
        </div>
        <div class="grid grid-cols-5 gap-3 text-center">
          <div class="p-3 rounded-lg bg-red-50">
            <div class="text-2xl font-bold text-red-600">{{ vulnSummary.critical }}</div>
            <div class="text-xs text-slate-500">严重</div>
          </div>
          <div class="p-3 rounded-lg bg-orange-50">
            <div class="text-2xl font-bold text-orange-600">{{ vulnSummary.high }}</div>
            <div class="text-xs text-slate-500">高危</div>
          </div>
          <div class="p-3 rounded-lg bg-yellow-50">
            <div class="text-2xl font-bold text-yellow-600">{{ vulnSummary.medium }}</div>
            <div class="text-xs text-slate-500">中危</div>
          </div>
          <div class="p-3 rounded-lg bg-blue-50">
            <div class="text-2xl font-bold text-blue-600">{{ vulnSummary.low }}</div>
            <div class="text-xs text-slate-500">低危</div>
          </div>
          <div class="p-3 rounded-lg bg-slate-50">
            <div class="text-2xl font-bold text-slate-600">{{ vulnSummary.info }}</div>
            <div class="text-xs text-slate-500">信息</div>
          </div>
        </div>
      </div>

      <!-- 漏洞列表 -->
      <div v-if="result.vulnerabilities && result.vulnerabilities.length" class="glass-card p-5">
        <div class="flex items-center justify-between mb-4">
          <span class="font-bold text-slate-700">漏洞详情 ({{ result.vulnerabilities.length }})</span>
        </div>
        <n-data-table
          :columns="vulnColumns"
          :data="result.vulnerabilities"
          :pagination="{ pageSize: 10 }"
          :row-class-name="vulnRowClass"
          size="small"
          striped
        />
      </div>

      <!-- Markdown 报告 -->
      <div v-if="result.report_content" class="glass-card p-5">
        <div class="flex items-center justify-between mb-4">
          <span class="font-bold text-slate-700">扫描报告</span>
          <n-button size="small" @click="showReport = !showReport">
            {{ showReport ? '收起' : '展开' }}
          </n-button>
        </div>
        <div v-if="showReport" class="markdown-body prose max-w-none" v-html="renderedReport"></div>
      </div>
    </div>

    <!-- 历史记录 -->
    <div class="glass-card p-5 mt-5">
      <div class="flex items-center justify-between mb-4">
        <span class="font-bold text-slate-700">扫描历史</span>
        <n-button size="small" quaternary @click="loadHistory">
          <template #icon><i class="fas fa-refresh"></i></template>
          刷新
        </n-button>
      </div>
      <n-data-table
        :columns="historyColumns"
        :data="historyList"
        :loading="historyLoading"
        :pagination="{ pageSize: 10 }"
        size="small"
        striped
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, h } from 'vue'
import { useMessage } from 'naive-ui'
import { NTag, NButton, NProgress, NSpin, NTabs, NTabPane, NInput, NCheckbox, NDataTable, NBadge, NPopselect } from 'naive-ui'
import { securityAPI } from '@/api/index.js'
import { marked } from 'marked'

const message = useMessage()

// 表单
const activeTab = ref('web_scan')
const form = ref({
  target: '',
  deepScan: false,
  sqlmapVerify: false,
  specVersionId: '',
  authToken: '',
  pythonReq: '',
  nodeDir: '',
  trivyTarget: '',
})

// 状态
const starting = ref(false)
const running = ref(false)
const currentTaskId = ref(null)
const currentProgress = ref(0)
const currentVulnCount = ref(0)
const result = ref(null)
const showReport = ref(false)
let pollTimer = null

// 历史
const historyList = ref([])
const historyLoading = ref(false)

// 安全测试用例任务
const securityCases = ref([])
const casesLoading = ref(false)
const caseFilterStatus = ref('all')
const caseSearch = ref('')
const caseStats = ref({ all: 0, pending: 0, pass: 0, bug: 0 })
const casePage = ref(1)
const casePageSize = 10

const caseFilters = computed(() => [
  { label: '全部', value: 'all', count: caseStats.value.all, badgeType: 'default' },
  { label: '待测试', value: '待测试', count: caseStats.value.pending, badgeType: 'info' },
  { label: '通过', value: '通过', count: caseStats.value.pass, badgeType: 'success' },
  { label: 'Bug', value: 'bug', count: caseStats.value.bug, badgeType: 'error' },
])

const casePagination = computed(() => ({
  page: casePage.value,
  pageSize: casePageSize,
  pageCount: Math.ceil((caseStats.value.all || 1) / casePageSize),
  itemCount: caseFilterStatus.value === 'all' ? caseStats.value.all : securityCases.value.length,
}))

// 安全用例状态选项
const statusOptions = [
  { label: '待测试', value: '待测试' },
  { label: '✅ 通过', value: '通过' },
  { label: '🐛 Bug', value: 'bug' },
]
const caseStatusTagType = { '待测试': 'default', '通过': 'success', 'bug': 'error' }

// 安全用例表格列
const caseColumns = [
  { title: 'ID', key: 'id', width: 60 },
  { title: '模块', key: 'module', width: 120, ellipsis: { tooltip: true } },
  { title: '用例名称', key: 'title', width: 200, ellipsis: { tooltip: true } },
  {
    title: '步骤',
    key: 'steps',
    width: 280,
    ellipsis: { tooltip: true },
    render: (row) => {
      const steps = Array.isArray(row.steps) ? row.steps : []
      return steps.map((s, i) => `${i + 1}. ${s}`).join('\n') || '-'
    }
  },
  {
    title: '优先级',
    key: 'priority',
    width: 70,
    render: (row) => {
      const pMap = { '1': 'error', '2': 'warning', '3': 'info', '4': 'default' }
      const pLabel = { '1': '1级', '2': '2级', '3': '3级', '4': '4级' }
      return h(NTag, { type: pMap[row.priority] || 'default', size: 'small' }, () => pLabel[row.priority] || row.priority)
    }
  },
  {
    title: '状态',
    key: 'security_status',
    width: 120,
    render: (row) => {
      const currentStatus = row.security_status || '待测试'
      return h(NPopselect, {
        value: currentStatus,
        options: statusOptions,
        onUpdateValue: (val) => handleUpdateCaseStatus(row.id, val),
        trigger: 'click',
      }, {
        default: () => h(NTag, {
          type: caseStatusTagType[currentStatus] || 'default',
          size: 'small',
          style: 'cursor: pointer',
        }, {
          default: () => currentStatus,
          icon: () => h('i', { class: 'fas fa-caret-down', style: 'margin-left: 4px; font-size: 10px' }),
        })
      })
    }
  },
]

// 计算属性
const stageLabel = computed(() => {
  const p = currentProgress.value
  if (p < 5) return '初始化'
  if (p < 30) return 'Spider 爬虫'
  if (p < 80) return 'Active Scan'
  if (p < 95) return '分析中'
  return '生成报告'
})

const stageTagType = computed(() => {
  const p = currentProgress.value
  if (p < 30) return 'info'
  if (p < 80) return 'warning'
  return 'success'
})

const vulnSummary = computed(() => {
  return result.value?.vuln_summary || { critical: 0, high: 0, medium: 0, low: 0, info: 0 }
})

const riskTagType = computed(() => {
  const level = result.value?.risk_level
  if (level === 'A') return 'success'
  if (level === 'B') return 'info'
  if (level === 'C') return 'warning'
  return 'error'
})

const renderedReport = computed(() => {
  if (!result.value?.report_content) return ''
  return marked(result.value.report_content)
})

// 漏洞表格列
const severityMap = { critical: '严重', high: '高危', medium: '中危', low: '低危', info: '信息' }
const severityTypeMap = { critical: 'error', high: 'warning', medium: 'warning', low: 'info', info: 'default' }

const vulnColumns = [
  {
    title: '级别',
    key: 'severity',
    width: 80,
    render: (row) => h(NTag, { type: severityTypeMap[row.severity] || 'default', size: 'small' }, () => severityMap[row.severity] || row.severity)
  },
  { title: '漏洞类型', key: 'vuln_type', ellipsis: { tooltip: true } },
  { title: '来源', key: 'source', width: 100 },
  { title: 'URL', key: 'url', width: 200, ellipsis: { tooltip: true } },
  { title: '描述', key: 'description', ellipsis: { tooltip: true } },
  { title: '修复建议', key: 'solution', ellipsis: { tooltip: true } },
]

function vulnRowClass(row) {
  if (row.severity === 'critical') return 'bg-red-50/50'
  if (row.severity === 'high') return 'bg-orange-50/50'
  return ''
}

// 历史表格列
const typeLabels = { web_scan: 'Web 扫描', api_attack: 'API 攻击', dependency_scan: '依赖扫描', baseline_check: '基线检测' }
const statusLabels = { pending: '等待中', running: '运行中', finished: '已完成', failed: '失败', stopped: '已停止' }
const statusTypes = { pending: 'default', running: 'info', finished: 'success', failed: 'error', stopped: 'warning' }

const historyColumns = [
  { title: 'ID', key: 'task_id', width: 60 },
  {
    title: '类型',
    key: 'type',
    width: 100,
    render: (row) => typeLabels[row.type] || row.type
  },
  { title: '目标', key: 'target', width: 200, ellipsis: { tooltip: true } },
  {
    title: '状态',
    key: 'status',
    width: 90,
    render: (row) => h(NTag, { type: statusTypes[row.status] || 'default', size: 'small' }, () => statusLabels[row.status] || row.status)
  },
  {
    title: '评分',
    key: 'risk_score',
    width: 80,
    render: (row) => row.risk_score != null ? h(NTag, { type: riskLevelType(row.risk_level), size: 'small' }, () => `${row.risk_level} ${row.risk_score}`) : '-'
  },
  { title: '耗时(s)', key: 'duration', width: 80 },
  { title: '时间', key: 'created_at', width: 160 },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    render: (row) => h('div', { class: 'flex gap-1' }, [
      row.status === 'finished' ? h(NButton, { size: 'tiny', type: 'primary', quaternary: true, onClick: () => viewResult(row.task_id) }, () => '查看') : null,
      h(NButton, { size: 'tiny', type: 'error', quaternary: true, onClick: () => deleteTask(row.task_id) }, () => '删除'),
    ])
  },
]

function riskLevelType(level) {
  if (level === 'A') return 'success'
  if (level === 'B') return 'info'
  if (level === 'C') return 'warning'
  return 'error'
}

// 方法
async function handleRun() {
  if (!form.value.target) {
    message.warning('请输入扫描目标')
    return
  }

  starting.value = true
  try {
    const config = {}
    if (activeTab.value === 'web_scan') {
      config.deep_scan = form.value.deepScan
      config.sqlmap_verify = form.value.sqlmapVerify
    } else if (activeTab.value === 'api_attack') {
      if (form.value.specVersionId) config.spec_version_id = parseInt(form.value.specVersionId)
      if (form.value.authToken) config.auth_info = { type: 'bearer', token: form.value.authToken }
    } else if (activeTab.value === 'dependency_scan') {
      if (form.value.pythonReq) config.python_requirements = form.value.pythonReq
      if (form.value.nodeDir) config.node_project_dir = form.value.nodeDir
      if (form.value.trivyTarget) config.trivy_target = form.value.trivyTarget
    }

    const res = await securityAPI.run(activeTab.value, form.value.target, config)
    if (res.success) {
      currentTaskId.value = res.data.task_id
      running.value = true
      currentProgress.value = 0
      currentVulnCount.value = 0
      result.value = null
      startPolling()
      message.success('扫描任务已启动')
    } else {
      message.error(res.message || '启动失败')
    }
  } catch (e) {
    message.error(e.response?.data?.detail || e.message || '启动失败')
  } finally {
    starting.value = false
  }
}

async function handleStop() {
  if (!currentTaskId.value) return
  try {
    await securityAPI.stop(currentTaskId.value)
    running.value = false
    stopPolling()
    message.info('已停止扫描')
  } catch (e) {
    message.error('停止失败')
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    if (!currentTaskId.value) return
    try {
      const res = await securityAPI.getStatus(currentTaskId.value)
      if (res.success) {
        const d = res.data
        currentProgress.value = d.progress || 0
        currentVulnCount.value = d.vuln_summary?.total || 0

        if (d.status === 'finished' || d.status === 'failed' || d.status === 'stopped') {
          running.value = false
          stopPolling()
          if (d.status === 'finished') {
            await loadResult(currentTaskId.value)
            message.success('扫描完成')
          } else if (d.status === 'failed') {
            message.error(`扫描失败: ${d.error_message || '未知错误'}`)
          }
          loadHistory()
        }
      }
    } catch (e) {
      console.error('轮询失败:', e)
    }
  }, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function loadResult(taskId) {
  try {
    const res = await securityAPI.getResult(taskId)
    if (res.success) {
      result.value = res.data
    }
  } catch (e) {
    console.error('加载结果失败:', e)
  }
}

async function viewResult(taskId) {
  await loadResult(taskId)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const res = await securityAPI.getHistory({ page: 1, page_size: 50 })
    if (res.success) {
      historyList.value = res.data.items || []
    }
  } catch (e) {
    console.error('加载历史失败:', e)
  } finally {
    historyLoading.value = false
  }
}

async function deleteTask(taskId) {
  try {
    await securityAPI.delete(taskId)
    message.success('已删除')
    loadHistory()
  } catch (e) {
    message.error('删除失败')
  }
}

// 安全测试用例任务方法
async function loadSecurityCases() {
  casesLoading.value = true
  try {
    const params = {
      page: casePage.value,
      page_size: casePageSize,
    }
    if (caseFilterStatus.value !== 'all') {
      params.status = caseFilterStatus.value
    }
    if (caseSearch.value) {
      params.search = caseSearch.value
    }
    const res = await securityAPI.getCases(params)
    if (res.success) {
      securityCases.value = res.data.items || []
      caseStats.value = res.data.stats || { all: 0, pending: 0, pass: 0, bug: 0 }
    }
  } catch (e) {
    console.error('加载安全用例失败:', e)
  } finally {
    casesLoading.value = false
  }
}

function handleCasePageChange(page) {
  casePage.value = page
  loadSecurityCases()
}

async function handleUpdateCaseStatus(caseId, newStatus) {
  try {
    const res = await securityAPI.updateCaseStatus(caseId, newStatus)
    if (res.success) {
      message.success(`已标记为「${newStatus}」`)
      // 更新本地数据
      const item = securityCases.value.find(c => c.id === caseId)
      if (item) item.security_status = newStatus
      // 刷新统计
      loadSecurityCases()
    }
  } catch (e) {
    message.error('状态更新失败')
  }
}

onMounted(() => {
  loadHistory()
  loadSecurityCases()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.security-test {
  max-width: 1200px;
}

.glass-card {
  background: white;
  border: 1px solid rgba(0, 120, 87, 0.1);
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
}

.markdown-body {
  font-size: 14px;
  line-height: 1.7;
}

.markdown-body h1, .markdown-body h2, .markdown-body h3 {
  margin-top: 1em;
  margin-bottom: 0.5em;
  color: #1e293b;
}

.markdown-body table {
  border-collapse: collapse;
  width: 100%;
  margin: 0.5em 0;
}

.markdown-body th, .markdown-body td {
  border: 1px solid #e2e8f0;
  padding: 6px 12px;
  text-align: left;
}

.markdown-body th {
  background: #f8fafc;
}

.markdown-body code {
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}

.markdown-body ul, .markdown-body ol {
  padding-left: 1.5em;
}
</style>
