<template>
  <div class="test-case-view">
    <!-- 生成测试用例卡片 -->
    <n-card title="测试用例生成">
      <n-grid :cols="2" :x-gap="24">
        <!-- 左侧：输入需求 -->
        <n-gi>
          <n-form-item label="测试需求">
            <n-input
              v-model:value="form.requirement"
              type="textarea"
              :rows="10"
              placeholder="请输入测试需求，例如：用户可以登录学生端，查看课程，打开实验项目，上传并提交文件"
              style="height: 184px;"
              :input-props="{ style: 'height: 184px; resize: none;' }"
            />
          </n-form-item>
          <n-button type="primary" @click="generateTestCases" :loading="generating">
            <template #icon>
              <i class="fas fa-magic"></i>
            </template>
            生成测试用例
          </n-button>
        </n-gi>

        <!-- 右侧：上传文件 -->
        <n-gi>
          <n-form-item label="或上传文件">
            <n-upload
              ref="uploadRef"
              :default-upload="false"
              @change="handleFileChange"
              :max="1"
              accept=".md,.txt,.pdf,.doc,.docx"
              directory-dnd
            >
              <n-upload-dragger>
                <div class="upload-content">
                  <i class="fas fa-cloud-upload-alt text-4xl text-gray-400 mb-2"></i>
                  <p class="text-gray-600">拖拽文件到此处或 <em class="text-primary">点击上传</em></p>
                  <p class="text-xs text-gray-400 mt-2">支持 .md / .txt / .pdf / .doc / .docx 格式，文件大小不超过 10MB</p>
                </div>
              </n-upload-dragger>
            </n-upload>
          </n-form-item>
          <n-button 
            type="success" 
            @click="uploadFileAndGenerate" 
            :loading="uploading"
            :disabled="!selectedFile"
          >
            <template #icon>
              <i class="fas fa-file-upload"></i>
            </template>
            上传文件并生成
          </n-button>
        </n-gi>
      </n-grid>
    </n-card>

    <!-- 测试用例列表 -->
    <n-card title="测试用例列表" style="margin-top: 20px">

      <n-data-table
        :columns="columns"
        :data="testCases"
        :loading="loading"
        :pagination="pagination"
        :row-key="row => row.id"
        striped
      />
    </n-card>

    <!-- 详情/编辑对话框 -->
    <n-modal v-model:show="dialogVisible" preset="card" style="width: 800px" :title="editMode ? '编辑测试用例' : '测试用例详情'">
      <template #header-extra>
        <n-space>
          <n-button v-if="!editMode" type="primary" size="small" @click="enterEditMode">
            <template #icon>
              <i class="fas fa-edit"></i>
            </template>
            编辑
          </n-button>
          <template v-else>
            <n-button size="small" @click="cancelEdit">取消</n-button>
            <n-button type="primary" size="small" @click="saveEdit" :loading="saving">保存</n-button>
          </template>
        </n-space>
      </template>

      <n-descriptions v-if="currentCase" :column="1" label-placement="left" bordered>
        <n-descriptions-item label="ID">{{ currentCase.id }}</n-descriptions-item>
        
        <n-descriptions-item label="模块">
          <span v-if="!editMode">{{ currentCase.module }}</span>
          <n-input v-else v-model:value="editForm.module" size="small" />
        </n-descriptions-item>
        
        <n-descriptions-item label="用例名称">
          <span v-if="!editMode">{{ currentCase.title }}</span>
          <n-input v-else v-model:value="editForm.title" size="small" />
        </n-descriptions-item>
        
        <n-descriptions-item label="前置条件">
          <span v-if="!editMode">{{ currentCase.precondition || '无' }}</span>
          <n-input v-else v-model:value="editForm.precondition" type="textarea" :rows="2" size="small" />
        </n-descriptions-item>
        
        <n-descriptions-item label="测试步骤">
          <div v-if="!editMode">
            <div v-for="(step, index) in currentCase.steps" :key="index" class="step-item">
              {{ index + 1 }}. {{ step }}
            </div>
          </div>
          <div v-else>
            <div v-for="(step, index) in editForm.steps" :key="index" class="edit-step-row">
              <span class="step-num">{{ index + 1 }}.</span>
              <n-input v-model:value="editForm.steps[index]" size="small" style="flex: 1" />
              <n-button 
                type="error" 
                size="small" 
                @click="removeStep(index)"
                :disabled="editForm.steps.length === 1"
              >
                删除
              </n-button>
            </div>
            <n-button type="primary" size="small" @click="addStep" style="margin-top: 8px">
              添加步骤
            </n-button>
          </div>
        </n-descriptions-item>
        
        <n-descriptions-item label="预期结果">
          <span v-if="!editMode">{{ currentCase.expected }}</span>
          <n-input v-else v-model:value="editForm.expected" type="textarea" :rows="2" size="small" />
        </n-descriptions-item>
        
        <n-descriptions-item label="关键词">
          <span v-if="!editMode">{{ currentCase.keywords }}</span>
          <n-input v-else v-model:value="editForm.keywords" size="small" />
        </n-descriptions-item>
        
        <n-descriptions-item label="优先级">
          <n-tag v-if="!editMode" :type="getPriorityType(currentCase.priority)">
            {{ formatPriority(currentCase.priority) }}
          </n-tag>
          <n-select v-else v-model:value="editForm.priority" size="small" :options="priorityOptions" style="width: 150px" />
        </n-descriptions-item>
        
        <n-descriptions-item label="用例类型">
          <span v-if="!editMode">{{ currentCase.case_type }}</span>
          <n-select v-else v-model:value="editForm.case_type" size="small" :options="caseTypeOptions" style="width: 150px" />
        </n-descriptions-item>
        
        <n-descriptions-item label="适用阶段">
          <span v-if="!editMode">{{ currentCase.stage }}</span>
          <n-input v-else v-model:value="editForm.stage" size="small" />
        </n-descriptions-item>
      </n-descriptions>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, h, onMounted, reactive } from 'vue'
import { 
  NCard, NGrid, NGi, NFormItem, NInput, NButton, NUpload, NUploadDragger,
  NDataTable, NModal, NDescriptions, NDescriptionsItem, NTag, NSelect, NSpace,
  useMessage
} from 'naive-ui'
import { testCaseAPI } from '@/api'

const message = useMessage()

// 表单数据
const form = ref({ requirement: '' })
const testCases = ref([])
const loading = ref(false)
const generating = ref(false)
const uploading = ref(false)
const dialogVisible = ref(false)
const currentCase = ref(null)
const selectedFile = ref(null)
const uploadRef = ref(null)

// 编辑相关
const editMode = ref(false)
const editForm = ref(null)
const saving = ref(false)

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 10,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  onChange: (page) => {
    pagination.page = page
    loadTestCases()
  },
  onUpdatePageSize: (pageSize) => {
    pagination.pageSize = pageSize
    pagination.page = 1
    loadTestCases()
  }
})

// 所有数据缓存
const allTestCases = ref([])

// 优先级选项
const priorityOptions = [
  { label: '1级（冒烟）', value: '1' },
  { label: '2级（核心）', value: '2' },
  { label: '3级（一般）', value: '3' },
  { label: '4级（优化）', value: '4' }
]

// 用例类型选项
const caseTypeOptions = [
  { label: '功能测试', value: '功能测试' },
  { label: '单元测试', value: '单元测试' },
  { label: '接口测试', value: '接口测试' },
  { label: '安全测试', value: '安全测试' },
  { label: '性能测试', value: '性能测试' }
]

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
      return h('div', {}, row.steps?.map((step, index) => 
        h('div', { style: 'margin: 2px 0; font-size: 12px;' }, `${index + 1}. ${step}`)
      ))
    }
  },
  { 
    title: '优先级', 
    key: 'priority', 
    width: 100,
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
    width: 100,
    fixed: 'right',
    render(row) {
      return h(NButton, { size: 'small', type: 'primary', onClick: () => viewDetail(row) }, 
        { default: () => '查看详情' }
      )
    }
  }
]

// 文件选择处理
const handleFileChange = ({ file }) => {
  selectedFile.value = file.file
}

// 上传文件并生成
const uploadFileAndGenerate = async () => {
  if (!selectedFile.value) {
    message.warning('请先选择文件')
    return
  }
  
  uploading.value = true
  try {
    const result = await testCaseAPI.uploadFile(selectedFile.value)
    if (result.success) {
      message.success(result.message)
      selectedFile.value = null
      if (uploadRef.value) {
        uploadRef.value.clear()
      }
      refreshData()
    } else {
      message.error(result.message)
    }
  } catch (error) {
    message.error('上传文件失败')
    console.error(error)
  } finally {
    uploading.value = false
  }
}

// 生成测试用例
const generateTestCases = async () => {
  if (!form.value.requirement.trim()) {
    message.warning('请输入测试需求')
    return
  }
  
  generating.value = true
  try {
    const result = await testCaseAPI.generate(form.value.requirement)
    if (result.success) {
      message.success(result.message)
      form.value.requirement = ''
      refreshData()
    } else {
      message.error(result.message)
    }
  } catch (error) {
    message.error('生成测试用例失败')
    console.error(error)
  } finally {
    generating.value = false
  }
}

// 加载所有测试用例
const loadAllTestCases = async () => {
  try {
    const result = await testCaseAPI.getList({ limit: 1000, offset: 0 })
    if (result.success) {
      allTestCases.value = result.data
    }
  } catch (error) {
    console.error('加载所有测试用例失败:', error)
  }
}

// 加载测试用例列表
const loadTestCases = async () => {
  loading.value = true
  try {
    if (allTestCases.value.length === 0) {
      await loadAllTestCases()
    }
    
    pagination.itemCount = allTestCases.value.length
    
    const start = (pagination.page - 1) * pagination.pageSize
    const end = start + pagination.pageSize
    testCases.value = allTestCases.value.slice(start, end)
  } catch (error) {
    message.error('加载测试用例失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// 刷新数据
const refreshData = async () => {
  allTestCases.value = []
  pagination.page = 1
  await loadTestCases()
}

// 查看详情
const viewDetail = (row) => {
  currentCase.value = row
  editMode.value = false
  dialogVisible.value = true
}

// 进入编辑模式
const enterEditMode = () => {
  if (!currentCase.value) return
  
  editForm.value = {
    id: currentCase.value.id,
    module: currentCase.value.module,
    title: currentCase.value.title,
    precondition: currentCase.value.precondition || '',
    steps: [...currentCase.value.steps],
    expected: currentCase.value.expected,
    keywords: currentCase.value.keywords || '',
    priority: String(currentCase.value.priority),
    case_type: currentCase.value.case_type || '',
    stage: currentCase.value.stage || '',
  }
  editMode.value = true
}

// 添加步骤
const addStep = () => {
  if (editForm.value) {
    editForm.value.steps.push('')
  }
}

// 删除步骤
const removeStep = (index) => {
  if (editForm.value && editForm.value.steps.length > 1) {
    editForm.value.steps.splice(index, 1)
  }
}

// 取消编辑
const cancelEdit = () => {
  editMode.value = false
  editForm.value = null
}

// 保存编辑
const saveEdit = async () => {
  if (!editForm.value) return
  
  if (!editForm.value.module || !editForm.value.title || !editForm.value.expected) {
    message.warning('请填写必填字段')
    return
  }
  
  if (editForm.value.steps.length === 0 || editForm.value.steps.some(s => !s.trim())) {
    message.warning('请填写所有测试步骤')
    return
  }
  
  saving.value = true
  try {
    const result = await testCaseAPI.update(editForm.value.id, {
      module: editForm.value.module,
      title: editForm.value.title,
      precondition: editForm.value.precondition,
      steps: editForm.value.steps,
      expected: editForm.value.expected,
      keywords: editForm.value.keywords,
      priority: editForm.value.priority,
      case_type: editForm.value.case_type,
      stage: editForm.value.stage,
    })
    
    if (result.success) {
      message.success('保存成功')
      editMode.value = false
      editForm.value = null
      dialogVisible.value = false
      refreshData()
    } else {
      message.error(result.message || '保存失败')
    }
  } catch (error) {
    message.error('保存失败')
    console.error(error)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadTestCases()
})
</script>

<style scoped>
.test-case-view {
  padding: 0;
}

.upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px;
}

.text-primary {
  color: #007857;
}

.step-item {
  margin: 4px 0;
  line-height: 1.6;
}

.edit-step-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.step-num {
  min-width: 24px;
  text-align: right;
}
</style>
