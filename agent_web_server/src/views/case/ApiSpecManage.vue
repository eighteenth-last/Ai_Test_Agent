<template>
  <div class="spec-manage-container">
    <!-- 顶部操作栏 -->
    <n-card>
      <template #header>
        <div class="flex items-center gap-2">
          <i class="fas fa-file-code text-xl" style="color:#007857"></i>
          <span class="text-lg font-bold">接口文件管理</span>
        </div>
      </template>
      <template #header-extra>
        <n-button type="primary" @click="showUploadModal = true">
          <template #icon><i class="fas fa-cloud-upload-alt"></i></template>
          上传接口文件
        </n-button>
      </template>
      <p class="text-gray-500">管理上传到 MinIO 的 Markdown 接口文档，系统自动解析接口信息用于智能匹配</p>
    </n-card>

    <!-- 筛选 -->
    <div class="flex items-center gap-4 mt-4 mb-4">
      <n-input v-model:value="searchText" placeholder="搜索文件名..." clearable style="width:280px">
        <template #prefix><i class="fas fa-search text-gray-400"></i></template>
      </n-input>
      <n-select v-model:value="filterService" :options="serviceOptions" clearable placeholder="按服务筛选" style="width:180px" />
      <div class="flex-1"></div>
      <span class="text-gray-400 text-sm">共 {{ filteredList.length }} 个文件</span>
    </div>

    <!-- 卡片列表 -->
    <n-spin :show="loading">
      <div v-if="filteredList.length === 0 && !loading" class="text-center py-16 text-gray-400">
        <i class="fas fa-inbox text-5xl mb-4 block"></i>
        <p>暂无接口文件，点击右上角上传</p>
      </div>
      <div v-else class="spec-grid">
        <div v-for="spec in filteredList" :key="spec.id" class="spec-card">
          <div class="spec-card-header">
            <div class="spec-icon">
              <i class="fas fa-file-alt"></i>
            </div>
            <div class="spec-meta">
              <h4 class="spec-filename" :title="spec.original_filename">{{ spec.original_filename }}</h4>
              <span class="spec-service">{{ spec.service_name || 'default' }}</span>
            </div>
          </div>
          <div class="spec-card-body">
            <div class="spec-stat-row">
              <div class="spec-stat">
                <span class="spec-stat-value">{{ spec.endpoint_count }}</span>
                <span class="spec-stat-label">接口数</span>
              </div>
              <div class="spec-stat">
                <span class="spec-stat-value">{{ formatSize(spec.file_size) }}</span>
                <span class="spec-stat-label">文件大小</span>
              </div>
            </div>
            <div v-if="spec.parse_warnings && spec.parse_warnings.length > 0" class="spec-warning">
              <i class="fas fa-exclamation-triangle"></i>
              {{ spec.parse_warnings[0] }}
            </div>
            <p class="spec-time">{{ formatTime(spec.created_at) }}</p>
          </div>
          <div class="spec-card-footer">
            <n-button size="small" quaternary @click="viewDetail(spec)">
              <template #icon><i class="fas fa-eye"></i></template>
              查看
            </n-button>
            <n-button size="small" quaternary @click="viewContent(spec)">
              <template #icon><i class="fas fa-code"></i></template>
              原文
            </n-button>
            <n-button size="small" quaternary type="error" @click="confirmDelete(spec)">
              <template #icon><i class="fas fa-trash"></i></template>
              删除
            </n-button>
          </div>
        </div>
      </div>
    </n-spin>

    <!-- 上传弹窗 -->
    <n-modal v-model:show="showUploadModal" preset="card" title="上传接口文件" style="width:520px">
      <n-form label-placement="left" label-width="80">
        <n-form-item label="服务名称">
          <n-input v-model:value="uploadForm.serviceName" placeholder="可选，用于分组管理" />
        </n-form-item>
        <n-form-item label="Markdown">
          <n-upload
            :max="1"
            accept=".md"
            :default-upload="false"
            @change="handleFileChange"
          >
            <n-button>
              <template #icon><i class="fas fa-paperclip"></i></template>
              选择 .md 文件
            </n-button>
          </n-upload>
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="flex justify-end gap-2">
          <n-button @click="showUploadModal = false">取消</n-button>
          <n-button type="primary" :loading="uploading" :disabled="!uploadForm.file" @click="doUpload">
            <template #icon><i class="fas fa-upload"></i></template>
            上传并解析
          </n-button>
        </div>
      </template>
    </n-modal>

    <!-- 详情弹窗 -->
    <n-modal v-model:show="showDetailModal" preset="card" title="接口文件详情" style="width:800px">
      <n-spin :show="detailLoading">
        <div v-if="currentDetail">
          <n-descriptions :column="2" label-placement="left" bordered size="small" class="mb-4">
            <n-descriptions-item label="文件名">{{ currentDetail.original_filename }}</n-descriptions-item>
            <n-descriptions-item label="服务">{{ currentDetail.service_name || 'default' }}</n-descriptions-item>
            <n-descriptions-item label="接口数">{{ currentDetail.endpoint_count }}</n-descriptions-item>
            <n-descriptions-item label="MinIO Key">
              <span class="text-xs text-gray-400 break-all">{{ currentDetail.minio_key }}</span>
            </n-descriptions-item>
          </n-descriptions>

          <h4 class="font-bold mb-2">接口列表</h4>
          <n-data-table
            :columns="endpointColumns"
            :data="currentDetail.endpoints || []"
            :max-height="360"
            size="small"
            striped
          />
        </div>
      </n-spin>
    </n-modal>

    <!-- 原文弹窗 -->
    <n-modal v-model:show="showContentModal" preset="card" title="Markdown 原文" style="width:800px">
      <n-spin :show="contentLoading">
        <div class="markdown-raw">
          <pre>{{ rawContent }}</pre>
        </div>
      </n-spin>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import {
  NCard, NButton, NInput, NSelect, NModal, NForm, NFormItem, NUpload,
  NDescriptions, NDescriptionsItem, NDataTable, NTag, NSpin, useMessage, useDialog
} from 'naive-ui'
import { specAPI } from '@/api'

const message = useMessage()
const dialog = useDialog()

const loading = ref(false)
const specList = ref([])
const searchText = ref('')
const filterService = ref(null)

// 上传
const showUploadModal = ref(false)
const uploading = ref(false)
const uploadForm = ref({ serviceName: '', file: null })

// 详情
const showDetailModal = ref(false)
const detailLoading = ref(false)
const currentDetail = ref(null)

// 原文
const showContentModal = ref(false)
const contentLoading = ref(false)
const rawContent = ref('')

// 服务选项
const serviceOptions = computed(() => {
  const names = [...new Set(specList.value.map(s => s.service_name).filter(Boolean))]
  return names.map(n => ({ label: n, value: n }))
})

// 筛选
const filteredList = computed(() => {
  let list = specList.value
  if (filterService.value) {
    list = list.filter(s => s.service_name === filterService.value)
  }
  if (searchText.value) {
    const kw = searchText.value.toLowerCase()
    list = list.filter(s => s.original_filename.toLowerCase().includes(kw))
  }
  return list
})

// endpoint 表格列
const endpointColumns = [
  {
    title: 'Method', key: 'method', width: 90,
    render(row) {
      const colorMap = { GET: 'success', POST: 'warning', PUT: 'info', DELETE: 'error', PATCH: 'default' }
      return h(NTag, { type: colorMap[row.method] || 'default', size: 'small' }, { default: () => row.method })
    }
  },
  { title: 'Path', key: 'path', ellipsis: { tooltip: true } },
  { title: 'Summary', key: 'summary', ellipsis: { tooltip: true } }
]

const loadList = async () => {
  loading.value = true
  try {
    const res = await specAPI.getList({ limit: 200 })
    if (res.success) specList.value = res.data
  } catch (e) {
    message.error('加载失败')
  } finally {
    loading.value = false
  }
}

const handleFileChange = ({ fileList }) => {
  uploadForm.value.file = fileList.length > 0 ? fileList[0].file : null
}

const doUpload = async () => {
  if (!uploadForm.value.file) return
  uploading.value = true
  try {
    const res = await specAPI.importMd(uploadForm.value.file, uploadForm.value.serviceName || undefined)
    if (res.success) {
      message.success(`上传成功，解析出 ${res.data.endpoint_count} 个接口`)
      showUploadModal.value = false
      uploadForm.value = { serviceName: '', file: null }
      await loadList()
    } else {
      message.error(res.message || '上传失败')
    }
  } catch (e) {
    const msg = e.response?.data?.detail || e.message || '上传失败'
    message.error(msg)
  } finally {
    uploading.value = false
  }
}

const viewDetail = async (spec) => {
  showDetailModal.value = true
  detailLoading.value = true
  try {
    const res = await specAPI.getDetail(spec.id)
    if (res.success) currentDetail.value = res.data
  } catch (e) {
    message.error('获取详情失败')
  } finally {
    detailLoading.value = false
  }
}

const viewContent = async (spec) => {
  showContentModal.value = true
  contentLoading.value = true
  rawContent.value = ''
  try {
    const res = await specAPI.getContent(spec.id)
    if (res.success) rawContent.value = res.data.content
  } catch (e) {
    message.error('获取原文失败')
  } finally {
    contentLoading.value = false
  }
}

const confirmDelete = (spec) => {
  dialog.warning({
    title: '确认删除',
    content: `确定删除 "${spec.original_filename}" 吗？MinIO 中的文件也会被删除。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res = await specAPI.delete(spec.id)
        if (res.success) {
          message.success('删除成功')
          await loadList()
        }
      } catch (e) {
        message.error('删除失败')
      }
    }
  })
}

const formatSize = (bytes) => {
  if (!bytes) return '0B'
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB'
  return (bytes / 1024 / 1024).toFixed(1) + 'MB'
}

const formatTime = (iso) => {
  if (!iso) return '-'
  return new Date(iso).toLocaleString()
}

onMounted(loadList)
</script>

<style scoped>
.spec-manage-container {
  padding: 0;
}

.spec-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.spec-card {
  background: white;
  border: 1px solid rgba(0, 120, 87, 0.1);
  border-radius: 12px;
  overflow: hidden;
  transition: transform 0.2s, box-shadow 0.2s;
}

.spec-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
}

.spec-card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 16px 0;
}

.spec-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  background: linear-gradient(135deg, #007857, #00a67e);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}

.spec-meta {
  flex: 1;
  min-width: 0;
}

.spec-filename {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.spec-service {
  font-size: 12px;
  color: #94a3b8;
}

.spec-card-body {
  padding: 12px 16px;
}

.spec-stat-row {
  display: flex;
  gap: 24px;
  margin-bottom: 8px;
}

.spec-stat {
  display: flex;
  flex-direction: column;
}

.spec-stat-value {
  font-size: 18px;
  font-weight: 700;
  color: #007857;
}

.spec-stat-label {
  font-size: 11px;
  color: #94a3b8;
}

.spec-warning {
  font-size: 12px;
  color: #f0a020;
  margin-bottom: 4px;
}

.spec-warning i {
  margin-right: 4px;
}

.spec-time {
  font-size: 12px;
  color: #cbd5e1;
  margin: 0;
}

.spec-card-footer {
  display: flex;
  justify-content: space-around;
  border-top: 1px solid #f1f5f9;
  padding: 8px 0;
}

.markdown-raw {
  max-height: 500px;
  overflow: auto;
  background: #f8fafc;
  border-radius: 8px;
  padding: 16px;
}

.markdown-raw pre {
  margin: 0;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  color: #334155;
}
</style>
