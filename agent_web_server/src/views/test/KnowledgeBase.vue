<template>
  <div>
    <!-- 顶部 -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center shadow-lg">
          <i class="fas fa-brain text-white text-lg"></i>
        </div>
        <div>
          <h2 class="text-xl font-bold text-slate-800">页面知识库</h2>
          <p class="text-xs text-slate-400">一键测试 RAG 记忆层 — 探索一次，记住永久</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <n-button size="small" quaternary @click="loadStats">
          <template #icon><i class="fas fa-sync-alt"></i></template>
          刷新
        </n-button>
        <n-button size="small" type="warning" @click="loadStaleList">
          <template #icon><i class="fas fa-clock"></i></template>
          查看老化记录
        </n-button>
        <n-button size="small" type="info" @click="openConfigModal">
          <template #icon><i class="fas fa-cog"></i></template>
          Collection 配置
        </n-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-4 text-center">
        <p class="text-2xl font-bold text-blue-600">{{ stats.total_records ?? '-' }}</p>
        <p class="text-xs text-slate-400 mt-1">总记录数</p>
      </div>
      <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-4 text-center">
        <p class="text-2xl font-bold text-emerald-600">{{ stats.vector_count ?? '-' }}</p>
        <p class="text-xs text-slate-400 mt-1">向量条数</p>
      </div>
      <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-4 text-center">
        <p class="text-2xl font-bold text-amber-600">{{ stats.stale_count ?? '-' }}</p>
        <p class="text-xs text-slate-400 mt-1">老化记录</p>
      </div>
      <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-4 text-center">
        <n-tag :type="stats.qdrant_healthy ? 'success' : 'error'" round size="small">
          {{ stats.qdrant_healthy ? '正常' : '异常' }}
        </n-tag>
        <p class="text-xs text-slate-400 mt-1">Qdrant 状态</p>
      </div>
    </div>

    <!-- 搜索 + 筛选 -->
    <div class="flex items-center gap-3 mb-4">
      <n-input v-model:value="searchQuery" placeholder="搜索页面 URL、摘要、模块名..."
        clearable size="small" style="max-width: 360px" @keydown.enter="loadList">
        <template #prefix><i class="fas fa-search text-slate-400"></i></template>
      </n-input>
      <n-select v-model:value="filterDomain" :options="domainOptions" placeholder="按域名筛选"
        clearable size="small" style="width: 200px" />
      <n-select v-model:value="filterPageType" :options="pageTypeOptions" placeholder="按页面类型"
        clearable size="small" style="width: 160px" />
      <n-button size="small" type="primary" @click="loadList">
        <template #icon><i class="fas fa-filter"></i></template>
        筛选
      </n-button>
    </div>

    <!-- 知识列表 -->
    <div v-if="knowledgeList.length > 0" class="space-y-3">
      <div v-for="item in knowledgeList" :key="item.id"
        class="bg-white rounded-2xl border border-slate-100 shadow-sm hover:shadow-md transition-all p-5">
        <div class="flex items-start justify-between">
          <!-- 左侧信息 -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1.5">
              <n-tag size="tiny" :type="pageTypeTag(item.page_type)" round :bordered="false">
                {{ item.page_type || '未知' }}
              </n-tag>
              <span class="text-sm font-semibold text-slate-800 truncate">{{ item.summary || item.url }}</span>
            </div>
            <div class="flex items-center gap-3 text-xs text-slate-400">
              <span><i class="fas fa-link mr-1"></i>{{ item.url }}</span>
              <span v-if="item.domain"><i class="fas fa-globe mr-1"></i>{{ item.domain }}</span>
              <span v-if="item.module_name"><i class="fas fa-cube mr-1"></i>{{ item.module_name }}</span>
            </div>
            <div class="flex items-center gap-3 text-xs text-slate-400 mt-1">
              <span>v{{ item.version ?? 1 }}</span>
              <span>哈希: {{ (item.hash_signature || '').substring(0, 12) }}...</span>
              <span v-if="item.updated_at">更新: {{ item.updated_at }}</span>
            </div>
          </div>
          <!-- 右侧操作 -->
          <div class="flex items-center gap-1 ml-3 flex-shrink-0">
            <n-button size="tiny" quaternary @click="viewDetail(item)">
              <template #icon><i class="fas fa-eye text-xs"></i></template>
            </n-button>
            <n-button size="tiny" quaternary @click="lookupSimilar(item)">
              <template #icon><i class="fas fa-search-plus text-xs"></i></template>
            </n-button>
            <n-popconfirm @positive-click="deleteKnowledge(item)">
              <template #trigger>
                <n-button size="tiny" quaternary type="error">
                  <template #icon><i class="fas fa-trash text-xs"></i></template>
                </n-button>
              </template>
              确定删除此知识记录？
            </n-popconfirm>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!loading" class="text-center py-16 text-slate-400">
      <i class="fas fa-database text-4xl mb-4 text-slate-300"></i>
      <p class="text-lg">知识库为空</p>
      <p class="text-sm mt-1">使用一键测试探索页面后，知识会自动存入</p>
    </div>

    <!-- 加载态 -->
    <div v-if="loading" class="flex justify-center py-12">
      <n-spin size="medium" />
    </div>

    <!-- 详情弹窗 -->
    <n-modal v-model:show="showDetail" preset="card" title="知识详情" style="width: 720px; max-width: 90vw">
      <div v-if="detailData" class="space-y-4 max-h-[70vh] overflow-auto">
        <div class="grid grid-cols-2 gap-3">
          <div><span class="text-xs text-slate-400">URL</span>
            <p class="text-sm font-mono break-all">{{ detailData.url }}</p></div>
          <div><span class="text-xs text-slate-400">页面类型</span>
            <p class="text-sm">{{ detailData.page_type }}</p></div>
          <div><span class="text-xs text-slate-400">域名</span>
            <p class="text-sm">{{ detailData.domain }}</p></div>
          <div><span class="text-xs text-slate-400">模块</span>
            <p class="text-sm">{{ detailData.module_name || '-' }}</p></div>
          <div class="col-span-2"><span class="text-xs text-slate-400">摘要</span>
            <p class="text-sm">{{ detailData.summary }}</p></div>
        </div>

        <!-- 表单能力 -->
        <div v-if="detailData.forms && detailData.forms.length > 0">
          <p class="text-xs font-semibold text-slate-500 mb-2"><i class="fas fa-edit mr-1"></i>表单 ({{ detailData.forms.length }})</p>
          <div v-for="(form, fi) in detailData.forms" :key="fi"
            class="bg-slate-50 rounded-xl p-3 mb-2 text-xs">
            <p class="font-semibold mb-1">{{ form.form_name || `表单 ${fi + 1}` }}</p>
            <div v-for="(field, ffi) in (form.fields || [])" :key="ffi"
              class="flex gap-2 text-slate-500 ml-2">
              <span class="text-slate-700">{{ field.field_name }}</span>
              <n-tag size="tiny" :bordered="false">{{ field.field_type }}</n-tag>
              <span v-if="field.required" class="text-red-400">*必填</span>
            </div>
          </div>
        </div>

        <!-- 表格能力 -->
        <div v-if="detailData.tables && detailData.tables.length > 0">
          <p class="text-xs font-semibold text-slate-500 mb-2"><i class="fas fa-table mr-1"></i>表格 ({{ detailData.tables.length }})</p>
          <div v-for="(table, ti) in detailData.tables" :key="ti"
            class="bg-slate-50 rounded-xl p-3 mb-2 text-xs">
            <p class="font-semibold mb-1">{{ table.table_name || `表格 ${ti + 1}` }}</p>
            <p class="text-slate-500">列: {{ (table.columns || []).join(', ') }}</p>
            <p v-if="table.has_pagination" class="text-slate-400">支持分页</p>
          </div>
        </div>

        <!-- 按钮 / 链接 -->
        <div class="grid grid-cols-2 gap-3">
          <div v-if="detailData.buttons && detailData.buttons.length > 0">
            <p class="text-xs font-semibold text-slate-500 mb-1"><i class="fas fa-mouse-pointer mr-1"></i>按钮</p>
            <div class="flex flex-wrap gap-1">
              <n-tag v-for="(btn, bi) in detailData.buttons" :key="bi" size="tiny" round>{{ btn }}</n-tag>
            </div>
          </div>
          <div v-if="detailData.links && detailData.links.length > 0">
            <p class="text-xs font-semibold text-slate-500 mb-1"><i class="fas fa-external-link-alt mr-1"></i>链接</p>
            <div class="flex flex-wrap gap-1">
              <n-tag v-for="(lnk, li) in detailData.links" :key="li" size="tiny" round type="info">{{ lnk }}</n-tag>
            </div>
          </div>
        </div>

        <!-- 元信息 -->
        <div class="bg-slate-50 rounded-xl p-3 text-xs text-slate-500 grid grid-cols-3 gap-2">
          <div>版本: v{{ detailData.version ?? 1 }}</div>
          <div>哈希: {{ (detailData.hash_signature || '').substring(0, 20) }}</div>
          <div>标签: {{ (detailData.tags || []).join(', ') || '-' }}</div>
          <div>需登录: {{ detailData.auth_required ? '是' : '否' }}</div>
          <div>文件上传: {{ detailData.has_file_upload ? '是' : '否' }}</div>
          <div>导出功能: {{ detailData.has_export ? '是' : '否' }}</div>
        </div>
      </div>
    </n-modal>

    <!-- 相似搜索弹窗 -->
    <n-modal v-model:show="showSimilar" preset="card" title="相似页面搜索" style="width: 640px; max-width: 90vw">
      <div v-if="similarResults.length > 0" class="space-y-2 max-h-[60vh] overflow-auto">
        <div v-for="(r, ri) in similarResults" :key="ri"
          class="bg-slate-50 rounded-xl p-3 flex items-center justify-between text-sm">
          <div>
            <p class="font-semibold text-slate-700">{{ r.summary || r.url }}</p>
            <p class="text-xs text-slate-400">{{ r.url }}</p>
          </div>
          <n-tag size="small" type="success" round>{{ (r.score * 100).toFixed(1) }}%</n-tag>
        </div>
      </div>
      <div v-else class="text-center py-8 text-slate-400">
        <p>未找到相似页面</p>
      </div>
    </n-modal>

    <!-- 老化记录弹窗 -->
    <n-modal v-model:show="showStale" preset="card" title="老化记录（超过 30 天未更新）" style="width: 640px; max-width: 90vw">
      <div v-if="staleList.length > 0" class="space-y-2 max-h-[60vh] overflow-auto">
        <div v-for="item in staleList" :key="item.id"
          class="bg-amber-50 rounded-xl p-3 flex items-center justify-between text-sm">
          <div>
            <p class="font-semibold text-slate-700">{{ item.summary || item.url }}</p>
            <p class="text-xs text-slate-400">{{ item.url }} · v{{ item.version }} · {{ item.updated_at }}</p>
          </div>
          <n-popconfirm @positive-click="deleteKnowledge(item)">
            <template #trigger>
              <n-button size="tiny" type="error" quaternary>
                <template #icon><i class="fas fa-trash"></i></template>
              </n-button>
            </template>
            确认删除？
          </n-popconfirm>
        </div>
      </div>
      <div v-else class="text-center py-8 text-slate-400">
        <p>暂无老化记录</p>
      </div>
    </n-modal>

    <!-- Collection 配置 Modal -->
    <n-modal v-model:show="showConfig" preset="card" title="Qdrant Collection 配置" style="width: 680px; max-width: 95vw">
      <n-form :model="configForm" label-placement="left" label-width="140" size="small" class="space-y-1">
        <n-divider title-placement="left" class="!my-3 text-xs text-slate-500">Qdrant 连接</n-divider>
        <n-form-item label="Collection 名称">
          <n-input v-model:value="configForm.collection_name" placeholder="page_knowledge" />
        </n-form-item>
        <n-form-item label="Qdrant 主机">
          <n-input v-model:value="configForm.qdrant_host" placeholder="localhost" />
        </n-form-item>
        <n-form-item label="Qdrant 端口">
          <n-input-number v-model:value="configForm.qdrant_port" :min="1" :max="65535" style="width:100%" />
        </n-form-item>
        <n-form-item label="向量维度">
          <n-input-number v-model:value="configForm.vector_size" :min="1" :max="65536" style="width:100%" />
        </n-form-item>
        <n-form-item label="距离度量">
          <n-select v-model:value="configForm.distance" :options="distanceOptions" />
        </n-form-item>

        <n-divider title-placement="left" class="!my-3 text-xs text-slate-500">Embedding 配置</n-divider>
        <n-form-item label="Embedding 模型">
          <n-input v-model:value="configForm.embedding_model" placeholder="Qwen/Qwen3-Embedding-4B" />
        </n-form-item>
        <n-form-item label="Embedding API 地址">
          <n-input v-model:value="configForm.embedding_api_url" placeholder="https://api.siliconflow.cn/v1/embeddings" />
        </n-form-item>
        <n-form-item label="Embedding API Key">
          <n-input v-model:value="configForm.embedding_api_key" type="password" show-password-on="click" placeholder="sk-xxx" />
        </n-form-item>
      </n-form>

      <div class="flex items-center justify-between mt-5 pt-4 border-t border-slate-100">
        <n-tag v-if="configForm._is_default" type="warning" size="small" round>当前为默认配置，尚未存入数据库</n-tag>
        <span v-else class="text-xs text-slate-400">ID: {{ configForm.id }}</span>
        <div class="flex gap-2">
          <n-button size="small" :loading="configLoading" @click="saveConfig">
            <template #icon><i class="fas fa-save"></i></template>
            保存配置
          </n-button>
          <n-button type="primary" size="small" :loading="createLoading" @click="initCollection(false)">
            <template #icon><i class="fas fa-database"></i></template>
            初始化 Collection
          </n-button>
          <n-popconfirm @positive-click="initCollection(true)">
            <template #trigger>
              <n-button type="error" size="small" :loading="createLoading">
                <template #icon><i class="fas fa-redo"></i></template>
                强制重建
              </n-button>
            </template>
            强制重建将删除现有 Collection 及其所有向量数据，确定继续？
          </n-popconfirm>
        </div>
      </div>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { knowledgeAPI } from '@/api/index'

const message = useMessage()

// ─── State ───────────────────────────
const loading = ref(false)
const stats = ref({})
const knowledgeList = ref([])
const searchQuery = ref('')
const filterDomain = ref(null)
const filterPageType = ref(null)
const domainOptions = ref([])
const pageTypeOptions = [
  { label: '表单页', value: 'form' },
  { label: '列表页', value: 'list' },
  { label: '详情页', value: 'detail' },
  { label: '仪表盘', value: 'dashboard' },
  { label: '登录页', value: 'login' },
  { label: '混合页', value: 'mixed' },
]

// 详情
const showDetail = ref(false)
const detailData = ref(null)

// 相似搜索
const showSimilar = ref(false)
const similarResults = ref([])

// 老化
const showStale = ref(false)
const staleList = ref([])

// Collection 配置
const showConfig = ref(false)
const configLoading = ref(false)
const createLoading = ref(false)
const configForm = ref({
  id: null,
  collection_name: 'page_knowledge',
  vector_size: 1024,
  distance: 'Cosine',
  qdrant_host: 'localhost',
  qdrant_port: 6333,
  embedding_model: 'Qwen/Qwen3-Embedding-4B',
  embedding_api_url: 'https://api.siliconflow.cn/v1/embeddings',
  embedding_api_key: '',
  _is_default: false,
})
const distanceOptions = [
  { label: 'Cosine（余弦）', value: 'Cosine' },
  { label: 'Dot（点积）', value: 'Dot' },
  { label: 'Euclid（欧氏）', value: 'Euclid' },
  { label: 'Manhattan（曼哈顿）', value: 'Manhattan' },
]

// ─── API Calls ───────────────────────
async function loadStats() {
  try {
    const res = await knowledgeAPI.getStats()
    stats.value = res.data || res
  } catch (e) {
    console.error('获取统计失败', e)
  }
}

async function loadList() {
  loading.value = true
  try {
    const res = await knowledgeAPI.getList({
      domain: filterDomain.value || undefined,
      page_type: filterPageType.value || undefined,
    })
    const list = res.data || res.records || res
    knowledgeList.value = Array.isArray(list) ? list : []
    // 构建域名筛选项
    const domains = new Set()
    knowledgeList.value.forEach(k => { if (k.domain) domains.add(k.domain) })
    domainOptions.value = [...domains].map(d => ({ label: d, value: d }))
  } catch (e) {
    console.error('获取列表失败', e)
  } finally {
    loading.value = false
  }
}

async function viewDetail(item) {
  try {
    const res = await knowledgeAPI.getDetail(item.url || item.id)
    detailData.value = res.data || res
    showDetail.value = true
  } catch (e) {
    message.error('获取详情失败')
  }
}

async function lookupSimilar(item) {
  try {
    const res = await knowledgeAPI.retrieveContext(item.summary || item.url)
    similarResults.value = res.data || res.contexts || res
    if (!Array.isArray(similarResults.value)) similarResults.value = []
    showSimilar.value = true
  } catch (e) {
    message.error('相似搜索失败')
  }
}

async function deleteKnowledge(item) {
  try {
    await knowledgeAPI.delete(item.url || item.id)
    message.success('已删除')
    loadList()
    loadStats()
  } catch (e) {
    message.error('删除失败')
  }
}

async function loadStaleList() {
  try {
    const res = await knowledgeAPI.getStale()
    staleList.value = res.data || res.records || res
    if (!Array.isArray(staleList.value)) staleList.value = []
    showStale.value = true
  } catch (e) {
    message.error('获取老化记录失败')
  }
}

async function openConfigModal() {
  try {
    const res = await knowledgeAPI.getCollectionConfig()
    const data = res.data || res
    configForm.value = {
      id: data.id || null,
      collection_name: data.collection_name || 'page_knowledge',
      vector_size: data.vector_size || 1024,
      distance: data.distance || 'Cosine',
      qdrant_host: data.qdrant_host || 'localhost',
      qdrant_port: data.qdrant_port || 6333,
      embedding_model: data.embedding_model || 'Qwen/Qwen3-Embedding-4B',
      embedding_api_url: data.embedding_api_url || 'https://api.siliconflow.cn/v1/embeddings',
      embedding_api_key: data.embedding_api_key || '',
      _is_default: !!res.is_default,
    }
  } catch (e) {
    console.error('加载配置失败', e)
  }
  showConfig.value = true
}

async function saveConfig() {
  configLoading.value = true
  try {
    const payload = { ...configForm.value }
    delete payload.id
    delete payload._is_default
    const res = await knowledgeAPI.saveCollectionConfig(payload)
    if (res.success !== false) {
      const d = res.data || res
      configForm.value.id = d.id || configForm.value.id
      configForm.value._is_default = false
      message.success('配置已保存')
    } else {
      message.error(res.message || '保存失败')
    }
  } catch (e) {
    message.error('保存配置失败')
  } finally {
    configLoading.value = false
  }
}

async function initCollection(force = false) {
  createLoading.value = true
  try {
    const res = await knowledgeAPI.createCollection(force)
    if (res.success !== false) {
      message.success(res.message || 'Collection 初始化成功')
      showConfig.value = false
      loadStats()
    } else {
      message.error(res.message || '初始化失败')
    }
  } catch (e) {
    message.error('初始化 Collection 失败')
  } finally {
    createLoading.value = false
  }
}

// ─── Helpers ─────────────────────────
function pageTypeTag(type) {
  const map = { form: 'info', list: 'success', detail: 'warning', dashboard: 'primary', login: 'error', mixed: 'default' }
  return map[type] || 'default'
}

// ─── Init ────────────────────────────
onMounted(() => {
  loadStats()
  loadList()
})
</script>
