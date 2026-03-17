<template>
  <div class="platform-control">
    <n-card title="项目管理平台总控制台" :bordered="false">
      <n-space vertical :size="16">
        <n-alert type="info" :bordered="false">
          选择项目管理平台并配置连接信息，激活后即可在左侧菜单中使用。
        </n-alert>

        <!-- 平台选择卡片 -->
        <n-grid :cols="3" :x-gap="16" :y-gap="16">
          <n-grid-item v-for="platform in supportedPlatforms" :key="platform.platform_id">
            <n-card
              :title="platform.platform_name"
              size="small"
              hoverable
              @click="selectPlatform(platform)"
              style="cursor: pointer"
            >
              <template #header-extra>
                <n-tag v-if="getPlatformStatus(platform.platform_id)" :type="getPlatformStatus(platform.platform_id).type" size="small">
                  {{ getPlatformStatus(platform.platform_id).text }}
                </n-tag>
              </template>
              <p class="text-sm text-gray-600">{{ platform.description }}</p>
            </n-card>
          </n-grid-item>
        </n-grid>
      </n-space>
    </n-card>

    <!-- 配置表单弹窗 -->
    <n-modal
      v-model:show="showConfigModal"
      preset="card"
      :title="`${selectedPlatform?.platform_name || ''} 配置`"
      style="width: 700px"
      :bordered="false"
      :segmented="{ content: 'soft', footer: 'soft' }"
    >
      <n-form ref="formRef" :model="formData" :rules="rules" label-placement="left" label-width="140">
        <n-form-item label="平台标识" path="platform_id">
          <n-input :value="selectedPlatform?.platform_id" disabled />
        </n-form-item>
        <n-form-item label="平台名称" path="platform_name">
          <n-input v-model:value="formData.platform_name" placeholder="可自定义显示名称" />
        </n-form-item>
        <n-form-item label="配置名称" path="config_name">
          <n-input v-model:value="formData.config_name" placeholder="如: 生产环境配置" />
        </n-form-item>
        <n-form-item label="平台地址" path="base_url">
          <n-input v-model:value="formData.base_url" placeholder="https://example.com" />
        </n-form-item>
        <n-form-item label="登录账号" path="account">
          <n-input v-model:value="formData.account" placeholder="用户名或邮箱" />
        </n-form-item>
        <n-form-item label="登录密码" path="password">
          <n-input v-model:value="formData.password" type="password" placeholder="密码" show-password-on="click" />
        </n-form-item>

        <!-- 禅道特有字段 -->
        <template v-if="selectedPlatform?.platform_id === 'zentao'">
          <n-form-item label="默认产品ID" path="default_product_id">
            <n-input-number v-model:value="formData.default_product_id" placeholder="可选" :show-button="false" style="width: 100%" />
          </n-form-item>
          <n-form-item label="API版本" path="api_version">
            <n-select v-model:value="formData.api_version" :options="apiVersionOptions" />
          </n-form-item>
        </template>

        <!-- PingCode 特有字段 -->
        <template v-if="selectedPlatform?.platform_id === 'pingcode'">
          <n-form-item label="鉴权方式" path="pingcode_auth_type">
            <n-select
              v-model:value="pingcodeExtra.auth_type"
              :options="pingcodeAuthOptions"
              @update:value="pingcodeExtra.auth_type = $event"
            />
          </n-form-item>
          <n-form-item label="Client ID" path="pingcode_client_id">
            <n-input v-model:value="pingcodeExtra.client_id" placeholder="OAuth2 Client ID" />
          </n-form-item>
          <n-form-item label="Client Secret" path="pingcode_client_secret">
            <n-input v-model:value="pingcodeExtra.client_secret" type="password" placeholder="OAuth2 Client Secret" show-password-on="click" />
          </n-form-item>
          <n-form-item v-if="pingcodeExtra.auth_type === 'authorization_code'" label="回调地址" path="pingcode_redirect_uri">
            <n-input v-model:value="pingcodeExtra.redirect_uri" placeholder="https://your-app.com/oauth/callback" />
          </n-form-item>
        </template>

        <!-- Worktile 特有字段 -->
        <template v-if="selectedPlatform?.platform_id === 'worktile'">
          <n-form-item label="鉴权方式">
            <n-text depth="3" style="font-size: 13px">Authorization Code（需要用户在浏览器完成授权，token 端点：dev.worktile.com）</n-text>
          </n-form-item>
          <n-form-item label="Client ID" path="worktile_client_id">
            <n-input v-model:value="worktileExtra.client_id" placeholder="OAuth2 Client ID" />
          </n-form-item>
          <n-form-item label="Client Secret" path="worktile_client_secret">
            <n-input v-model:value="worktileExtra.client_secret" type="password" placeholder="OAuth2 Client Secret" show-password-on="click" />
          </n-form-item>
          <n-form-item label="回调地址" path="worktile_redirect_uri">
            <n-input v-model:value="worktileExtra.redirect_uri" placeholder="https://your-app.com/oauth/callback（可选）" />
          </n-form-item>
        </template>

        <!-- 其他平台可能需要API Token -->
        <n-form-item v-if="needsApiToken(selectedPlatform?.platform_id)" label="API Token" path="api_token">
          <n-input v-model:value="formData.api_token" placeholder="可选，某些平台使用" />
        </n-form-item>

        <n-form-item label="备注说明" path="description">
          <n-input v-model:value="formData.description" type="textarea" placeholder="可选" />
        </n-form-item>

        <n-form-item label="启用状态">
          <n-space align="center">
            <n-switch
              v-model:value="formData.is_enabled"
              :checked-value="1"
              :unchecked-value="0"
            >
              <template #checked>在菜单中显示</template>
              <template #unchecked>在菜单中隐藏</template>
            </n-switch>
            <n-text depth="3" style="font-size: 12px">
              {{ formData.is_enabled ? '启用后将显示在左侧菜单' : '禁用后不会显示在菜单中' }}
            </n-text>
          </n-space>
        </n-form-item>
      </n-form>

      <template #footer>
        <n-space justify="space-between">
          <n-space>
            <n-button v-if="isEdit && !formData.is_active" type="success" @click="handleActivate">
              激活此配置
            </n-button>
            <n-button v-if="isEdit" type="error" @click="handleDelete">
              删除配置
            </n-button>
          </n-space>
          <n-space>
            <n-button @click="showConfigModal = false">取消</n-button>
            <n-button @click="handleTestConnection" :loading="testing">
              测试连接
            </n-button>
            <n-button type="primary" @click="handleSubmit" :loading="submitting">
              {{ isEdit ? '保存配置' : '创建配置' }}
            </n-button>
          </n-space>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { NCard, NButton, NSpace, NAlert, NGrid, NGridItem, NModal, NForm, NFormItem, NInput, NInputNumber, NSelect, NSwitch, NTag, NText, useMessage } from 'naive-ui'
import {
  getSupportedPlatforms,
  listPlatforms,
  getPlatform,
  createPlatform,
  updatePlatform,
  deletePlatform,
  activatePlatform,
  testConnection
} from '@/api/project'

const message = useMessage()
const supportedPlatforms = ref([])
const configuredPlatforms = ref([])
const selectedPlatform = ref(null)
const showConfigModal = ref(false)
const submitting = ref(false)
const testing = ref(false)
const isEdit = ref(false)
const formRef = ref(null)

// PingCode OAuth2 额外配置
const pingcodeExtra = ref({
  auth_type: 'client_credentials',
  client_id: '',
  client_secret: '',
  redirect_uri: ''
})

// Worktile OAuth2 额外配置（Authorization Code 流程）
const worktileExtra = ref({
  client_id: '',
  client_secret: '',
  redirect_uri: ''
})

const pingcodeAuthOptions = [
  { label: 'Client Credentials（推荐，服务端直接调用）', value: 'client_credentials' },
  { label: 'Authorization Code（需要用户授权）', value: 'authorization_code' }
]

const formData = ref({
  platform_id: '',
  platform_name: '',
  config_name: '',
  base_url: '',
  account: '',
  password: '',
  api_token: '',
  default_product_id: null,
  api_version: 'v2',
  description: '',
  is_enabled: 1,
  is_active: 0
})

const rules = {
  platform_name: { required: true, message: '请输入平台名称', trigger: 'blur' },
  config_name: { required: true, message: '请输入配置名称', trigger: 'blur' },
  base_url: { required: true, message: '请输入平台地址', trigger: 'blur' },
  account: { required: true, message: '请输入登录账号', trigger: 'blur' },
  password: { required: true, message: '请输入登录密码', trigger: 'blur' }
}

const apiVersionOptions = [
  { label: 'API v1', value: 'v1' },
  { label: 'API v2', value: 'v2' }
]

const needsApiToken = (platformId) => {
  return ['pingcode', 'worktile', 'ones', 'jira', 'asana', 'clickup'].includes(platformId)
}

const getPlatformStatus = (platformId) => {
  const config = configuredPlatforms.value.find(p => p.platform_id === platformId)
  if (!config) return null
  if (config.is_active) return { type: 'success', text: '已激活' }
  if (config.is_enabled) return { type: 'info', text: '已配置' }
  return { type: 'default', text: '已禁用' }
}

const getExtraConfig = (platformId) => {
  if (platformId === 'pingcode') return JSON.stringify(pingcodeExtra.value)
  if (platformId === 'worktile') return JSON.stringify(worktileExtra.value)
  return formData.value.extra_config
}

const selectPlatform = async (platform) => {
  selectedPlatform.value = platform
  showConfigModal.value = true

  try {
    const res = await getPlatform(platform.platform_id)
    if (res.success && res.data) {
      isEdit.value = true
      formData.value = {
        ...res.data,
        password: '',
        is_enabled: res.data.is_enabled || 0,
        is_active: res.data.is_active || 0
      }
      // 回显 extra_config
      if (res.data.extra_config) {
        try {
          const extra = typeof res.data.extra_config === 'string'
            ? JSON.parse(res.data.extra_config)
            : res.data.extra_config
          if (platform.platform_id === 'pingcode') {
            pingcodeExtra.value = { auth_type: 'client_credentials', client_id: '', client_secret: '', redirect_uri: '', ...extra }
          } else if (platform.platform_id === 'worktile') {
            worktileExtra.value = { client_id: '', client_secret: '', redirect_uri: '', ...extra }
          }
        } catch (e) { /* ignore */ }
      }
    } else {
      isEdit.value = false
      resetForm()
      formData.value.platform_id = platform.platform_id
      formData.value.platform_name = platform.platform_name
      if (platform.platform_id === 'pingcode') {
        pingcodeExtra.value = { auth_type: 'client_credentials', client_id: '', client_secret: '', redirect_uri: '' }
      } else if (platform.platform_id === 'worktile') {
        worktileExtra.value = { client_id: '', client_secret: '', redirect_uri: '' }
      }
    }
  } catch (error) {
    console.error('加载平台配置失败:', error)
    isEdit.value = false
    resetForm()
    formData.value.platform_id = platform.platform_id
    formData.value.platform_name = platform.platform_name
  }
}

const loadSupportedPlatforms = async () => {
  try {
    const res = await getSupportedPlatforms()
    if (res.success) supportedPlatforms.value = res.data
  } catch (error) {
    message.error('加载平台列表失败：' + error.message)
  }
}

const loadConfiguredPlatforms = async () => {
  try {
    const res = await listPlatforms()
    if (res.success) configuredPlatforms.value = res.data
  } catch (error) {
    console.error('加载已配置平台失败:', error)
  }
}

const handleSubmit = async () => {
  try {
    await formRef.value?.validate()
    submitting.value = true

    const data = {
      platform_id: selectedPlatform.value.platform_id,
      platform_name: formData.value.platform_name,
      config_name: formData.value.config_name,
      base_url: formData.value.base_url,
      account: formData.value.account,
      password: formData.value.password,
      api_token: formData.value.api_token,
      default_product_id: formData.value.default_product_id,
      api_version: formData.value.api_version,
      description: formData.value.description,
      is_enabled: formData.value.is_enabled,
      is_active: formData.value.is_active,
      extra_config: getExtraConfig(selectedPlatform.value.platform_id)
    }

    if (isEdit.value && !data.password) delete data.password

    const res = isEdit.value
      ? await updatePlatform(formData.value.id, data)
      : await createPlatform(data)

    if (res.success) {
      message.success(res.message || (isEdit.value ? '更新成功' : '创建成功'))
      showConfigModal.value = false
      selectedPlatform.value = null
      await loadConfiguredPlatforms()
      window.location.reload()
    }
  } catch (error) {
    if (error.message) {
      message.error((isEdit.value ? '更新' : '创建') + '失败：' + error.message)
    }
  } finally {
    submitting.value = false
  }
}

const handleActivate = async () => {
  try {
    const res = await activatePlatform(formData.value.id)
    if (res.success) {
      message.success(res.message)
      formData.value.is_active = 1
      await loadConfiguredPlatforms()
      window.location.reload()
    }
  } catch (error) {
    message.error('激活失败：' + error.message)
  }
}

const handleTestConnection = async () => {
  if (!formData.value.base_url) {
    message.warning('请先填写平台地址')
    return
  }
  testing.value = true
  try {
    const res = await testConnection({
      base_url: formData.value.base_url,
      account: formData.value.account,
      password: formData.value.password,
      api_token: formData.value.api_token,
      platform_id: selectedPlatform.value?.platform_id,
      api_version: formData.value.api_version,
      extra_config: getExtraConfig(selectedPlatform.value?.platform_id)
    })
    if (res.success) {
      message.success(res.message || '连接成功')
    } else {
      message.error(res.message || '连接失败')
    }
  } catch (error) {
    message.error('测试失败：' + error.message)
  } finally {
    testing.value = false
  }
}

const handleDelete = async () => {
  if (!confirm(`确定要删除 "${formData.value.platform_name}" 的配置吗？`)) return
  try {
    const res = await deletePlatform(formData.value.id)
    if (res.success) {
      message.success(res.message)
      showConfigModal.value = false
      selectedPlatform.value = null
      await loadConfiguredPlatforms()
      window.location.reload()
    }
  } catch (error) {
    message.error('删除失败：' + error.message)
  }
}

const resetForm = () => {
  formData.value = {
    platform_id: '',
    platform_name: '',
    config_name: '',
    base_url: '',
    account: '',
    password: '',
    api_token: '',
    default_product_id: null,
    api_version: 'v2',
    description: '',
    is_enabled: 1,
    is_active: 0
  }
  isEdit.value = false
}

onMounted(() => {
  loadSupportedPlatforms()
  loadConfiguredPlatforms()
})
</script>

<style scoped>
.platform-control {
  max-width: 1400px;
}
</style>
