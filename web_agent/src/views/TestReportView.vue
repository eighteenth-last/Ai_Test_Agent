<template>
  <div class="test-report-view">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <h3>测试报告列表</h3>
          <el-button size="small" @click="loadReports">刷新</el-button>
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
        <div v-if="currentReport.format_type === 'html'" v-html="currentReport.details"></div>
        <pre v-else style="white-space: pre-wrap; background: #f5f5f5; padding: 15px; border-radius: 4px">{{ currentReport.details }}</pre>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import { testReportAPI } from '@/api'

const reports = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const fullscreen = ref(false)
const currentReport = ref(null)

// 加载报告列表
const loadReports = async () => {
  loading.value = true
  try {
    const result = await testReportAPI.getList({ limit: 20, offset: 0 })
    if (result.success) {
      reports.value = result.data
    }
  } catch (error) {
    ElMessage.error('加载报告列表失败')
    console.error(error)
  } finally {
    loading.value = false
  }
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

onMounted(() => {
  loadReports()
})
</script>

<style scoped>
.test-report-view {
  padding: 20px;
}
</style>
