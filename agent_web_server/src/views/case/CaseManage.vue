<template>
  <div class="case-manage-view">
    <!-- 页面说明 -->
    <n-card>
      <template #header>
        <div class="flex items-center gap-2">
          <i class="fas fa-list-check text-xl text-primary"></i>
          <span class="text-lg font-bold">用例管理</span>
        </div>
      </template>
      <p class="text-gray-500">
        管理所有测试用例，支持增删改查操作
      </p>
    </n-card>

    <!-- 操作栏 -->
    <n-card style="margin-top: 20px">
      <n-form inline :model="filters" label-placement="left">
        <n-form-item label="模块">
          <n-input 
            v-model:value="filters.module" 
            placeholder="筛选模块"
            clearable
            style="width: 150px"
          />
        </n-form-item>
        <n-form-item label="关键词">
          <n-input 
            v-model:value="filters.search" 
            placeholder="搜索用例名称"
            clearable
            style="width: 200px"
          />
        </n-form-item>
        <n-form-item label="优先级">
          <n-select 
            v-model:value="filters.priority" 
            :options="priorityOptions"
            clearable
            placeholder="全部"
            style="width: 100px"
          />
        </n-form-item>
      </n-form>
    </n-card>

    <!-- 用例列表 -->
    <n-card style="margin-top: 20px">
      <template #header>
        <span class="font-bold">测试用例列表</span>
      </template>
      <template #header-extra>
        <n-space>
          <n-button type="primary" @click="openCreateDialog">
            <template #icon>
              <i class="fas fa-plus"></i>
            </template>
            新建用例
          </n-button>
        </n-space>
      </template>

      <n-data-table
        :columns="columns"
        :data="testCases"
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
          @update:page="loadTestCases"
          @update:page-size="handlePageSizeChange"
        />
      </div>
    </n-card>

    <!-- 详情对话框 -->
    <n-modal v-model:show="detailDialogVisible" preset="card" title="测试用例详情" style="width: 800px">
      <n-descriptions v-if="currentCase" :column="1" label-placement="left" bordered>
        <n-descriptions-item label="ID">{{ currentCase.id }}</n-descriptions-item>
        <n-descriptions-item label="模块">{{ currentCase.module }}</n-descriptions-item>
        <n-descriptions-item label="用例名称">{{ currentCase.title }}</n-descriptions-item>
        <n-descriptions-item label="前置条件">{{ currentCase.precondition || '无' }}</n-descriptions-item>
        <n-descriptions-item label="测试步骤">
          <div v-for="(step, index) in currentCase.steps" :key="index">
            {{ index + 1 }}. {{ step }}
          </div>
        </n-descriptions-item>
        <n-descriptions-item label="预期结果">{{ currentCase.expected }}</n-descriptions-item>
        <n-descriptions-item label="关键词">{{ currentCase.keywords }}</n-descriptions-item>
        <n-descriptions-item label="优先级">{{ formatPriority(currentCase.priority) }}</n-descriptions-item>
        <n-descriptions-item label="用例类型">{{ currentCase.case_type }}</n-descriptions-item>
        <n-descriptions-item label="适用阶段">{{ currentCase.stage }}</n-descriptions-item>
      </n-descriptions>
    </n-modal>

    <!-- 新建/编辑对话框 -->
    <n-modal 
      v-model:show="editDialogVisible" 
      preset="card" 
      :title="isEditing ? '编辑用例' : '新建用例'" 
      style="width: 800px"
    >
      <n-form 
        ref="formRef"
        :model="formData" 
        :rules="formRules"
        label-placement="left" 
        label-width="100"
      >
        <n-form-item label="模块" path="module">
          <n-input v-model:value="formData.module" placeholder="请输入模块名称" />
        </n-form-item>
        
        <n-form-item label="用例名称" path="title">
          <n-input v-model:value="formData.title" placeholder="请输入用例名称" />
        </n-form-item>
        
        <n-form-item label="前置条件" path="precondition">
          <n-input 
            v-model:value="formData.precondition" 
            type="textarea" 
            placeholder="请输入前置条件（可选）"
            :rows="2"
          />
        </n-form-item>
        
        <n-form-item label="测试步骤" path="steps">
          <div style="width: 100%">
            <div v-for="(step, index) in formData.steps" :key="index" class="step-item">
              <n-input 
                v-model:value="formData.steps[index]" 
                :placeholder="`步骤 ${index + 1}`"
              />
              <n-button 
                v-if="formData.steps.length > 1"
                type="error" 
                text 
                @click="removeStep(index)"
              >
                <i class="fas fa-times"></i>
              </n-button>
            </div>
            <n-button dashed block @click="addStep" style="margin-top: 8px">
              <template #icon>
                <i class="fas fa-plus"></i>
              </template>
              添加步骤
            </n-button>
          </div>
        </n-form-item>
        
        <n-form-item label="预期结果" path="expected">
          <n-input 
            v-model:value="formData.expected" 
            type="textarea" 
            placeholder="请输入预期结果"
            :rows="2"
          />
        </n-form-item>
        
        <n-form-item label="关键词" path="keywords">
          <n-input v-model:value="formData.keywords" placeholder="请输入关键词，用逗号分隔" />
        </n-form-item>
        
        <n-form-item label="优先级" path="priority">
          <n-select 
            v-model:value="formData.priority" 
            :options="prioritySelectOptions"
            placeholder="请选择优先级"
          />
        </n-form-item>
        
        <n-form-item label="用例类型" path="case_type">
          <n-select 
            v-model:value="formData.case_type" 
            :options="caseTypeOptions"
            placeholder="请选择用例类型"
          />
        </n-form-item>
        
        <n-form-item label="适用阶段" path="stage">
          <n-select 
            v-model:value="formData.stage" 
            :options="stageOptions"
            placeholder="请选择适用阶段"
          />
        </n-form-item>
      </n-form>

      <template #footer>
        <n-space justify="end">
          <n-button @click="editDialogVisible = false">取消</n-button>
          <n-button type="primary" @click="submitForm" :loading="submitting">
            {{ isEditing ? '保存' : '创建' }}
          </n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, h, reactive, onMounted, watch } from 'vue'
import { 
  NCard, NButton, NDataTable, NModal, NDescriptions, NDescriptionsItem, 
  NTag, NForm, NFormItem, NInput, NSelect, NSpace, NPagination,
  useMessage, useDialog
} from 'naive-ui'
import { testCaseAPI } from '@/api'

const message = useMessage()
const dialog = useDialog()

// 列表数据
const testCases = ref([])
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

// 筛选条件
const filters = reactive({
  module: '',
  search: '',
  priority: null
})

// 优先级选项
const priorityOptions = [
  { label: '全部', value: null },
  { label: '1级', value: '1' },
  { label: '2级', value: '2' },
  { label: '3级', value: '3' },
  { label: '4级', value: '4' }
]

const prioritySelectOptions = [
  { label: '1级 - 最高', value: '1' },
  { label: '2级 - 高', value: '2' },
  { label: '3级 - 中', value: '3' },
  { label: '4级 - 低', value: '4' }
]

const caseTypeOptions = [
  { label: '功能测试', value: '功能测试' },
  { label: '冒烟测试', value: '冒烟测试' },
  { label: '回归测试', value: '回归测试' },
  { label: '边界测试', value: '边界测试' },
  { label: '异常测试', value: '异常测试' }
]

const stageOptions = [
  { label: '开发阶段', value: '开发阶段' },
  { label: '测试阶段', value: '测试阶段' },
  { label: '验收阶段', value: '验收阶段' },
  { label: '上线阶段', value: '上线阶段' }
]

// 详情对话框
const detailDialogVisible = ref(false)
const currentCase = ref(null)

// 编辑对话框
const editDialogVisible = ref(false)
const isEditing = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const formData = reactive({
  id: null,
  module: '',
  title: '',
  precondition: '',
  steps: [''],
  expected: '',
  keywords: '',
  priority: '2',
  case_type: '功能测试',
  stage: '测试阶段'
})

// 表单验证规则
const formRules = {
  module: { required: true, message: '请输入模块名称', trigger: 'blur' },
  title: { required: true, message: '请输入用例名称', trigger: 'blur' },
  steps: { 
    required: true, 
    validator: (rule, value) => {
      if (!value || value.length === 0 || value.every(s => !s.trim())) {
        return new Error('请至少输入一个测试步骤')
      }
      return true
    },
    trigger: 'blur' 
  },
  expected: { required: true, message: '请输入预期结果', trigger: 'blur' },
  priority: { required: true, message: '请选择优先级', trigger: 'change' }
}

// 优先级类型映射
const getPriorityType = (priority) => {
  const typeMap = { '1': 'error', '2': 'warning', '3': 'info', '4': 'default' }
  return typeMap[String(priority)] || 'default'
}

// 格式化优先级
const formatPriority = (priority) => {
  if (/^[1-4]$/.test(String(priority))) {
    return `${priority}级`
  }
  return priority
}

// 表格列定义
const columns = [
  { title: 'ID', key: 'id', width: 80 },
  { title: '模块', key: 'module', width: 120 },
  { title: '用例名称', key: 'title', width: 200, ellipsis: { tooltip: true } },
  { 
    title: '步骤', 
    key: 'steps',
    render(row) {
      const steps = row.steps || []
      if (steps.length === 0) return '-'
      return h('div', {}, steps.slice(0, 3).map((step, index) => 
        h('div', { style: 'margin: 2px 0; font-size: 12px;' }, `${index + 1}. ${step}`)
      ).concat(steps.length > 3 ? [h('div', { style: 'font-size: 12px; color: #999;' }, `...共${steps.length}步`)] : []))
    }
  },
  { 
    title: '优先级', 
    key: 'priority', 
    width: 80,
    render(row) {
      return h(NTag, { type: getPriorityType(row.priority), size: 'small' }, 
        { default: () => formatPriority(row.priority) }
      )
    }
  },
  { title: '用例类型', key: 'case_type', width: 100 },
  {
    title: '操作',
    key: 'actions',
    width: 220,
    fixed: 'right',
    render(row) {
      return h(NSpace, {}, {
        default: () => [
          h(NButton, { size: 'small', type: 'info', onClick: () => viewDetail(row) }, 
            { default: () => '详情' }
          ),
          h(NButton, { size: 'small', type: 'primary', onClick: () => editCase(row) }, 
            { default: () => '编辑' }
          ),
          h(NButton, { size: 'small', type: 'error', onClick: () => deleteCase(row) }, 
            { default: () => '删除' }
          )
        ]
      })
    }
  }
]

// 加载测试用例列表
const loadTestCases = async () => {
  loading.value = true
  try {
    const params = {
      limit: pageSize.value,
      offset: (currentPage.value - 1) * pageSize.value
    }
    
    if (filters.module) {
      params.module = filters.module
    }
    if (filters.search) {
      params.search = filters.search
    }
    if (filters.priority) {
      params.priority = filters.priority
    }
    
    const result = await testCaseAPI.getList(params)
    if (result.success) {
      testCases.value = result.data || []
      total.value = result.total || result.data?.length || 0
    }
  } catch (error) {
    message.error('加载测试用例失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// 监听筛选条件变化，自动查询
watch(filters, () => {
  currentPage.value = 1
  loadTestCases()
})

// 处理分页大小改变
const handlePageSizeChange = (size) => {
  pageSize.value = size
  currentPage.value = 1
  loadTestCases()
}

// 查看详情
const viewDetail = (row) => {
  currentCase.value = row
  detailDialogVisible.value = true
}

// 打开新建对话框
const openCreateDialog = () => {
  isEditing.value = false
  resetFormData()
  editDialogVisible.value = true
}

// 编辑用例
const editCase = (row) => {
  isEditing.value = true
  formData.id = row.id
  formData.module = row.module || ''
  formData.title = row.title || ''
  formData.precondition = row.precondition || ''
  formData.steps = row.steps && row.steps.length > 0 ? [...row.steps] : ['']
  formData.expected = row.expected || ''
  formData.keywords = row.keywords || ''
  formData.priority = String(row.priority || '2')
  formData.case_type = row.case_type || '功能测试'
  formData.stage = row.stage || '测试阶段'
  editDialogVisible.value = true
}

// 重置表单数据
const resetFormData = () => {
  formData.id = null
  formData.module = ''
  formData.title = ''
  formData.precondition = ''
  formData.steps = ['']
  formData.expected = ''
  formData.keywords = ''
  formData.priority = '2'
  formData.case_type = '功能测试'
  formData.stage = '测试阶段'
}

// 添加步骤
const addStep = () => {
  formData.steps.push('')
}

// 移除步骤
const removeStep = (index) => {
  formData.steps.splice(index, 1)
}

// 提交表单
const submitForm = async () => {
  try {
    await formRef.value?.validate()
  } catch (error) {
    return
  }

  submitting.value = true
  try {
    // 过滤空步骤
    const data = {
      ...formData,
      steps: formData.steps.filter(s => s.trim())
    }

    let result
    if (isEditing.value) {
      result = await testCaseAPI.update(formData.id, data)
    } else {
      result = await testCaseAPI.create(data)
    }

    if (result.success) {
      message.success(isEditing.value ? '更新成功' : '创建成功')
      editDialogVisible.value = false
      loadTestCases()
    } else {
      message.error(result.message || '操作失败')
    }
  } catch (error) {
    message.error('操作失败: ' + (error.message || '未知错误'))
    console.error(error)
  } finally {
    submitting.value = false
  }
}

// 删除用例
const deleteCase = (row) => {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除用例 "${row.title}" 吗？`,
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const result = await testCaseAPI.delete(row.id)
        if (result.success) {
          message.success('删除成功')
          loadTestCases()
        } else {
          message.error(result.message || '删除失败')
        }
      } catch (error) {
        message.error('删除失败: ' + (error.message || '未知错误'))
        console.error(error)
      }
    }
  })
}

onMounted(() => {
  loadTestCases()
})
</script>

<style scoped>
.case-manage-view {
  padding: 0;
}

.text-primary {
  color: #007857;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.step-item .n-input {
  flex: 1;
}
</style>
