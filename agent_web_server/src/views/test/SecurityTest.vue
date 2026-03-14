<template>
  <div class="security-scan-page">
    <!-- 首页视图 -->
    <div v-if="currentView === 'home'" class="home-view">

      <!-- 输入区域 -->
      <div class="input-section glass-card">
        <div class="input-label">
          <iconify-icon icon="mdi:web" class="label-icon"></iconify-icon>
          <span>目标网址</span>
        </div>
        <n-input
          v-model:value="scanUrl"
          size="large"
          placeholder="https://example.com"
          clearable
          @keyup.enter="startQuickScan"
        >
          <template #prefix>
            <iconify-icon icon="mdi:web" style="font-size: 18px; color: #9ca3af;"></iconify-icon>
          </template>
        </n-input>

        <!-- 扫描类型选择 -->
        <div class="scan-types">
          <div 
            class="scan-type" 
            :class="{active: scanType === 'quick'}"
            @click="scanType = 'quick'"
          >
            <iconify-icon icon="mdi:lightning-bolt" class="type-icon"></iconify-icon>
            <div class="type-info">
              <div class="type-name">快速扫描</div>
              <div class="type-desc">5-10分钟，检测常见漏洞</div>
            </div>
            <iconify-icon 
              v-if="scanType === 'quick'" 
              icon="mdi:check-circle" 
              class="check-icon"
            ></iconify-icon>
          </div>

          <div 
            class="scan-type" 
            :class="{active: scanType === 'full'}"
            @click="scanType = 'full'"
          >
            <iconify-icon icon="mdi:magnify-scan" class="type-icon"></iconify-icon>
            <div class="type-info">
              <div class="type-name">全面扫描</div>
              <div class="type-desc">20-30分钟，深度安全检测</div>
            </div>
            <iconify-icon 
              v-if="scanType === 'full'" 
              icon="mdi:check-circle" 
              class="check-icon"
            ></iconify-icon>
          </div>
        </div>

        <!-- 开始扫描按钮 -->
        <n-button 
          type="primary" 
          size="large" 
          block 
          :loading="isStarting"
          @click="startQuickScan"
        >
          <template #icon>
            <iconify-icon icon="mdi:play" style="font-size: 20px;"></iconify-icon>
          </template>
          开始扫描
        </n-button>
      </div>

      <!-- 最近扫描 -->
      <div v-if="scanHistory.length > 0" class="history-section glass-card">
        <div class="section-header">
          <iconify-icon icon="mdi:history" class="section-icon"></iconify-icon>
          <span class="section-title">最近扫描</span>
        </div>
        <div class="history-list">
          <div 
            v-for="item in scanHistory" 
            :key="item.id" 
            class="history-item"
            @click="viewScanResult(item)"
          >
            <div class="history-info">
              <div class="history-url">{{ getTargetUrl(item.target_id) }}</div>
              <div class="history-time">{{ formatTime(item.created_at) }}</div>
            </div>
            <div class="history-status">
              <iconify-icon 
                v-if="item.status === 'finished'" 
                icon="mdi:check-circle" 
                class="status-icon success"
              ></iconify-icon>
              <iconify-icon 
                v-else-if="item.status === 'running'" 
                icon="mdi:loading" 
                class="status-icon running rotating"
              ></iconify-icon>
              <iconify-icon 
                v-else-if="item.status === 'failed'" 
                icon="mdi:close-circle" 
                class="status-icon error"
              ></iconify-icon>
              <span class="status-text">{{ getStatusText(item.status) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 扫描中视图 -->
    <div v-if="currentView === 'scanning'" class="scanning-view">
      <div class="scanning-card glass-card">
        <div class="scanning-header">
          <iconify-icon icon="mdi:shield-search" class="scanning-icon rotating"></iconify-icon>
          <div class="scanning-title">
            <h2>正在扫描</h2>
            <p class="scanning-url">{{ scanUrl }}</p>
          </div>
        </div>

        <!-- 进度条 -->
        <div class="progress-section">
          <n-progress 
            type="line" 
            :percentage="scanProgress" 
            :indicator-placement="'inside'"
            processing
          />
        </div>

        <!-- 扫描信息 -->
        <div class="scanning-info">
          <div class="info-item">
            <iconify-icon icon="mdi:progress-clock" class="info-icon"></iconify-icon>
            <span class="info-label">当前阶段：</span>
            <span class="info-value">{{ scanStage }}</span>
          </div>
          <div class="info-item">
            <iconify-icon icon="mdi:alert-circle" class="info-icon"></iconify-icon>
            <span class="info-label">已发现：</span>
            <span class="info-value">{{ foundVulns.length }} 个漏洞</span>
          </div>
        </div>

        <!-- 实时发现的漏洞 -->
        <div v-if="foundVulns.length > 0" class="realtime-vulns">
          <div class="realtime-header">
            <iconify-icon icon="mdi:eye" class="realtime-icon"></iconify-icon>
            <span>实时发现</span>
          </div>
          <div class="vuln-list">
            <div 
              v-for="vuln in foundVulns.slice(0, 5)" 
              :key="vuln.id"
              class="vuln-item-mini"
            >
              <iconify-icon 
                :icon="getSeverityIcon(vuln.severity)" 
                :class="['severity-icon', vuln.severity]"
              ></iconify-icon>
              <span class="vuln-title-mini">{{ vuln.title }}</span>
            </div>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="scanning-actions">
          <n-button @click="minimizeScanning">
            <template #icon>
              <iconify-icon icon="mdi:window-minimize"></iconify-icon>
            </template>
            最小化
          </n-button>
          <n-button type="error" @click="stopScanning">
            <template #icon>
              <iconify-icon icon="mdi:stop"></iconify-icon>
            </template>
            停止扫描
          </n-button>
        </div>
      </div>
    </div>

    <!-- 结果视图 -->
    <div v-if="currentView === 'result'" class="result-view">
      <div class="result-card glass-card">
        <!-- 结果标题 -->
        <div class="result-header">
          <iconify-icon icon="mdi:check-circle" class="result-icon success"></iconify-icon>
          <div class="result-title">
            <h2>扫描完成</h2>
            <p class="result-url">{{ scanUrl }}</p>
          </div>
        </div>

        <!-- 扫描统计 -->
        <div class="result-stats">
          <div class="stat-item">
            <iconify-icon icon="mdi:clock-outline" class="stat-icon"></iconify-icon>
            <span class="stat-label">耗时</span>
            <span class="stat-value">{{ scanDuration }}</span>
          </div>
          <div class="stat-item">
            <iconify-icon icon="mdi:shield-alert" class="stat-icon"></iconify-icon>
            <span class="stat-label">风险等级</span>
            <span class="stat-value" :class="riskLevelClass">{{ riskLevel }}</span>
          </div>
        </div>

        <!-- 漏洞概览 -->
        <div class="overview-section">
          <div class="section-header">
            <iconify-icon icon="mdi:chart-bar" class="section-icon"></iconify-icon>
            <span class="section-title">漏洞概览</span>
          </div>
          <div class="overview-stats">
            <div class="overview-item critical">
              <iconify-icon icon="mdi:alert-octagon" class="overview-icon"></iconify-icon>
              <div class="overview-number">{{ vulnStats.critical }}</div>
              <div class="overview-label">严重</div>
            </div>
            <div class="overview-item high">
              <iconify-icon icon="mdi:alert" class="overview-icon"></iconify-icon>
              <div class="overview-number">{{ vulnStats.high }}</div>
              <div class="overview-label">高危</div>
            </div>
            <div class="overview-item medium">
              <iconify-icon icon="mdi:alert-circle" class="overview-icon"></iconify-icon>
              <div class="overview-number">{{ vulnStats.medium }}</div>
              <div class="overview-label">中危</div>
            </div>
            <div class="overview-item low">
              <iconify-icon icon="mdi:information" class="overview-icon"></iconify-icon>
              <div class="overview-number">{{ vulnStats.low }}</div>
              <div class="overview-label">低危</div>
            </div>
          </div>
        </div>

        <!-- 漏洞详情 -->
        <div v-if="vulnerabilities.length > 0" class="vulns-section">
          <div class="section-header">
            <iconify-icon icon="mdi:bug" class="section-icon"></iconify-icon>
            <span class="section-title">漏洞详情</span>
          </div>
          <div class="vulns-list">
            <div 
              v-for="vuln in vulnerabilities" 
              :key="vuln.id"
              class="vuln-item"
            >
              <div class="vuln-header">
                <span class="vuln-severity-badge" :class="vuln.severity">
                  <iconify-icon :icon="getSeverityIcon(vuln.severity)"></iconify-icon>
                  {{ getSeverityLabel(vuln.severity) }}
                </span>
                <span class="vuln-title">{{ vuln.title }}</span>
              </div>
              <div class="vuln-body">
                <div class="vuln-field">
                  <iconify-icon icon="mdi:link-variant" class="field-icon"></iconify-icon>
                  <span class="field-label">URL:</span>
                  <span class="field-value">{{ vuln.url || '未知' }}</span>
                </div>
                <div v-if="vuln.description" class="vuln-field">
                  <iconify-icon icon="mdi:file-document-outline" class="field-icon"></iconify-icon>
                  <span class="field-label">描述:</span>
                  <span class="field-value">{{ vuln.description }}</span>
                </div>
              </div>
              <div class="vuln-actions">
                <n-button size="small" @click="viewVulnDetail(vuln)">
                  <template #icon>
                    <iconify-icon icon="mdi:eye"></iconify-icon>
                  </template>
                  查看详情
                </n-button>
                <n-button size="small" type="success" @click="markAsFixed(vuln)">
                  <template #icon>
                    <iconify-icon icon="mdi:check"></iconify-icon>
                  </template>
                  标记已修复
                </n-button>
              </div>
            </div>
          </div>
        </div>

        <!-- 无漏洞状态 -->
        <div v-else class="no-vulns">
          <iconify-icon icon="mdi:shield-check" class="no-vulns-icon"></iconify-icon>
          <p class="no-vulns-text">未发现安全漏洞</p>
          <p class="no-vulns-subtext">目标网站安全性良好</p>
        </div>

        <!-- 操作按钮 -->
        <div class="result-actions">
          <n-button @click="backToHome">
            <template #icon>
              <iconify-icon icon="mdi:home"></iconify-icon>
            </template>
            返回首页
          </n-button>
          <n-button type="primary" @click="rescan">
            <template #icon>
              <iconify-icon icon="mdi:refresh"></iconify-icon>
            </template>
            重新扫描
          </n-button>
          <n-button type="info" @click="downloadReport">
            <template #icon>
              <iconify-icon icon="mdi:download"></iconify-icon>
            </template>
            下载报告
          </n-button>
        </div>
      </div>
    </div>

    <!-- 漏洞详情弹窗 -->
    <n-modal v-model:show="showVulnDetail" preset="card" title="漏洞详情" style="width: 800px">
      <div v-if="selectedVuln" class="vuln-detail">
        <div class="detail-field">
          <iconify-icon icon="mdi:alert-circle-outline" class="detail-icon"></iconify-icon>
          <span class="detail-label">严重程度</span>
          <span class="vuln-severity-badge" :class="selectedVuln.severity">
            <iconify-icon :icon="getSeverityIcon(selectedVuln.severity)"></iconify-icon>
            {{ getSeverityLabel(selectedVuln.severity) }}
          </span>
        </div>
        <div class="detail-field">
          <iconify-icon icon="mdi:text" class="detail-icon"></iconify-icon>
          <span class="detail-label">标题</span>
          <span class="detail-value">{{ selectedVuln.title }}</span>
        </div>
        <div class="detail-field">
          <iconify-icon icon="mdi:link-variant" class="detail-icon"></iconify-icon>
          <span class="detail-label">URL</span>
          <span class="detail-value">{{ selectedVuln.url || '未知' }}</span>
        </div>
        <div v-if="selectedVuln.description" class="detail-field">
          <iconify-icon icon="mdi:file-document-outline" class="detail-icon"></iconify-icon>
          <span class="detail-label">描述</span>
          <span class="detail-value">{{ selectedVuln.description }}</span>
        </div>
        <div v-if="selectedVuln.fix_suggestion" class="detail-field">
          <iconify-icon icon="mdi:wrench" class="detail-icon"></iconify-icon>
          <span class="detail-label">修复建议</span>
          <span class="detail-value">{{ selectedVuln.fix_suggestion }}</span>
        </div>
      </div>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useMessage } from 'naive-ui'
import { NInput, NButton, NProgress, NModal } from 'naive-ui'
import { securityAPI } from '@/api/index.js'

const message = useMessage()

// 视图状态
const currentView = ref('home') // home | scanning | result

// 扫描配置
const scanUrl = ref('')
const scanType = ref('quick') // quick | full
const isStarting = ref(false)

// 扫描状态
const currentScan = ref(null)
const scanProgress = ref(0)
const scanStage = ref('初始化...')
const foundVulns = ref([])

// 扫描结果
const vulnerabilities = ref([])
const scanDuration = ref('')
const riskLevel = ref('低危')

// 历史记录
const scanHistory = ref([])
const targetMap = ref({})

// 漏洞详情
const showVulnDetail = ref(false)
const selectedVuln = ref(null)

// 轮询定时器
let pollTimer = null

// 计算属性
const vulnStats = computed(() => {
  const stats = { critical: 0, high: 0, medium: 0, low: 0, info: 0 }
  vulnerabilities.value.forEach(vuln => {
    if (stats[vuln.severity] !== undefined) {
      stats[vuln.severity]++
    }
  })
  return stats
})

const riskLevelClass = computed(() => {
  if (vulnStats.value.critical > 0) return 'risk-critical'
  if (vulnStats.value.high > 0) return 'risk-high'
  if (vulnStats.value.medium > 0) return 'risk-medium'
  return 'risk-low'
})

// 工具函数
function getSeverityIcon(severity) {
  const icons = {
    critical: 'mdi:alert-octagon',
    high: 'mdi:alert',
    medium: 'mdi:alert-circle',
    low: 'mdi:information',
    info: 'mdi:information-outline'
  }
  return icons[severity] || 'mdi:help-circle'
}

function getSeverityLabel(severity) {
  const labels = { critical: '严重', high: '高危', medium: '中危', low: '低危', info: '信息' }
  return labels[severity] || severity
}

function getStatusText(status) {
  const texts = { 
    pending: '等待中', 
    running: '扫描中', 
    finished: '已完成', 
    failed: '失败', 
    stopped: '已停止' 
  }
  return texts[status] || status
}

function formatTime(timeStr) {
  if (!timeStr) return '-'
  const date = new Date(timeStr)
  const now = new Date()
  const diff = now - date
  
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return date.toLocaleDateString('zh-CN')
}

function getTargetUrl(targetId) {
  return targetMap.value[targetId] || '未知目标'
}

// API 方法
async function startQuickScan() {
  if (!scanUrl.value) {
    message.warning('请输入目标网址')
    return
  }
  
  if (!scanUrl.value.startsWith('http://') && !scanUrl.value.startsWith('https://')) {
    message.warning('请输入完整的URL（包含http://或https://）')
    return
  }
  
  isStarting.value = true
  
  try {
    // 1. 创建目标
    const targetRes = await securityAPI.createTarget({
      name: scanUrl.value,
      base_url: scanUrl.value,
      description: `自动创建 - ${new Date().toLocaleString()}`
    })
    
    if (!targetRes.success) {
      message.error(targetRes.message || '创建目标失败')
      return
    }
    
    const targetId = targetRes.data.id
    targetMap.value[targetId] = scanUrl.value
    
    // 2. 创建扫描任务
    const scanTypeMap = {
      quick: 'nuclei',
      full: 'full_scan'
    }
    
    const taskRes = await securityAPI.createScan({
      target_id: targetId,
      scan_type: scanTypeMap[scanType.value]
    })
    
    if (!taskRes.success) {
      message.error(taskRes.message || '创建扫描任务失败')
      return
    }
    
    currentScan.value = taskRes.data
    
    // 3. 切换到扫描中视图
    currentView.value = 'scanning'
    scanProgress.value = 0
    scanStage.value = '初始化...'
    foundVulns.value = []
    
    // 4. 开始轮询
    startPolling()
    
    message.success('扫描已开始')
  } catch (error) {
    console.error('启动扫描失败:', error)
    message.error('启动扫描失败')
  } finally {
    isStarting.value = false
  }
}

function startPolling() {
  stopPolling()
  
  pollTimer = setInterval(async () => {
    if (!currentScan.value) {
      stopPolling()
      return
    }
    
    try {
      const res = await securityAPI.getTask(currentScan.value.id)
      if (!res.success) return
      
      const task = res.data
      
      // 更新进度
      scanProgress.value = task.progress || 0
      
      // 更新阶段
      if (scanProgress.value < 10) {
        scanStage.value = '初始化...'
      } else if (scanProgress.value < 30) {
        scanStage.value = '漏洞扫描中...'
      } else if (scanProgress.value < 60) {
        scanStage.value = 'SQL注入检测...'
      } else if (scanProgress.value < 80) {
        scanStage.value = 'XSS漏洞检测...'
      } else if (scanProgress.value < 95) {
        scanStage.value = '生成报告...'
      } else {
        scanStage.value = '即将完成...'
      }
      
      // 加载实时发现的漏洞
      if (scanProgress.value > 20) {
        await loadRealtimeVulns()
      }
      
      // 检查是否完成
      if (task.status === 'finished') {
        stopPolling()
        await loadScanResult()
        currentView.value = 'result'
        message.success('扫描完成')
      } else if (task.status === 'failed') {
        stopPolling()
        message.error('扫描失败')
        currentView.value = 'home'
      } else if (task.status === 'stopped') {
        stopPolling()
        message.warning('扫描已停止')
        currentView.value = 'home'
      }
    } catch (error) {
      console.error('轮询任务状态失败:', error)
    }
  }, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function loadRealtimeVulns() {
  try {
    const res = await securityAPI.getVulnerabilities({
      task_id: currentScan.value.id
    })
    if (res.success) {
      foundVulns.value = res.data || []
    }
  } catch (error) {
    console.error('加载实时漏洞失败:', error)
  }
}

async function loadScanResult() {
  try {
    // 加载漏洞列表
    const vulnRes = await securityAPI.getVulnerabilities({
      task_id: currentScan.value.id
    })
    if (vulnRes.success) {
      vulnerabilities.value = vulnRes.data || []
    }
    
    // 计算扫描时长
    const task = await securityAPI.getTask(currentScan.value.id)
    if (task.success && task.data.created_at) {
      const start = new Date(task.data.created_at)
      const end = new Date()
      const duration = Math.floor((end - start) / 1000)
      const minutes = Math.floor(duration / 60)
      const seconds = duration % 60
      scanDuration.value = `${minutes}分${seconds}秒`
    }
    
    // 计算风险等级
    if (vulnStats.value.critical > 0) {
      riskLevel.value = '严重'
    } else if (vulnStats.value.high > 0) {
      riskLevel.value = '高危'
    } else if (vulnStats.value.medium > 0) {
      riskLevel.value = '中危'
    } else if (vulnStats.value.low > 0) {
      riskLevel.value = '低危'
    } else {
      riskLevel.value = '安全'
    }
  } catch (error) {
    console.error('加载扫描结果失败:', error)
    message.error('加载扫描结果失败')
  }
}

async function loadHistory() {
  try {
    const res = await securityAPI.getTasks()
    if (res.success) {
      scanHistory.value = (res.data || [])
        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
        .slice(0, 5)
      
      // 加载目标信息
      const targetIds = [...new Set(scanHistory.value.map(item => item.target_id))]
      if (targetIds.length > 0) {
        const targetsRes = await securityAPI.getTargets()
        if (targetsRes.success) {
          const targets = targetsRes.data || []
          targets.forEach(target => {
            targetMap.value[target.id] = target.base_url
          })
        }
      }
    }
  } catch (error) {
    console.error('加载历史记录失败:', error)
  }
}

async function viewScanResult(item) {
  currentScan.value = item
  scanUrl.value = getTargetUrl(item.target_id)
  await loadScanResult()
  currentView.value = 'result'
}

function minimizeScanning() {
  currentView.value = 'home'
  message.info('扫描将在后台继续进行')
}

async function stopScanning() {
  if (!currentScan.value) return
  
  try {
    const res = await securityAPI.stopTask(currentScan.value.id)
    if (res.success) {
      stopPolling()
      message.success('扫描已停止')
      currentView.value = 'home'
    } else {
      message.error(res.message || '停止扫描失败')
    }
  } catch (error) {
    console.error('停止扫描失败:', error)
    message.error('停止扫描失败')
  }
}

function backToHome() {
  currentView.value = 'home'
  currentScan.value = null
  vulnerabilities.value = []
  loadHistory()
}

function rescan() {
  currentView.value = 'home'
  startQuickScan()
}

async function downloadReport() {
  if (!currentScan.value) return
  
  try {
    message.loading('正在生成报告...')
    const res = await securityAPI.generateReport({
      task_id: currentScan.value.id,
      format: 'html'
    })
    
    if (res.success) {
      message.success('报告生成成功，开始下载')
      // 这里需要实现下载逻辑
    } else {
      message.error(res.message || '生成报告失败')
    }
  } catch (error) {
    console.error('下载报告失败:', error)
    message.error('下载报告失败')
  }
}

function viewVulnDetail(vuln) {
  selectedVuln.value = vuln
  showVulnDetail.value = true
}

async function markAsFixed(vuln) {
  try {
    const res = await securityAPI.updateVulnerability(vuln.id, {
      status: 'fixed'
    })
    if (res.success) {
      message.success('已标记为已修复')
      await loadScanResult()
    } else {
      message.error(res.message || '更新失败')
    }
  } catch (error) {
    console.error('标记失败:', error)
    message.error('标记失败')
  }
}

// 生命周期
onMounted(() => {
  loadHistory()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.security-scan-page {
  max-width: 1400px;
  margin: 0 auto;
  padding: 16px;
}

/* 玻璃卡片效果 */
.glass-card {
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(102, 126, 234, 0.1);
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  backdrop-filter: blur(10px);
  padding: 20px;
  margin-bottom: 16px;
}

/* 页面标题 */
.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.header-icon {
  font-size: 40px;
  color: #667eea;
}

.header-text {
  flex: 1;
}

.page-title {
  font-size: 28px;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 4px 0;
}

.page-subtitle {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

/* 输入区域 */
.input-section {
  margin-bottom: 16px;
}

.input-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
}

.label-icon {
  font-size: 18px;
  color: #667eea;
}

/* 扫描类型选择 */
.scan-types {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin: 16px 0;
}

.scan-type {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border: 2px solid #e5e7eb;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.3s ease;
  background: white;
}

.scan-type:hover {
  border-color: #667eea;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
  transform: translateY(-2px);
}

.scan-type.active {
  border-color: #667eea;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
}

.type-icon {
  font-size: 28px;
  color: #667eea;
}

.type-info {
  flex: 1;
}

.type-name {
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 2px;
}

.type-desc {
  font-size: 12px;
  color: #6b7280;
}

.check-icon {
  font-size: 20px;
  color: #667eea;
}

/* 历史记录 */
.history-section {
  margin-bottom: 16px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.section-icon {
  font-size: 18px;
  color: #667eea;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.history-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: white;
}

.history-item:hover {
  border-color: #667eea;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.1);
}

.history-info {
  flex: 1;
}

.history-url {
  font-size: 14px;
  font-weight: 500;
  color: #1f2937;
  margin-bottom: 2px;
}

.history-time {
  font-size: 12px;
  color: #9ca3af;
}

.history-status {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-icon {
  font-size: 16px;
}

.status-icon.success {
  color: #059669;
}

.status-icon.running {
  color: #0284c7;
}

.status-icon.error {
  color: #dc2626;
}

.status-text {
  font-size: 13px;
  font-weight: 500;
  color: #6b7280;
}

/* 扫描中视图 */
.scanning-view {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}

.scanning-card {
  width: 100%;
  max-width: 900px;
}

.scanning-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.scanning-icon {
  font-size: 40px;
  color: #667eea;
}

.scanning-title h2 {
  font-size: 22px;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 4px 0;
}

.scanning-url {
  font-size: 13px;
  color: #6b7280;
  margin: 0;
}

.progress-section {
  margin: 20px 0;
}

.scanning-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 20px 0;
  padding: 14px;
  background: #f9fafb;
  border-radius: 8px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.info-icon {
  font-size: 16px;
  color: #667eea;
}

.info-label {
  font-size: 13px;
  color: #6b7280;
}

.info-value {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
}

.realtime-vulns {
  margin: 20px 0;
  padding: 14px;
  background: #fef3c7;
  border: 1px solid #fbbf24;
  border-radius: 8px;
}

.realtime-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #92400e;
  margin-bottom: 10px;
}

.realtime-icon {
  font-size: 16px;
}

.vuln-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.vuln-item-mini {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  background: white;
  border-radius: 6px;
}

.severity-icon {
  font-size: 16px;
}

.severity-icon.critical {
  color: #dc2626;
}

.severity-icon.high {
  color: #ea580c;
}

.severity-icon.medium {
  color: #d97706;
}

.severity-icon.low {
  color: #059669;
}

.vuln-title-mini {
  font-size: 13px;
  color: #1f2937;
}

.scanning-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 20px;
}

/* 结果视图 */
.result-view {
  display: flex;
  justify-content: center;
}

.result-card {
  width: 100%;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.result-icon {
  font-size: 40px;
}

.result-icon.success {
  color: #059669;
}

.result-title h2 {
  font-size: 22px;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 4px 0;
}

.result-url {
  font-size: 13px;
  color: #6b7280;
  margin: 0;
}

.result-stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin: 20px 0;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px;
  background: #f9fafb;
  border-radius: 8px;
}

.stat-icon {
  font-size: 22px;
  color: #667eea;
}

.stat-label {
  font-size: 13px;
  color: #6b7280;
  margin-right: auto;
}

.stat-value {
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
}

.stat-value.risk-critical {
  color: #dc2626;
}

.stat-value.risk-high {
  color: #ea580c;
}

.stat-value.risk-medium {
  color: #d97706;
}

.stat-value.risk-low {
  color: #059669;
}

.overview-section {
  margin: 24px 0;
}

.overview-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.overview-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 18px;
  border-radius: 10px;
  text-align: center;
}

.overview-item.critical {
  background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
  border: 2px solid #fecaca;
}

.overview-item.high {
  background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
  border: 2px solid #fed7aa;
}

.overview-item.medium {
  background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
  border: 2px solid #fde68a;
}

.overview-item.low {
  background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
  border: 2px solid #bbf7d0;
}

.overview-icon {
  font-size: 28px;
  margin-bottom: 6px;
}

.overview-item.critical .overview-icon {
  color: #dc2626;
}

.overview-item.high .overview-icon {
  color: #ea580c;
}

.overview-item.medium .overview-icon {
  color: #d97706;
}

.overview-item.low .overview-icon {
  color: #059669;
}

.overview-number {
  font-size: 28px;
  font-weight: 700;
  margin-bottom: 2px;
}

.overview-item.critical .overview-number {
  color: #dc2626;
}

.overview-item.high .overview-number {
  color: #ea580c;
}

.overview-item.medium .overview-number {
  color: #d97706;
}

.overview-item.low .overview-number {
  color: #059669;
}

.overview-label {
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
}

.vulns-section {
  margin: 24px 0;
}

.vulns-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.vuln-item {
  padding: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: white;
}

.vuln-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.vuln-severity-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
}

.vuln-severity-badge.critical {
  background: #fef2f2;
  color: #dc2626;
}

.vuln-severity-badge.high {
  background: #fff7ed;
  color: #ea580c;
}

.vuln-severity-badge.medium {
  background: #fffbeb;
  color: #d97706;
}

.vuln-severity-badge.low {
  background: #f0fdf4;
  color: #059669;
}

.vuln-title {
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
}

.vuln-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}

.vuln-field {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
}

.field-icon {
  font-size: 16px;
  color: #9ca3af;
  margin-top: 2px;
}

.field-label {
  color: #6b7280;
  font-weight: 500;
  min-width: 50px;
}

.field-value {
  color: #1f2937;
  flex: 1;
  word-break: break-all;
}

.vuln-actions {
  display: flex;
  gap: 8px;
}

.no-vulns {
  text-align: center;
  padding: 50px 20px;
}

.no-vulns-icon {
  font-size: 56px;
  color: #059669;
  margin-bottom: 12px;
}

.no-vulns-text {
  font-size: 17px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 6px 0;
}

.no-vulns-subtext {
  font-size: 13px;
  color: #6b7280;
  margin: 0;
}

.result-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-top: 24px;
}

/* 漏洞详情弹窗 */
.vuln-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-field {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.detail-icon {
  font-size: 18px;
  color: #667eea;
  margin-top: 2px;
}

.detail-label {
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  min-width: 70px;
}

.detail-value {
  font-size: 13px;
  color: #1f2937;
  flex: 1;
}

/* 旋转动画 */
.rotating {
  animation: rotate 2s linear infinite;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* 响应式设计 */
@media (max-width: 768px) {
  .security-scan-page {
    padding: 10px;
  }

  .glass-card {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
    text-align: center;
  }

  .header-icon {
    font-size: 36px;
  }

  .page-title {
    font-size: 24px;
  }

  .scan-types {
    grid-template-columns: 1fr;
  }

  .overview-stats {
    grid-template-columns: repeat(2, 1fr);
  }

  .result-stats {
    grid-template-columns: 1fr;
  }

  .result-actions {
    flex-direction: column;
  }

  .scanning-actions {
    flex-direction: column;
  }
}
</style>
