<template>
  <div class="test-case-view">
    <el-card>
      <template #header>
        <h3>测试用例生成</h3>
      </template>
      
      <!-- 生成测试用例 -->
      <el-form :model="form" label-width="100px">
        <el-form-item label="测试需求">
          <el-input
            v-model="form.requirement"
            type="textarea"
            :rows="6"
            placeholder="请输入测试需求，例如：用户可以登录学生端，查看课程，打开实验项目，上传并提交文件"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="generateTestCases" :loading="generating">
            生成测试用例
          </el-button>
        </el-form-item>
      </el-form>
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
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="viewDetail(row)">
              查看详情
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
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { testCaseAPI } from '@/api'

const form = ref({ requirement: '' })
const testCases = ref([])
const loading = ref(false)
const generating = ref(false)
const dialogVisible = ref(false)
const currentCase = ref(null)

// 生成测试用例
const generateTestCases = async () => {
  if (!form.value.requirement.trim()) {
    ElMessage.warning('请输入测试需求')
    return
  }
  
  generating.value = true
  try {
    const result = await testCaseAPI.generate(form.value.requirement)
    if (result.success) {
      ElMessage.success(result.message)
      form.value.requirement = ''
      loadTestCases()
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    ElMessage.error('生成测试用例失败')
    console.error(error)
  } finally {
    generating.value = false
  }
}

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

onMounted(() => {
  loadTestCases()
})
</script>

<style scoped>
.test-case-view {
  padding: 20px;
}
</style>
