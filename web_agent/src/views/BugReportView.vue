<template>
  <div class="bug-report-view">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <h3>错误集合</h3>
          <el-button size="small" @click="refreshData">刷新</el-button>
        </div>
      </template>
      
      <!-- 筛选条件 -->
      <div style="margin-bottom: 20px; display: flex; gap: 10px; flex-wrap: wrap">
        <el-select
          v-model="filterSeverity"
          placeholder="严重程度"
          clearable
          style="width: 150px"
          @change="handleFilterChange"
        >
          <el-option label="一级" value="一级" />
          <el-option label="二级" value="二级" />
          <el-option label="三级" value="三级" />
          <el-option label="四级" value="四级" />
        </el-select>
        
        <el-select
          v-model="filterStatus"
          placeholder="状态"
          clearable
          style="width: 150px"
          @change="handleFilterChange"
        >
          <el-option label="待处理" value="待处理" />
          <el-option label="已确认" value="已确认" />
          <el-option label="已修复" value="已修复" />
          <el-option label="已关闭" value="已关闭" />
        </el-select>
        
        <el-select
          v-model="filterErrorType"
          placeholder="错误类型"
          clearable
          style="width: 150px"
          @change="handleFilterChange"
        >
          <el-option label="功能错误" value="功能错误" />
          <el-option label="界面错误" value="界面错误" />
          <el-option label="性能问题" value="性能问题" />
          <el-option label="兼容性问题" value="兼容性问题" />
          <el-option label="其他" value="其他" />
        </el-select>
        
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          style="width: 280px"
          @change="handleFilterChange"
        />
        
        <el-button @click="resetFilters">重置筛选</el-button>
      </div>
      
      <el-table :data="bugs" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="bug_name" label="Bug名称" width="300" />
        <el-table-column label="严重程度" width="120">
          <template #default="{ row }">
            <el-tag :color="getSeverityColor(row.severity_level)" style="color: white">
              {{ row.severity_level }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="error_type" label="错误类型" width="120" />
        <el-table-column prop="location_url" label="定位地址" min-width="200">
          <template #default="{ row }">
            <a :href="row.location_url" target="_blank" class="url-link">
              {{ row.location_url }}
            </a>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="viewDetail(row)">
              查看详情
            </el-button>
            <el-dropdown @command="(status) => updateStatus(row.id, status)" style="margin-left: 5px">
              <el-button size="small">
                更新状态<el-icon class="el-icon--right"><arrow-down /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="待处理">待处理</el-dropdown-item>
                  <el-dropdown-item command="已确认">已确认</el-dropdown-item>
                  <el-dropdown-item command="已修复">已修复</el-dropdown-item>
                  <el-dropdown-item command="已关闭">已关闭</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
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

    <!-- Bug 详情对话框 -->
    <el-dialog v-model="dialogVisible" title="Bug 详情" width="900px">
      <div v-if="currentBug">
        <el-descriptions :column="2" border style="margin-bottom: 20px">
          <el-descriptions-item label="Bug ID">{{ currentBug.id }}</el-descriptions-item>
          <el-descriptions-item label="Bug名称">{{ currentBug.bug_name }}</el-descriptions-item>
          <el-descriptions-item label="严重程度">
            <el-tag :color="getSeverityColor(currentBug.severity_level)" style="color: white">
              {{ currentBug.severity_level }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="错误类型">{{ currentBug.error_type }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentBug.status)">
              {{ currentBug.status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(currentBug.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="定位地址" :span="2">
            <a :href="currentBug.location_url" target="_blank" class="url-link">
              {{ currentBug.location_url }}
            </a>
          </el-descriptions-item>
        </el-descriptions>

        <el-divider />

        <h4>复现步骤：</h4>
        <ol style="padding-left: 20px">
          <li v-for="(step, index) in currentBug.reproduce_steps" :key="index" style="margin: 8px 0">
            {{ step }}
          </li>
        </ol>

        <el-divider />

        <h4>预期结果：</h4>
        <p style="background: #f5f5f5; padding: 15px; border-radius: 4px">
          {{ currentBug.expected_result }}
        </p>

        <h4>实际结果：</h4>
        <p style="background: #fff3cd; padding: 15px; border-radius: 4px; border-left: 4px solid #ffc107">
          {{ currentBug.actual_result }}
        </p>

        <h4>结果反馈：</h4>
        <p style="background: #e3f2fd; padding: 15px; border-radius: 4px; border-left: 4px solid #2196f3">
          {{ currentBug.result_feedback }}
        </p>

        <div v-if="currentBug.screenshot_path">
          <h4>失败截图：</h4>
          <img :src="currentBug.screenshot_path" alt="失败截图" style="max-width: 100%; border-radius: 4px" />
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { bugReportAPI } from '@/api'

const bugs = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const currentBug = ref(null)

// 分页状态
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

// 筛选条件
const filterSeverity = ref('')
const filterStatus = ref('')
const filterErrorType = ref('')
const dateRange = ref(null)

// 所有数据缓存（用于前端筛选和分页）
const allBugs = ref([])

// 严重程度颜色映射
const severityColors = {
  '一级': '#f56c6c',
  '二级': '#e6a23c',
  '三级': '#fdf6ec',
  '四级': '#808080'
}

// 获取严重程度颜色
const getSeverityColor = (level) => {
  return severityColors[level] || '#909399'
}

// 获取状态类型
const getStatusType = (status) => {
  const typeMap = {
    '待处理': 'warning',
    '已确认': 'info',
    '已修复': 'success',
    '已关闭': 'info'
  }
  return typeMap[status] || 'info'
}

// 加载所有 Bug 数据
const loadAllBugs = async () => {
  try {
    // 获取大量数据以支持前端筛选
    const result = await bugReportAPI.getList({ limit: 1000, offset: 0 })
    if (result.success) {
      allBugs.value = result.data
    }
  } catch (error) {
    console.error('加载所有 Bug 失败:', error)
  }
}

// 加载 Bug 列表（应用筛选和分页）
const loadBugs = async () => {
  loading.value = true
  try {
    // 如果没有缓存数据，先加载
    if (allBugs.value.length === 0) {
      await loadAllBugs()
    }
    
    // 应用前端筛选
    let filteredData = allBugs.value
    
    // 严重程度筛选
    if (filterSeverity.value) {
      filteredData = filteredData.filter(bug => 
        bug.severity_level === filterSeverity.value
      )
    }
    
    // 状态筛选
    if (filterStatus.value) {
      filteredData = filteredData.filter(bug => 
        bug.status === filterStatus.value
      )
    }
    
    // 错误类型筛选
    if (filterErrorType.value) {
      filteredData = filteredData.filter(bug => 
        bug.error_type === filterErrorType.value
      )
    }
    
    // 日期范围筛选
    if (dateRange.value && dateRange.value.length === 2) {
      const [startDate, endDate] = dateRange.value
      filteredData = filteredData.filter(bug => {
        const bugDate = new Date(bug.created_at)
        return bugDate >= startDate && bugDate <= endDate
      })
    }
    
    // 更新总数
    total.value = filteredData.length
    
    // 前端分页
    const start = (currentPage.value - 1) * pageSize.value
    const end = start + pageSize.value
    bugs.value = filteredData.slice(start, end)
    
  } catch (error) {
    ElMessage.error('加载 Bug 列表失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// 处理筛选条件变化
const handleFilterChange = () => {
  currentPage.value = 1  // 重置到第一页
  loadBugs()
}

// 重置筛选条件
const resetFilters = () => {
  filterSeverity.value = ''
  filterStatus.value = ''
  filterErrorType.value = ''
  dateRange.value = null
  currentPage.value = 1
  loadBugs()
}

// 处理每页条数变化
const handleSizeChange = (newSize) => {
  pageSize.value = newSize
  currentPage.value = 1
  loadBugs()
}

// 处理当前页变化
const handleCurrentChange = (newPage) => {
  currentPage.value = newPage
  loadBugs()
}

// 刷新数据（重新加载所有数据）
const refreshData = async () => {
  allBugs.value = []  // 清空缓存
  await loadBugs()
}

// 查看详情
const viewDetail = async (row) => {
  try {
    const result = await bugReportAPI.getById(row.id)
    if (result.success) {
      currentBug.value = result.data
      dialogVisible.value = true
    } else {
      ElMessage.error('加载 Bug 详情失败')
    }
  } catch (error) {
    ElMessage.error('加载 Bug 详情失败')
    console.error(error)
  }
}

// 更新状态
const updateStatus = async (bugId, status) => {
  try {
    const result = await bugReportAPI.updateStatus(bugId, status)
    if (result.success) {
      ElMessage.success(`状态已更新为: ${status}`)
      // 更新缓存中的数据
      const bug = allBugs.value.find(b => b.id === bugId)
      if (bug) {
        bug.status = status
      }
      loadBugs()
    } else {
      ElMessage.error('更新状态失败')
    }
  } catch (error) {
    ElMessage.error('更新状态失败')
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
  loadBugs()
})
</script>

<style scoped>
.bug-report-view {
  padding: 20px;
}

.url-link {
  color: #409eff;
  text-decoration: none;
  word-break: break-all;
}

.url-link:hover {
  text-decoration: underline;
}

h4 {
  margin-top: 20px;
  margin-bottom: 10px;
  color: #303133;
}

p {
  margin: 10px 0;
  line-height: 1.6;
}

ol {
  line-height: 1.8;
}
</style>
