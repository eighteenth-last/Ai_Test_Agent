<template>
  <div class="test-report-view">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <h3>测试报告列表</h3>
          <!-- 筛选条件和刷新按钮在同一行 -->
          <div style="display: flex; gap: 10px; align-items: center">
            <el-select
              v-model="filterStatus"
              placeholder="测试状态"
              clearable
              size="small"
              style="width: 120px"
              @change="handleFilterChange"
            >
              <el-option label="通过" value="通过" />
              <el-option label="失败" value="失败" />
            </el-select>
            
            <el-select
              v-model="filterFormat"
              placeholder="格式类型"
              clearable
              size="small"
              style="width: 120px"
              @change="handleFilterChange"
            >
              <el-option label="HTML" value="html" />
              <el-option label="Markdown" value="markdown" />
              <el-option label="TXT" value="txt" />
            </el-select>
            
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              size="small"
              style="width: 240px"
              @change="handleFilterChange"
            />
            
            <el-button size="small" @click="resetFilters">重置筛选</el-button>
            <el-button size="small" @click="refreshData">刷新</el-button>
          </div>
        </div>
      </template>
      
      <el-table :data="reports" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="报告标题" width="300" />
        <el-table-column label="测试汇总" width="300">
          <template #default="{ row }">
            <div v-if="row.summary">
              <!-- 新格式：直接有 status 字段 -->
              <template v-if="row.summary.status">
                <el-tag :type="row.summary.status === '通过' ? 'success' : 'danger'">
                  {{ row.summary.status }}
                </el-tag>
              </template>
              <!-- 旧格式：有 pass 和 fail 字段，需要计算 -->
              <template v-else-if="row.summary.pass !== undefined">
                <el-tag :type="row.summary.fail === 0 ? 'success' : 'danger'">
                  {{ row.summary.fail === 0 ? '通过' : '失败' }}
                </el-tag>
              </template>
              <el-tag type="warning" style="margin-left: 10px">耗时: {{ row.summary.duration }}s</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="format_type" label="格式" width="100" />
        <el-table-column prop="created_at" label="生成时间" width="200">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="viewReport(row)">
              查看报告
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 分页组件 -->
      <div style="margin-top: 20px; display: flex; justify-content: center">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- 报告详情对话框 -->
    <el-dialog v-model="dialogVisible" title="测试报告详情" width="900px" :fullscreen="fullscreen">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>测试报告详情</span>
          <div>
            <el-button type="primary" size="small" @click="downloadReport" style="margin-right: 10px">
              <el-icon style="margin-right: 5px"><Download /></el-icon>
              下载报告
            </el-button>
            <el-button @click="fullscreen = !fullscreen" link>
              {{ fullscreen ? '退出全屏' : '全屏显示' }}
            </el-button>
          </div>
        </div>
      </template>
      
      <div v-if="currentReport">
        <el-descriptions :column="2" border style="margin-bottom: 20px">
          <el-descriptions-item label="报告ID">{{ currentReport.id }}</el-descriptions-item>
          <el-descriptions-item label="报告标题">{{ currentReport.title }}</el-descriptions-item>
          <el-descriptions-item label="格式类型">{{ currentReport.format_type }}</el-descriptions-item>
          <el-descriptions-item label="生成时间">{{ formatDate(currentReport.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="测试结果" span="1">
            <!-- 新格式：直接有 status 字段 -->
            <el-tag v-if="currentReport.summary?.status" 
                    :type="currentReport.summary.status === '通过' ? 'success' : 'danger'">
              {{ currentReport.summary.status }}
            </el-tag>
            <!-- 旧格式：有 pass 和 fail 字段 -->
            <el-tag v-else-if="currentReport.summary?.pass !== undefined"
                    :type="currentReport.summary.fail === 0 ? 'success' : 'danger'">
              {{ currentReport.summary.fail === 0 ? '通过' : '失败' }}
            </el-tag>
            <el-tag v-else type="info">未知</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="执行耗时" span="1">
            <el-tag type="warning">{{ currentReport.summary?.duration || 0 }}s</el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <el-divider />

        <h4>报告内容：</h4>
        <div v-if="currentReport.format_type === 'html'" v-html="currentReport.details" class="report-content"></div>
        <div v-else-if="currentReport.format_type === 'markdown'" v-html="renderedMarkdown" class="report-content markdown-body"></div>
        <pre v-else style="white-space: pre-wrap; background: #f5f5f5; padding: 15px; border-radius: 4px">{{ currentReport.details }}</pre>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import { testReportAPI } from '@/api'
import { marked } from 'marked'

// 配置 marked
marked.setOptions({
  breaks: true,
  gfm: true,
})

const reports = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const fullscreen = ref(false)
const currentReport = ref(null)

// 分页状态
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

// 筛选条件
const filterStatus = ref('')
const filterFormat = ref('')
const dateRange = ref(null)

// 所有数据缓存（用于前端筛选和分页）
const allReports = ref([])

// 加载所有报告数据
const loadAllReports = async () => {
  try {
    // 获取大量数据以支持前端筛选
    const result = await testReportAPI.getList({ limit: 1000, offset: 0 })
    if (result.success) {
      allReports.value = result.data
    }
  } catch (error) {
    console.error('加载所有报告失败:', error)
  }
}

// 加载报告列表（应用筛选和分页）
const loadReports = async () => {
  loading.value = true
  try {
    // 如果没有缓存数据，先加载
    if (allReports.value.length === 0) {
      await loadAllReports()
    }
    
    // 应用前端筛选
    let filteredData = allReports.value
    
    // 状态筛选
    if (filterStatus.value) {
      filteredData = filteredData.filter(report => {
        if (report.summary?.status) {
          return report.summary.status === filterStatus.value
        } else if (report.summary?.pass !== undefined) {
          const status = report.summary.fail === 0 ? '通过' : '失败'
          return status === filterStatus.value
        }
        return false
      })
    }
    
    // 格式筛选
    if (filterFormat.value) {
      filteredData = filteredData.filter(report => 
        report.format_type === filterFormat.value
      )
    }
    
    // 日期范围筛选
    if (dateRange.value && dateRange.value.length === 2) {
      const [startDate, endDate] = dateRange.value
      filteredData = filteredData.filter(report => {
        const reportDate = new Date(report.created_at)
        return reportDate >= startDate && reportDate <= endDate
      })
    }
    
    // 更新总数
    total.value = filteredData.length
    
    // 前端分页
    const start = (currentPage.value - 1) * pageSize.value
    const end = start + pageSize.value
    reports.value = filteredData.slice(start, end)
    
  } catch (error) {
    ElMessage.error('加载报告列表失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// 处理筛选条件变化
const handleFilterChange = () => {
  currentPage.value = 1  // 重置到第一页
  loadReports()
}

// 重置筛选条件
const resetFilters = () => {
  filterStatus.value = ''
  filterFormat.value = ''
  dateRange.value = null
  currentPage.value = 1
  loadReports()
}

// 处理每页条数变化
const handleSizeChange = (newSize) => {
  pageSize.value = newSize
  currentPage.value = 1
  loadReports()
}

// 处理当前页变化
const handleCurrentChange = (newPage) => {
  currentPage.value = newPage
  loadReports()
}

// 刷新数据（重新加载所有数据）
const refreshData = async () => {
  allReports.value = []  // 清空缓存
  await loadReports()
}

// 查看报告
const viewReport = async (row) => {
  try {
    // Fetch full report details including content
    const result = await testReportAPI.getById(row.id)
    if (result.success) {
      currentReport.value = result.data
      dialogVisible.value = true
    } else {
      ElMessage.error('加载报告详情失败')
    }
  } catch (error) {
    ElMessage.error('加载报告详情失败')
    console.error(error)
  }
}

// 下载报告
const downloadReport = () => {
  if (!currentReport.value) {
    ElMessage.warning('没有可下载的报告')
    return
  }
  
  try {
    testReportAPI.download(currentReport.value.id)
    ElMessage.success('报告下载已开始')
  } catch (error) {
    ElMessage.error('下载报告失败')
    console.error(error)
  }
}

// 格式化日期
const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

// 渲染 Markdown 为 HTML
const renderedMarkdown = computed(() => {
  if (!currentReport.value || currentReport.value.format_type !== 'markdown') {
    return ''
  }
  try {
    return marked.parse(currentReport.value.details || '')
  } catch (error) {
    console.error('Markdown 解析失败:', error)
    return '<p>Markdown 解析失败</p>'
  }
})

onMounted(() => {
  loadReports()
})
</script>

<style scoped>
.test-report-view {
  padding: 20px;
}

.report-content {
  background: #f5f5f5;
  padding: 20px;
  border-radius: 4px;
  max-height: 600px;
  overflow-y: auto;
}

/* Markdown 样式 */
.markdown-body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  font-size: 14px;
  line-height: 1.6;
  color: #333;
  background: #fff;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  margin-top: 24px;
  margin-bottom: 16px;
  font-weight: 600;
  line-height: 1.25;
  color: #24292e;
}

.markdown-body :deep(h1) {
  font-size: 2em;
  border-bottom: 1px solid #eaecef;
  padding-bottom: 0.3em;
}

.markdown-body :deep(h2) {
  font-size: 1.5em;
  border-bottom: 1px solid #eaecef;
  padding-bottom: 0.3em;
}

.markdown-body :deep(h3) {
  font-size: 1.25em;
}

.markdown-body :deep(h4) {
  font-size: 1em;
}

.markdown-body :deep(p) {
  margin-top: 0;
  margin-bottom: 16px;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 2em;
  margin-top: 0;
  margin-bottom: 16px;
}

.markdown-body :deep(li) {
  margin-bottom: 4px;
}

.markdown-body :deep(code) {
  padding: 0.2em 0.4em;
  margin: 0;
  font-size: 85%;
  background-color: rgba(27, 31, 35, 0.05);
  border-radius: 3px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
}

.markdown-body :deep(pre) {
  padding: 16px;
  overflow: auto;
  font-size: 85%;
  line-height: 1.45;
  background-color: #f6f8fa;
  border-radius: 6px;
  margin-bottom: 16px;
}

.markdown-body :deep(pre code) {
  display: inline;
  padding: 0;
  margin: 0;
  overflow: visible;
  line-height: inherit;
  background-color: transparent;
  border: 0;
}

.markdown-body :deep(table) {
  border-spacing: 0;
  border-collapse: collapse;
  margin-bottom: 16px;
  width: 100%;
}

.markdown-body :deep(table th),
.markdown-body :deep(table td) {
  padding: 6px 13px;
  border: 1px solid #dfe2e5;
}

.markdown-body :deep(table th) {
  font-weight: 600;
  background-color: #f6f8fa;
}

.markdown-body :deep(table tr) {
  background-color: #fff;
  border-top: 1px solid #c6cbd1;
}

.markdown-body :deep(table tr:nth-child(2n)) {
  background-color: #f6f8fa;
}

.markdown-body :deep(blockquote) {
  padding: 0 1em;
  color: #6a737d;
  border-left: 0.25em solid #dfe2e5;
  margin-bottom: 16px;
}

.markdown-body :deep(hr) {
  height: 0.25em;
  padding: 0;
  margin: 24px 0;
  background-color: #e1e4e8;
  border: 0;
}

.markdown-body :deep(a) {
  color: #0366d6;
  text-decoration: none;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

.markdown-body :deep(strong) {
  font-weight: 600;
}

.markdown-body :deep(em) {
  font-style: italic;
}
</style>
