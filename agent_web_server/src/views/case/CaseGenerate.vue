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
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { 
  NCard, NGrid, NGi, NFormItem, NInput, NButton, NUpload, NUploadDragger,
  useMessage
} from 'naive-ui'
import { testCaseAPI } from '@/api'

const message = useMessage()

// 表单数据
const form = ref({ requirement: '' })
const generating = ref(false)
const uploading = ref(false)
const selectedFile = ref(null)
const uploadRef = ref(null)

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
</style>
