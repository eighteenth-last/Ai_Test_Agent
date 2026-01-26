<template>
  <div class="send-mail-container">
    <n-card title="📧 邮件发送记录" :bordered="false">
      <!-- 统计信息 -->
      <div class="stats-grid mb-6">
        <div class="stat-card">
          <div class="stat-icon" style="background: #e3f2fd;">
            <i class="fas fa-paper-plane" style="color: #2196f3;"></i>
          </div>
          <div class="stat-content">
            <p class="stat-value">{{ statistics.total_sends }}</p>
            <p class="stat-label">总发送次数</p>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon" style="background: #e8f5e9;">
            <i class="fas fa-check-circle" style="color: #4caf50;"></i>
          </div>
          <div class="stat-content">
            <p class="stat-value">{{ statistics.total_success_emails }}</p>
            <p class="stat-label">成功邮件数</p>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon" style="background: #ffebee;">
            <i class="fas fa-times-circle" style="color: #f44336;"></i>
          </div>
          <div class="stat-content">
            <p class="stat-value">{{ statistics.total_failed_emails }}</p>
            <p class="stat-label">失败邮件数</p>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon" style="background: #fff3e0;">
            <i class="fas fa-percentage" style="color: #ff9800;"></i>
          </div>
          <div class="stat-content">
            <p class="stat-value">{{ statistics.success_rate }}%</p>
            <p class="stat-label">成功率</p>
          </div>
        </div>
      </div>

      <!-- 筛选器 -->
      <div class="filter-bar mb-4">
        <n-space>
          <n-select
            v-model:value="filterStatus"
            :options="statusOptions"
            placeholder="状态筛选"
            style="width: 150px"
            clearable
            @update:value="loadRecords"
          />
          <n-select
            v-model:value="filterType"
            :options="typeOptions"
            placeholder="类型筛选"
            style="width: 150px"
            clearable
            @update:value="loadRecords"
          />
          <n-button @click="loadRecords" type="primary">
            <template #icon>
              <i class="fas fa-sync-alt"></i>
            </template>
            刷新
          </n-button>
        </n-space>
      </div>

      <!-- 数据表格 -->
      <n-data-table
        :columns="columns"
        :data="records"
        :loading="loading"
        :pagination="pagination"
        :bordered="false"
      />
    </n-card>

    <!-- 详情模态框 -->
    <n-modal v-model:show="showDetailModal">
      <n-card
        style="width: 700px"
        title="邮件发送详情"
        :bordered="false"
        size="huge"
        role="dialog"
        aria-modal="true"
      >
        <template #header-extra>
          <n-button text @click="showDetailModal = false">
            <template #icon>
              <i class="fas fa-times"></i>
            </template>
          </n-button>
        </template>

        <div v-if="selectedRecord">
          <n-descriptions :column="2" bordered>
            <n-descriptions-item label="邮件主题">
              {{ selectedRecord.subject }}
            </n-descriptions-item>
            <n-descriptions-item label="发送状态">
              <n-tag :type="getStatusType(selectedRecord.status)">
                {{ getStatusText(selectedRecord.status) }}
              </n-tag>
            </n-descriptions-item>
            <n-descriptions-item label="邮件类型">
              {{ getTypeText(selectedRecord.email_type) }}
            </n-descriptions-item>
            <n-descriptions-item label="发送时间">
              {{ formatDate(selectedRecord.created_at) }}
            </n-descriptions-item>
            <n-descriptions-item label="成功/失败/总数">
              <span style="color: #4caf50;">{{ selectedRecord.success_count }}</span> / 
              <span style="color: #f44336;">{{ selectedRecord.failed_count }}</span> / 
              {{ selectedRecord.total_count }}
            </n-descriptions-item>
          </n-descriptions>

          <n-divider>内容摘要</n-divider>
          <p class="text-gray-600">{{ selectedRecord.content_summary || '无' }}</p>

          <n-divider>收件人列表</n-divider>
          <div class="recipients-list">
            <div
              v-for="(recipient, index) in selectedRecord.recipients"
              :key="index"
              class="recipient-item"
            >
              <i
                :class="[
                  'fas',
                  recipient.status === 'success' ? 'fa-check-circle text-green-500' :
                  recipient.status === 'skipped' ? 'fa-exclamation-triangle text-orange-500' :
                  'fa-times-circle text-red-500'
                ]"
              ></i>
              <span class="ml-2">{{ recipient.name }} ({{ recipient.email }})</span>
              <span v-if="recipient.error" class="ml-2 text-xs text-gray-400">
                - {{ recipient.error }}
              </span>
            </div>
          </div>

          <n-divider v-if="selectedRecord.email_ids && selectedRecord.email_ids.length > 0">
            Resend Email IDs
          </n-divider>
          <div v-if="selectedRecord.email_ids && selectedRecord.email_ids.length > 0" class="email-ids">
            <n-tag
              v-for="(id, index) in selectedRecord.email_ids"
              :key="index"
              size="small"
              class="mr-2 mb-2"
            >
              {{ id }}
            </n-tag>
          </div>
        </div>
      </n-card>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, onMounted, h } from 'vue'
import {
  NCard,
  NDataTable,
  NButton,
  NTag,
  NSpace,
  NSelect,
  NModal,
  NDescriptions,
  NDescriptionsItem,
  NDivider,
  useMessage,
  useDialog
} from 'naive-ui'
import { emailAPI } from '@/api/index'

const message = useMessage()
const dialog = useDialog()
const loading = ref(false)
const records = ref([])
const statistics = ref({
  total_sends: 0,
  total_success_emails: 0,
  total_failed_emails: 0,
  success_rate: 0
})

const filterStatus = ref(null)
const filterType = ref(null)

const showDetailModal = ref(false)
const selectedRecord = ref(null)

const statusOptions = [
  { label: '全部', value: null },
  { label: '成功', value: 'success' },
  { label: '部分成功', value: 'partial' },
  { label: '失败', value: 'failed' }
]

const typeOptions = [
  { label: '全部', value: null },
  { label: '测试报告', value: 'report' },
  { label: 'Bug通知', value: 'bug' },
  { label: '自定义', value: 'custom' }
]

const pagination = {
  pageSize: 10
}

const columns = [
  {
    title: 'ID',
    key: 'id',
    width: 60
  },
  {
    title: '邮件主题',
    key: 'subject',
    ellipsis: {
      tooltip: true
    }
  },
  {
    title: '类型',
    key: 'email_type',
    width: 100,
    render(row) {
      return getTypeText(row.email_type)
    }
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render(row) {
      return h(
        NTag,
        { type: getStatusType(row.status) },
        { default: () => getStatusText(row.status) }
      )
    }
  },
  {
    title: '收件人',
    key: 'total_count',
    width: 80,
    render(row) {
      return `${row.success_count}/${row.total_count}`
    }
  },
  {
    title: '发送时间',
    key: 'created_at',
    width: 160,
    render(row) {
      return formatDate(row.created_at)
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 150,
    render(row) {
      return h(
        NSpace,
        {},
        {
          default: () => [
            h(
              NButton,
              {
                size: 'small',
                onClick: () => viewDetail(row)
              },
              { default: () => '详情' }
            ),
            h(
              NButton,
              {
                size: 'small',
                type: 'error',
                onClick: () => deleteRecord(row)
              },
              { default: () => '删除' }
            )
          ]
        }
      )
    }
  }
]

// 加载统计信息
const loadStatistics = async () => {
  try {
    const res = await emailAPI.getStatistics()
    if (res.success) {
      statistics.value = res.data
    }
  } catch (error) {
    console.error('加载统计信息失败:', error)
  }
}

// 加载记录列表
const loadRecords = async () => {
  loading.value = true
  try {
    const params = {
      limit: 100,
      offset: 0
    }
    
    if (filterStatus.value) {
      params.status = filterStatus.value
    }
    
    if (filterType.value) {
      params.email_type = filterType.value
    }
    
    const res = await emailAPI.getRecords(params)
    records.value = Array.isArray(res) ? res : []
  } catch (error) {
    console.error('加载记录失败:', error)
    message.error('加载记录失败')
  } finally {
    loading.value = false
  }
}

// 查看详情
const viewDetail = async (row) => {
  try {
    const res = await emailAPI.getRecordDetail(row.id)
    selectedRecord.value = res
    showDetailModal.value = true
  } catch (error) {
    console.error('加载详情失败:', error)
    message.error('加载详情失败')
  }
}

// 删除记录
const deleteRecord = (row) => {
  dialog.warning({
    title: '确认删除',
    content: '确定要删除这条发送记录吗？',
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res = await emailAPI.deleteRecord(row.id)
        if (res.success) {
          message.success('删除成功')
          loadRecords()
          loadStatistics()
        }
      } catch (error) {
        message.error('删除失败')
      }
    }
  })
}

// 格式化日期
const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 获取状态类型
const getStatusType = (status) => {
  const types = {
    success: 'success',
    partial: 'warning',
    failed: 'error'
  }
  return types[status] || 'default'
}

// 获取状态文本
const getStatusText = (status) => {
  const texts = {
    success: '成功',
    partial: '部分成功',
    failed: '失败'
  }
  return texts[status] || status
}

// 获取类型文本
const getTypeText = (type) => {
  const texts = {
    report: '测试报告',
    bug: 'Bug通知',
    custom: '自定义'
  }
  return texts[type] || type
}

onMounted(() => {
  loadStatistics()
  loadRecords()
})
</script>

<style scoped>
.send-mail-container {
  padding: 20px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

.stat-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 15px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: transform 0.2s;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.stat-icon {
  width: 50px;
  height: 50px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #333;
  margin: 0;
}

.stat-label {
  font-size: 13px;
  color: #666;
  margin: 5px 0 0 0;
}

.filter-bar {
  background: #f5f5f5;
  padding: 15px;
  border-radius: 8px;
}

.recipients-list {
  max-height: 300px;
  overflow-y: auto;
}

.recipient-item {
  padding: 10px;
  border-bottom: 1px solid #eee;
  display: flex;
  align-items: center;
}

.recipient-item:last-child {
  border-bottom: none;
}

.email-ids {
  display: flex;
  flex-wrap: wrap;
}
</style>
