<template>
  <div class="security-platform">
    <!-- 页面导航 -->
    <div class="glass-card p-3 mb-3">
      <div class="flex items-center justify-between">
        <n-tabs v-model:value="activeModule" type="segment" size="small">
          <n-tab-pane name="assets" tab="资产管理" />
          <n-tab-pane name="tasks" tab="扫描任务" />
          <n-tab-pane name="vulnerabilities" tab="漏洞列表" />
          <n-tab-pane name="logs" tab="扫描日志" />
          <n-tab-pane name="reports" tab="报告下载" />
        </n-tabs>
      </div>
    </div>

    <!-- 1. 资产管理页面 -->
    <div v-if="activeModule === 'assets'" class="space-y-4">
      <!-- 资产管理操作区 -->
      <div class="glass-card p-4">
        <div class="flex items-center justify-between mb-3">
          <span class="font-bold text-slate-700">资产管理</span>
          <n-button type="primary" @click="showCreateTarget = true">
            <template #icon><i class="fas fa-plus"></i></template>
            新建目标
          </n-button>
        </div>
        
        <!-- 搜索区 -->
        <div class="flex items-center gap-3 mb-3">
          <n-input v-model:value="targetSearch" placeholder="搜索目标..." style="width: 300px" clearable @keyup.enter="loadTargets">
            <template #prefix><i class="fas fa-search text-slate-400"></i></template>
          </n-input>
          <n-button @click="loadTargets">搜索</n-button>
        </div>

        <!-- 目标列表 -->
        <n-data-table
          :columns="targetColumns"
          :data="targets"
          :loading="targetsLoading"
          :pagination="{ pageSize: 10 }"
          size="small"
          striped
        />
      </div>
    </div>

    <!-- 2. 扫描任务页面 -->
    <div v-if="activeModule === 'tasks'" class="space-y-4">
      <!-- 扫描任务操作区 -->
      <div class="glass-card p-4">
        <div class="flex items-center justify-between mb-3">
          <span class="font-bold text-slate-700">扫描任务</span>
          <n-button type="primary" @click="showCreateTask = true">
            <template #icon><i class="fas fa-plus"></i></template>
            新建任务
          </n-button>
        </div>

        <!-- 任务列表 -->
        <n-data-table
          :columns="taskColumns"
          :data="tasks"
          :loading="tasksLoading"
          :pagination="{ pageSize: 10 }"
          size="small"
          striped
        />
      </div>

      <!-- 执行中状态 -->
      <div v-if="runningTask" class="glass-card p-4">
        <div class="flex items-center gap-3 mb-2">
          <n-spin size="small" />
          <span class="font-bold text-slate-700">扫描进行中...</span>
          <n-tag :type="getProgressType(runningTask.progress)" size="small">
            {{ getProgressLabel(runningTask.progress) }}
          </n-tag>
          <n-button type="error" size="small" @click="stopTask(runningTask.id)">
            <template #icon><i class="fas fa-stop"></i></template>
            停止
          </n-button>
        </div>
        <n-progress type="line" :percentage="runningTask.progress" :indicator-placement="'inside'" processing />
        <div class="mt-2 text-xs text-slate-400">
          任务 ID: {{ runningTask.id }} | 目标: {{ getTargetName(runningTask.target_id) }}
        </div>
      </div>
    </div>

    <!-- 3. 漏洞列表页面 -->
    <div v-if="activeModule === 'vulnerabilities'" class="space-y-4">
      <div class="glass-card p-4">
        <div class="flex items-center justify-between mb-3">
          <span class="font-bold text-slate-700">漏洞管理</span>
          <n-button size="small" quaternary @click="loadVulnerabilities">
            <template #icon><i class="fas fa-refresh"></i></template>
            刷新
          </n-button>
        </div>

        <!-- 筛选区 -->
        <div class="flex items-center gap-3 mb-3">
          <n-select v-model:value="vulnSeverityFilter" placeholder="严重程度" style="width: 120px" clearable @update:value="loadVulnerabilities">
            <n-option value="critical" label="严重" />
            <n-option value="high" label="高危" />
            <n-option value="medium" label="中危" />
            <n-option value="low" label="低危" />
            <n-option value="info" label="信息" />
          </n-select>
          <n-select v-model:value="vulnStatusFilter" placeholder="状态" style="width: 120px" clearable @update:value="loadVulnerabilities">
            <n-option value="open" label="待修复" />
            <n-option value="fixed" label="已修复" />
            <n-option value="false_positive" label="误报" />
            <n-option value="accepted" label="已接受" />
          </n-select>
          <n-input v-model:value="vulnSearch" placeholder="搜索漏洞..." style="width: 200px" clearable @keyup.enter="loadVulnerabilities">
            <template #prefix><i class="fas fa-search text-slate-400"></i></template>
          </n-input>
        </div>

        <!-- 漏洞列表 -->
        <n-data-table
          :columns="vulnColumns"
          :data="vulnerabilities"
          :loading="vulnLoading"
          :pagination="{ pageSize: 10 }"
          :row-class-name="vulnRowClass"
          size="small"
          striped
        />
      </div>
    </div>

    <!-- 4. 扫描日志页面 -->
    <div v-if="activeModule === 'logs'" class="space-y-4">
      <div class="glass-card p-4">
        <div class="flex items-center justify-between mb-3">
          <span class="font-bold text-slate-700">扫描日志</span>
          <n-button size="small" quaternary @click="loadLogs">
            <template #icon><i class="fas fa-refresh"></i></template>
            刷新
          </n-button>
        </div>

        <!-- 日志筛选 -->
        <div class="flex items-center gap-3 mb-3">
          <n-select v-model:value="logTaskFilter" placeholder="选择任务" style="width: 200px" clearable @update:value="loadLogs">
            <n-option v-for="task in tasks" :key="task.id" :value="task.id" :label="`任务${task.id} - ${task.scan_type} (${getTargetName(task.target_id)})`" />
          </n-select>
          <n-select v-model:value="logLevelFilter" placeholder="日志级别" style="width: 120px" clearable @update:value="loadLogs">
            <n-option value="debug" label="DEBUG" />
            <n-option value="info" label="INFO" />
            <n-option value="warning" label="WARNING" />
            <n-option value="error" label="ERROR" />
          </n-select>
        </div>

        <!-- 日志列表 -->
        <n-data-table
          :columns="logColumns"
          :data="logs"
          :loading="logsLoading"
          :pagination="{ pageSize: 20 }"
          size="small"
          striped
        />
      </div>
    </div>

    <!-- 5. 报告下载页面 -->
    <div v-if="activeModule === 'reports'" class="space-y-4">
      <!-- 生成报告 -->
      <div class="glass-card p-4">
        <div class="flex items-center justify-between mb-3">
          <span class="font-bold text-slate-700">报告管理</span>
        </div>

        <!-- 生成报告表单 -->
        <div class="space-y-3 mb-5">
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-2">生成报告:</label>
            <div class="flex items-center gap-3">
              <n-select v-model:value="reportTaskId" placeholder="选择任务" style="width: 200px">
                <n-option v-for="task in finishedTasks" :key="task.id" :value="task.id" :label="`任务${task.id} - ${task.scan_type} (${getTargetName(task.target_id)})`" />
              </n-select>
              <n-radio-group v-model:value="reportFormat">
                <n-radio value="html">HTML</n-radio>
                <n-radio value="markdown">Markdown</n-radio>
                <n-radio value="json">JSON</n-radio>
              </n-radio-group>
              <n-button type="primary" :loading="generatingReport" @click="generateReport">
                生成报告
              </n-button>
            </div>
          </div>
        </div>

        <!-- 报告历史 -->
        <div>
          <h3 class="text-sm font-medium text-slate-700 mb-3">报告历史:</h3>
          <n-data-table
            :columns="reportColumns"
            :data="reportHistory"
            :loading="reportsLoading"
            :pagination="{ pageSize: 10 }"
            size="small"
            striped
          />
        </div>
      </div>
    </div>

    <!-- 新建目标对话框 -->
    <n-modal v-model:show="showCreateTarget" preset="dialog" title="新建扫描目标">
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">名称</label>
          <n-input v-model:value="newTarget.name" placeholder="输入目标名称" />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">URL</label>
          <n-input v-model:value="newTarget.base_url" placeholder="输入目标URL" />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">描述</label>
          <n-input v-model:value="newTarget.description" placeholder="输入描述信息" type="textarea" />
        </div>
      </div>
      <template #action>
        <n-button @click="showCreateTarget = false">取消</n-button>
        <n-button type="primary" :loading="creatingTarget" @click="createTarget">保存</n-button>
      </template>
    </n-modal>

    <!-- 新建任务对话框 -->
    <n-modal v-model:show="showCreateTask" preset="dialog" title="新建扫描任务">
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">目标</label>
          <n-select v-model:value="newTask.target_id" placeholder="选择扫描目标">
            <n-option v-for="target in targets" :key="target.id" :value="target.id" :label="`${target.name} (${target.base_url})`" />
          </n-select>
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">扫描类型</label>
          <n-radio-group v-model:value="newTask.scan_type">
            <n-radio value="sqlmap">SQLMap SQL注入</n-radio>
            <n-radio value="xsstrike">XSStrike XSS检测</n-radio>
            <n-radio value="fuzz">Fuzz 模糊测试</n-radio>
            <n-radio value="full_scan">全面扫描</n-radio>
          </n-radio-group>
          <div class="text-xs text-gray-500 mt-1">
            注意: Nuclei工具暂时不可用，需要手动安装
          </div>
        </div>
      </div>
      <template #action>
        <n-button @click="showCreateTask = false">取消</n-button>
        <n-button type="primary" :loading="creatingTask" @click="createTask">开始扫描</n-button>
      </template>
    </n-modal>

    <!-- 漏洞详情对话框 -->
    <n-modal v-model:show="showVulnDetail" preset="card" title="漏洞详情" style="width: 800px">
      <div v-if="selectedVuln" class="space-y-4">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">严重程度</label>
            <n-tag :type="getSeverityType(selectedVuln.severity)">{{ getSeverityLabel(selectedVuln.severity) }}</n-tag>
          </div>
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-1">发现时间</label>
            <span class="text-sm">{{ formatTime(selectedVuln.first_found) }}</span>
          </div>
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">漏洞标题</label>
          <p class="text-sm">{{ selectedVuln.title }}</p>
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">描述</label>
          <p class="text-sm">{{ selectedVuln.description || '暂无描述' }}</p>
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">修复建议</label>
          <p class="text-sm">{{ selectedVuln.fix_suggestion || '暂无修复建议' }}</p>
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">状态</label>
          <n-select v-model:value="selectedVuln.status" style="width: 150px" @update:value="updateVulnStatus">
            <n-option value="open" label="待修复" />
            <n-option value="fixed" label="已修复" />
            <n-option value="false_positive" label="误报" />
            <n-option value="accepted" label="已接受" />
          </n-select>
        </div>
      </div>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, h } from 'vue'
import { useMessage } from 'naive-ui'
import { NTag, NButton, NProgress, NSpin, NTabs, NTabPane, NInput, NCheckbox, NDataTable, NBadge, NPopselect } from 'naive-ui'
import { securityAPI } from '@/api/index.js'

const message = useMessage()

// 安全测试平台状态管理
const activeModule = ref('assets')

// 1. 资产管理相关状态
const targets = ref([])
const targetsLoading = ref(false)
const targetSearch = ref('')
const showCreateTarget = ref(false)
const creatingTarget = ref(false)
const newTarget = ref({
  name: '',
  base_url: '',
  description: ''
})

// 2. 扫描任务相关状态
const tasks = ref([])
const tasksLoading = ref(false)
const showCreateTask = ref(false)
const creatingTask = ref(false)
const runningTask = ref(null)
const newTask = ref({
  target_id: null,
  scan_type: 'xsstrike'  // 使用可用的工具作为默认值
})

// 3. 漏洞管理相关状态
const vulnerabilities = ref([])
const vulnLoading = ref(false)
const vulnSeverityFilter = ref(null)
const vulnStatusFilter = ref(null)
const vulnSearch = ref('')
const showVulnDetail = ref(false)
const selectedVuln = ref(null)

// 4. 扫描日志相关状态
const logs = ref([])
const logsLoading = ref(false)
const logTaskFilter = ref(null)
const logLevelFilter = ref(null)

// 5. 报告管理相关状态
const reportHistory = ref([])
const reportsLoading = ref(false)
const reportTaskId = ref(null)
const reportFormat = ref('html')
const generatingReport = ref(false)

// 计算属性
const finishedTasks = computed(() => {
  return tasks.value.filter(task => task.status === 'finished')
})

// 表格列定义
const targetColumns = [
  { title: 'ID', key: 'id', width: 60 },
  { title: '名称', key: 'name', width: 150, ellipsis: { tooltip: true } },
  { title: 'URL', key: 'base_url', width: 300, ellipsis: { tooltip: true } },
  { title: '描述', key: 'description', ellipsis: { tooltip: true } },
  { title: '创建时间', key: 'created_at', width: 160 },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    render: (row) => h('div', { class: 'flex gap-1' }, [
      h(NButton, { size: 'tiny', type: 'primary', quaternary: true, onClick: () => editTarget(row) }, () => '编辑'),
      h(NButton, { size: 'tiny', type: 'error', quaternary: true, onClick: () => deleteTarget(row.id) }, () => '删除'),
    ])
  },
]

const taskColumns = [
  { title: 'ID', key: 'id', width: 60 },
  { 
    title: '目标', 
    key: 'target_name', 
    width: 150, 
    ellipsis: { tooltip: true },
    render: (row) => {
      const target = targets.value.find(t => t.id === row.target_id)
      return target ? `${target.name} (${target.base_url})` : `目标ID: ${row.target_id}`
    }
  },
  {
    title: '扫描类型',
    key: 'scan_type',
    width: 120,
    render: (row) => {
      const typeMap = { nuclei: 'Nuclei', sqlmap: 'SQLMap', xsstrike: 'XSStrike', fuzz: 'Fuzz', full_scan: '全面扫描' }
      return typeMap[row.scan_type] || row.scan_type
    }
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (row) => {
      const statusMap = { pending: '等待中', running: '运行中', finished: '已完成', failed: '失败', stopped: '已停止' }
      const statusTypes = { pending: 'default', running: 'info', finished: 'success', failed: 'error', stopped: 'warning' }
      return h(NTag, { type: statusTypes[row.status] || 'default', size: 'small' }, () => statusMap[row.status] || row.status)
    }
  },
  { 
    title: '创建时间', 
    key: 'created_at', 
    width: 160,
    render: (row) => formatTime(row.created_at)
  },
  {
    title: '操作',
    key: 'actions',
    width: 150,
    render: (row) => h('div', { class: 'flex gap-1' }, [
      row.status === 'running' ? h(NButton, { size: 'tiny', type: 'error', onClick: () => stopTask(row.id) }, () => '停止') : null,
      row.status === 'finished' ? h(NButton, { size: 'tiny', type: 'primary', quaternary: true, onClick: () => viewTaskResult(row.id) }, () => '查看') : null,
      h(NButton, { size: 'tiny', type: 'error', quaternary: true, onClick: () => deleteTask(row.id) }, () => '删除'),
    ])
  },
]

const vulnColumns = [
  { title: 'ID', key: 'id', width: 60 },
  { title: '标题', key: 'title', width: 200, ellipsis: { tooltip: true } },
  {
    title: '严重程度',
    key: 'severity',
    width: 100,
    render: (row) => {
      const severityMap = { critical: '严重', high: '高危', medium: '中危', low: '低危', info: '信息' }
      const severityTypes = { critical: 'error', high: 'warning', medium: 'warning', low: 'info', info: 'default' }
      return h(NTag, { type: severityTypes[row.severity] || 'default', size: 'small' }, () => severityMap[row.severity] || row.severity)
    }
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (row) => {
      const statusMap = { open: '待修复', fixed: '已修复', false_positive: '误报', accepted: '已接受' }
      const statusTypes = { open: 'error', fixed: 'success', false_positive: 'warning', accepted: 'info' }
      return h(NTag, { type: statusTypes[row.status] || 'default', size: 'small' }, () => statusMap[row.status] || row.status)
    }
  },
  { title: '发现时间', key: 'first_found', width: 160 },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    render: (row) => h(NButton, { size: 'tiny', type: 'primary', quaternary: true, onClick: () => viewVulnDetail(row) }, () => '详情')
  },
]

const logColumns = [
  { title: '时间', key: 'created_at', width: 160 },
  {
    title: '级别',
    key: 'level',
    width: 80,
    render: (row) => {
      const levelTypes = { debug: 'default', info: 'info', warning: 'warning', error: 'error' }
      return h(NTag, { type: levelTypes[row.level] || 'default', size: 'small' }, () => row.level?.toUpperCase() || 'INFO')
    }
  },
  { title: '消息', key: 'message', ellipsis: { tooltip: true } },
]

const reportColumns = [
  { title: '时间', key: 'created_at', width: 160 },
  { title: '任务ID', key: 'task_id', width: 80 },
  { title: '格式', key: 'format', width: 80 },
  { title: '文件名', key: 'filename', ellipsis: { tooltip: true } },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    render: (row) => h(NButton, { size: 'tiny', type: 'primary', quaternary: true, onClick: () => downloadReport(row) }, () => '下载')
  },
]

// 工具函数
function getSeverityType(severity) {
  const types = { critical: 'error', high: 'warning', medium: 'warning', low: 'info', info: 'default' }
  return types[severity] || 'default'
}

function getSeverityLabel(severity) {
  const labels = { critical: '严重', high: '高危', medium: '中危', low: '低危', info: '信息' }
  return labels[severity] || severity
}

function getProgressType(progress) {
  if (progress < 30) return 'info'
  if (progress < 80) return 'warning'
  return 'success'
}

function getProgressLabel(progress) {
  if (progress < 5) return '初始化'
  if (progress < 30) return '扫描中'
  if (progress < 80) return '分析中'
  if (progress < 95) return '生成报告'
  return '完成'
}

function formatTime(timeStr) {
  if (!timeStr) return '-'
  return new Date(timeStr).toLocaleString('zh-CN')
}

function getTargetName(targetId) {
  const target = targets.value.find(t => t.id === targetId)
  return target ? `${target.name} (${target.base_url})` : `目标ID: ${targetId}`
}

function vulnRowClass(row) {
  if (row.severity === 'critical') return 'bg-red-50/50'
  if (row.severity === 'high') return 'bg-orange-50/50'
  return ''
}

// API 方法

// 1. 资产管理 API
async function loadTargets() {
  targetsLoading.value = true
  try {
    const params = {}
    if (targetSearch.value) params.search = targetSearch.value
    
    const response = await securityAPI.getTargets(params)
    if (response.success) {
      targets.value = response.data || []
    } else {
      message.error(response.message || '加载目标失败')
    }
  } catch (error) {
    console.error('加载目标失败:', error)
    message.error('加载目标失败')
  } finally {
    targetsLoading.value = false
  }
}

async function createTarget() {
  if (!newTarget.value.name || !newTarget.value.base_url) {
    message.warning('请填写完整信息')
    return
  }
  
  creatingTarget.value = true
  try {
    const response = await securityAPI.createTarget(newTarget.value)
    if (response.success) {
      message.success('目标创建成功')
      showCreateTarget.value = false
      newTarget.value = { name: '', base_url: '', description: '' }
      loadTargets()
    } else {
      message.error(response.message || '创建失败')
    }
  } catch (error) {
    console.error('创建目标失败:', error)
    message.error('创建目标失败')
  } finally {
    creatingTarget.value = false
  }
}

async function editTarget(target) {
  // 编辑目标功能
  newTarget.value = { ...target }
  showCreateTarget.value = true
}

async function deleteTarget(targetId) {
  try {
    const response = await securityAPI.deleteTarget(targetId)
    if (response.success) {
      message.success('目标删除成功')
      loadTargets()
    } else {
      message.error(response.message || '删除失败')
    }
  } catch (error) {
    console.error('删除目标失败:', error)
    message.error('删除目标失败')
  }
}

// 2. 扫描任务 API
async function loadTasks() {
  tasksLoading.value = true
  try {
    const response = await securityAPI.getTasks()
    if (response.success) {
      tasks.value = response.data || []
      // 检查是否有运行中的任务
      runningTask.value = tasks.value.find(task => task.status === 'running') || null
    } else {
      message.error(response.message || '加载任务失败')
    }
  } catch (error) {
    console.error('加载任务失败:', error)
    message.error('加载任务失败')
  } finally {
    tasksLoading.value = false
  }
}

async function createTask() {
  if (!newTask.value.target_id || !newTask.value.scan_type) {
    message.warning('请选择目标和扫描类型')
    return
  }
  
  creatingTask.value = true
  try {
    const response = await securityAPI.createScan({
      target_id: newTask.value.target_id,
      scan_type: newTask.value.scan_type
    })
    if (response.success) {
      message.success('扫描任务已创建')
      showCreateTask.value = false
      newTask.value = { target_id: null, scan_type: 'xsstrike' }  // 使用可用的工具
      loadTasks()
      // 开始轮询任务状态
      startTaskPolling()
    } else {
      message.error(response.message || '创建任务失败')
    }
  } catch (error) {
    console.error('创建任务失败:', error)
    message.error('创建任务失败')
  } finally {
    creatingTask.value = false
  }
}

async function stopTask(taskId) {
  try {
    const response = await securityAPI.stopTask(taskId)
    if (response.success) {
      message.success('任务已停止')
      loadTasks()
    } else {
      message.error(response.message || '停止任务失败')
    }
  } catch (error) {
    console.error('停止任务失败:', error)
    message.error('停止任务失败')
  }
}

async function viewTaskResult(taskId) {
  try {
    const response = await securityAPI.getTask(taskId)
    if (response.success) {
      // 切换到漏洞列表页面显示结果
      activeModule.value = 'vulnerabilities'
      loadVulnerabilities()
    } else {
      message.error(response.message || '获取任务结果失败')
    }
  } catch (error) {
    console.error('获取任务结果失败:', error)
    message.error('获取任务结果失败')
  }
}

async function deleteTask(taskId) {
  try {
    const response = await securityAPI.deleteTask(taskId)
    if (response.success) {
      message.success('任务删除成功')
      loadTasks()
    } else {
      message.error(response.message || '删除任务失败')
    }
  } catch (error) {
    console.error('删除任务失败:', error)
    message.error('删除任务失败')
  }
}

// 3. 漏洞管理 API
async function loadVulnerabilities() {
  vulnLoading.value = true
  try {
    const params = {}
    if (vulnSeverityFilter.value) params.severity = vulnSeverityFilter.value
    if (vulnStatusFilter.value) params.status = vulnStatusFilter.value
    if (vulnSearch.value) params.search = vulnSearch.value
    
    const response = await securityAPI.getVulnerabilities(params)
    if (response.success) {
      vulnerabilities.value = response.data || []
    } else {
      message.error(response.message || '加载漏洞失败')
    }
  } catch (error) {
    console.error('加载漏洞失败:', error)
    message.error('加载漏洞失败')
  } finally {
    vulnLoading.value = false
  }
}

function viewVulnDetail(vuln) {
  selectedVuln.value = { ...vuln }
  showVulnDetail.value = true
}

async function updateVulnStatus(newStatus) {
  if (!selectedVuln.value) return
  
  try {
    const response = await securityAPI.updateVulnerability(selectedVuln.value.id, {
      status: newStatus
    })
    if (response.success) {
      message.success('状态更新成功')
      selectedVuln.value.status = newStatus
      loadVulnerabilities()
    } else {
      message.error(response.message || '状态更新失败')
    }
  } catch (error) {
    console.error('状态更新失败:', error)
    message.error('状态更新失败')
  }
}

// 4. 扫描日志 API
async function loadLogs() {
  logsLoading.value = true
  try {
    const params = {}
    if (logTaskFilter.value) params.task_id = logTaskFilter.value
    if (logLevelFilter.value) params.level = logLevelFilter.value
    
    const response = await securityAPI.getLogs(params)
    if (response.success) {
      logs.value = response.data || []
    } else {
      message.error(response.message || '加载日志失败')
    }
  } catch (error) {
    console.error('加载日志失败:', error)
    message.error('加载日志失败')
  } finally {
    logsLoading.value = false
  }
}

// 5. 报告管理 API
async function loadReportHistory() {
  reportsLoading.value = true
  try {
    const response = await securityAPI.getReports()
    if (response.success) {
      reportHistory.value = response.data || []
    } else {
      message.error(response.message || '加载报告历史失败')
    }
  } catch (error) {
    console.error('加载报告历史失败:', error)
    message.error('加载报告历史失败')
  } finally {
    reportsLoading.value = false
  }
}

async function generateReport() {
  if (!reportTaskId.value || !reportFormat.value) {
    message.warning('请选择任务和报告格式')
    return
  }
  
  generatingReport.value = true
  try {
    const response = await securityAPI.generateReport({
      task_id: reportTaskId.value,
      format: reportFormat.value
    })
    if (response.success) {
      message.success('报告生成成功')
      loadReportHistory()
    } else {
      message.error(response.message || '报告生成失败')
    }
  } catch (error) {
    console.error('报告生成失败:', error)
    message.error('报告生成失败')
  } finally {
    generatingReport.value = false
  }
}

async function downloadReport(report) {
  try {
    const response = await securityAPI.downloadReport(report.id)
    
    // 创建下载链接
    const url = window.URL.createObjectURL(new Blob([response]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', report.filename)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    
    message.success('报告下载成功')
  } catch (error) {
    console.error('报告下载失败:', error)
    message.error('报告下载失败')
  }
}

// 任务状态轮询
let taskPollTimer = null

function startTaskPolling() {
  stopTaskPolling()
  taskPollTimer = setInterval(async () => {
    if (runningTask.value) {
      try {
        const response = await securityAPI.getTask(runningTask.value.id)
        if (response.success) {
          const taskData = response.data
          runningTask.value = { ...runningTask.value, ...taskData }
          
          if (taskData.status !== 'running') {
            runningTask.value = null
            stopTaskPolling()
            loadTasks()
            if (taskData.status === 'finished') {
              message.success('扫描完成')
            } else if (taskData.status === 'failed') {
              message.error('扫描失败')
            }
          }
        }
      } catch (error) {
        console.error('轮询任务状态失败:', error)
      }
    } else {
      stopTaskPolling()
    }
  }, 3000)
}

function stopTaskPolling() {
  if (taskPollTimer) {
    clearInterval(taskPollTimer)
    taskPollTimer = null
  }
}

// 生命周期
onMounted(() => {
  loadTargets()
  loadTasks()
  loadVulnerabilities()
  loadLogs()
  loadReportHistory()
})

onUnmounted(() => {
  stopTaskPolling()
})
</script>

<style scoped>
.security-platform {
  max-width: 1400px;
  margin: 0 auto;
  padding: 10px 20px;
}

.glass-card {
  background: white;
  border: 1px solid rgba(0, 120, 87, 0.1);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
  backdrop-filter: blur(10px);
}

/* 模块切换标签样式 */
.n-tabs .n-tab-pane {
  padding: 0;
}

/* 表格行样式 */
.bg-red-50\/50 {
  background-color: rgba(254, 242, 242, 0.5);
}

.bg-orange-50\/50 {
  background-color: rgba(255, 247, 237, 0.5);
}

/* 按钮组样式 */
.flex.gap-1 {
  display: flex;
  gap: 4px;
}

.flex.gap-3 {
  display: flex;
  gap: 12px;
  align-items: center;
}

/* 搜索区域样式 */
.space-y-3 > * + * {
  margin-top: 12px;
}

.space-y-4 > * + * {
  margin-top: 16px;
}

.space-y-5 > * + * {
  margin-top: 20px;
}

/* 表单标签样式 */
label.block {
  display: block;
  font-weight: 500;
  color: #374151;
  margin-bottom: 4px;
}

/* 进度条容器样式 */
.progress-container {
  background: #f8fafc;
  border-radius: 8px;
  padding: 16px;
  margin: 16px 0;
}

/* 状态标签样式 */
.n-tag {
  font-size: 12px;
  font-weight: 500;
}

/* 漏洞严重程度颜色 */
.severity-critical {
  color: #dc2626;
  background-color: #fef2f2;
  border-color: #fecaca;
}

.severity-high {
  color: #ea580c;
  background-color: #fff7ed;
  border-color: #fed7aa;
}

.severity-medium {
  color: #d97706;
  background-color: #fffbeb;
  border-color: #fde68a;
}

.severity-low {
  color: #059669;
  background-color: #ecfdf5;
  border-color: #a7f3d0;
}

.severity-info {
  color: #0284c7;
  background-color: #f0f9ff;
  border-color: #bae6fd;
}

/* 任务状态颜色 */
.status-pending {
  color: #6b7280;
  background-color: #f9fafb;
  border-color: #d1d5db;
}

.status-running {
  color: #0284c7;
  background-color: #f0f9ff;
  border-color: #bae6fd;
}

.status-finished {
  color: #059669;
  background-color: #ecfdf5;
  border-color: #a7f3d0;
}

.status-failed {
  color: #dc2626;
  background-color: #fef2f2;
  border-color: #fecaca;
}

.status-stopped {
  color: #d97706;
  background-color: #fffbeb;
  border-color: #fde68a;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .security-platform {
    padding: 10px;
  }
  
  .glass-card {
    padding: 16px !important;
  }
  
  .flex.gap-3 {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }
  
  .n-data-table {
    font-size: 12px;
  }
}

/* 动画效果 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 加载状态 */
.loading-overlay {
  position: relative;
}

.loading-overlay::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}

/* 工具提示样式 */
.tooltip {
  position: relative;
  cursor: help;
}

.tooltip:hover::after {
  content: attr(data-tooltip);
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  background: #1f2937;
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  white-space: nowrap;
  z-index: 1000;
}

/* 扫描工具图标 */
.tool-icon {
  width: 16px;
  height: 16px;
  margin-right: 4px;
}

.tool-nuclei {
  color: #059669;
}

.tool-sqlmap {
  color: #dc2626;
}

.tool-xsstrike {
  color: #d97706;
}

.tool-fuzz {
  color: #7c3aed;
}

/* 统计卡片样式 */
.stats-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 12px;
  padding: 20px;
  text-align: center;
}

.stats-number {
  font-size: 2rem;
  font-weight: bold;
  margin-bottom: 4px;
}

.stats-label {
  font-size: 0.875rem;
  opacity: 0.9;
}

/* 日志级别样式 */
.log-debug {
  color: #6b7280;
}

.log-info {
  color: #0284c7;
}

.log-warning {
  color: #d97706;
}

.log-error {
  color: #dc2626;
}

/* 报告格式图标 */
.format-html::before {
  content: '🌐';
  margin-right: 4px;
}

.format-markdown::before {
  content: '📝';
  margin-right: 4px;
}

.format-json::before {
  content: '📋';
  margin-right: 4px;
}

/* 空状态样式 */
.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: #6b7280;
}

.empty-state-icon {
  font-size: 3rem;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-state-text {
  font-size: 1rem;
  margin-bottom: 8px;
}

.empty-state-subtext {
  font-size: 0.875rem;
  opacity: 0.7;
}
</style>
