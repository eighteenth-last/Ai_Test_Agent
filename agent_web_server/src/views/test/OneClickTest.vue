<template>
  <div class="flex flex-col h-full gap-4">
    <div class="bg-white rounded-2xl border border-slate-100 shadow-sm px-6 py-4">
      <div class="flex items-start justify-between gap-4">
        <div class="flex items-center gap-3">
          <div class="w-11 h-11 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-lg">
            <i class="fas fa-rocket text-white text-lg"></i>
          </div>
          <div>
            <h2 class="text-xl font-bold text-slate-800 leading-tight">一键测试</h2>
            <p class="text-xs text-slate-500 mt-1">输入一句话，AI 生成用例并一键执行</p>
            <div class="flex flex-wrap gap-2 mt-3">
              <span class="inline-flex items-center gap-2 text-xs text-slate-500 bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-full">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                生成用例 → 选择用例 → 执行
              </span>
              <span class="inline-flex items-center gap-2 text-xs text-slate-500 bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-full">
                <i class="fas fa-shield-alt text-[10px] text-emerald-600"></i>
                支持中途停止
              </span>
            </div>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <n-button size="small" quaternary @click="showHistory = true" class="!rounded-xl">
            <template #icon><i class="fas fa-history"></i></template>
            历史记录
          </n-button>
          <n-button size="small" quaternary @click="clearAll" class="!rounded-xl">
            <template #icon><i class="fas fa-broom"></i></template>
            清空
          </n-button>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-3 gap-4 flex-1 min-h-0">
      <div class="xl:col-span-2 bg-white rounded-2xl shadow-sm border border-slate-100 flex flex-col overflow-hidden min-h-0">
        <div ref="messageContainer" class="flex-1 overflow-y-auto px-6 py-5 space-y-4">
          <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full text-slate-400">
            <div class="w-14 h-14 rounded-2xl bg-emerald-50 border border-emerald-100 flex items-center justify-center mb-4">
              <i class="fas fa-robot text-3xl text-emerald-500"></i>
            </div>
            <p class="text-lg font-semibold text-slate-700">输入需求，开始一键测试</p>
            <p class="text-sm mt-1 text-slate-500">比如：指定模块 + 重点功能 + 期望覆盖范围</p>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-6 w-full max-w-3xl">
              <button
                v-for="hint in quickHints"
                :key="hint"
                class="text-left p-3 rounded-2xl border border-slate-200 hover:border-emerald-300 hover:bg-emerald-50 transition-colors"
                @click="inputText = hint"
              >
                <div class="text-xs text-slate-400">示例指令</div>
                <div class="text-sm text-slate-700 mt-1">{{ hint }}</div>
              </button>
            </div>
          </div>

          <div v-for="(msg, idx) in messages" :key="idx" class="flex" :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
            <div v-if="msg.role === 'user'" class="max-w-[78%] bg-gradient-to-br from-emerald-600 to-teal-600 text-white rounded-2xl rounded-br-md px-4 py-3 shadow-sm">
              <p class="text-sm whitespace-pre-wrap leading-relaxed">{{ msg.content }}</p>
            </div>
            <div v-else class="max-w-[88%] flex gap-3">
              <div class="w-8 h-8 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center flex-shrink-0 mt-1 shadow-sm">
                <i class="fas fa-robot text-white text-xs"></i>
              </div>
              <div class="bg-slate-50 border border-slate-100 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm">
                <p class="text-sm text-slate-800 whitespace-pre-wrap leading-relaxed">{{ msg.content }}</p>
                <div v-if="msg.type === 'case_result'" class="mt-2">
                  <n-tag size="tiny" :type="msg.status === 'pass' ? 'success' : 'error'" round>
                    {{ msg.status === 'pass' ? '通过' : '失败' }}
                  </n-tag>
                </div>
              </div>
            </div>
          </div>

          <div v-if="loading" class="flex gap-3">
            <div class="w-8 h-8 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center flex-shrink-0 shadow-sm">
              <i class="fas fa-robot text-white text-xs"></i>
            </div>
            <div class="bg-slate-50 border border-slate-100 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm">
              <div class="flex items-center gap-2">
                <n-spin size="small" />
                <span class="text-sm text-slate-500">{{ loadingText }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="border-t border-slate-100 p-4 bg-white">
          <div class="flex gap-3 items-end">
            <div class="flex-1">
              <n-input
                v-model:value="inputText"
                type="textarea"
                placeholder="输入测试指令，如：帮我测试课程作业的所有功能"
                :autosize="{ minRows: 1, maxRows: 4 }"
                @keydown.enter.exact.prevent="sendMessage"
                :disabled="loading || executing"
              />
            </div>
            <n-button
              type="primary"
              :disabled="!inputText.trim() || loading || executing"
              @click="sendMessage"
              class="!rounded-xl"
            >
              <template #icon><i class="fas fa-paper-plane"></i></template>
              发送
            </n-button>
            <n-button
              v-if="executing || loading"
              type="error"
              ghost
              @click="stopSession"
              class="!rounded-xl"
            >
              <template #icon><i class="fas fa-stop"></i></template>
              停止
            </n-button>
          </div>
        </div>
      </div>

      <div class="bg-white rounded-2xl shadow-sm border border-slate-100 flex flex-col overflow-hidden min-h-0">
        <div class="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <i class="fas fa-list-check text-emerald-600"></i>
            <span class="text-sm font-semibold text-slate-800">用例选择与执行</span>
          </div>
          <n-tag size="small" :type="generatedCases.length ? 'info' : 'default'" round>
            {{ generatedCases.length ? `已生成 ${generatedCases.length}` : '未生成' }}
          </n-tag>
        </div>

        <div class="flex-1 overflow-y-auto p-5">
          <div class="grid grid-cols-2 gap-3">
            <div class="p-3 rounded-2xl bg-slate-50 border border-slate-100">
              <div class="text-xs text-slate-500">会话</div>
              <div class="text-sm font-semibold text-slate-800 mt-1">
                {{ currentSessionId ? `#${currentSessionId}` : '-' }}
              </div>
            </div>
            <div class="p-3 rounded-2xl bg-slate-50 border border-slate-100">
              <div class="text-xs text-slate-500">已选</div>
              <div class="text-sm font-semibold text-slate-800 mt-1">
                {{ generatedCases.length ? `${checkedCount}/${generatedCases.length}` : '0/0' }}
              </div>
            </div>
          </div>

          <div class="flex gap-2 mt-4">
            <n-button size="small" quaternary @click="selectAll" :disabled="generatedCases.length === 0" class="!rounded-xl">
              全选
            </n-button>
            <n-button size="small" quaternary @click="deselectAll" :disabled="generatedCases.length === 0" class="!rounded-xl">
              取消全选
            </n-button>
          </div>

          <div class="mt-4">
            <div class="flex items-center justify-between">
              <div class="text-xs text-slate-500 font-medium">用例列表</div>
              <span v-if="generatedCases.length" class="text-xs text-slate-400">勾选后执行</span>
            </div>

            <div v-if="generatedCases.length === 0" class="mt-3 p-4 rounded-2xl border border-dashed border-slate-200 text-center">
              <div class="text-sm text-slate-500">还没有生成用例</div>
              <div class="text-xs text-slate-400 mt-1">在左侧输入需求后，AI 会生成可执行的测试用例</div>
            </div>

            <div v-else class="mt-3 space-y-2">
              <div
                v-for="(c, ci) in generatedCases"
                :key="ci"
                class="flex items-start gap-2 p-3 bg-white rounded-2xl border border-slate-200 hover:border-emerald-300 transition-colors cursor-pointer group"
                @click.self="openCaseDetail(ci)"
              >
                <n-checkbox v-model:checked="c._checked" size="small" class="mt-0.5" />
                <div class="min-w-0 flex-1" @click="openCaseDetail(ci)">
                  <div class="flex items-center gap-1">
                    <span class="text-xs text-slate-400">{{ ci + 1 }}</span>
                    <i class="fas fa-pen text-[9px] text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity"></i>
                  </div>
                  <div class="text-sm text-slate-800 mt-0.5 break-words">{{ c.title }}</div>
                  <div v-if="c.module" class="text-[11px] text-slate-400 mt-0.5">{{ c.module }}</div>
                </div>
                <n-tag size="tiny" :type="c.priority === '1' ? 'error' : c.priority === '2' ? 'warning' : 'info'" round>
                  P{{ c.priority || 3 }}
                </n-tag>
              </div>
            </div>
          </div>
        </div>

        <div class="p-5 border-t border-slate-100 bg-white">
          <n-button
            type="primary"
            block
            class="!rounded-2xl"
            @click="confirmExecute"
            :disabled="!currentSessionId || checkedCount === 0 || loading || executing"
            :loading="executing"
          >
            <template #icon><i class="fas fa-play"></i></template>
            确认执行（{{ checkedCount }}）
          </n-button>
          <div class="text-[11px] text-slate-400 mt-2 leading-relaxed">
            执行会在左侧输出过程与结果；失败用例会生成 BUG 报告并触发邮件通知（如后端已启用）。
          </div>
        </div>
      </div>
    </div>

    <!-- 用例详情/编辑弹窗 -->
    <n-modal v-model:show="showCaseModal" preset="card" :title="caseEditing ? '编辑用例' : '用例详情'"
      style="width: 600px; max-width: 92vw;" :bordered="false" :segmented="{ content: true, footer: true }">
      <template v-if="editingCase">
        <div class="space-y-4">
          <div>
            <label class="text-xs text-slate-500 font-medium">用例标题</label>
            <n-input v-if="caseEditing" v-model:value="editingCase.title" placeholder="用例标题" class="mt-1" />
            <div v-else class="text-sm text-slate-800 mt-1">{{ editingCase.title }}</div>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="text-xs text-slate-500 font-medium">所属模块</label>
              <n-input v-if="caseEditing" v-model:value="editingCase.module" placeholder="模块名称" class="mt-1" size="small" />
              <div v-else class="text-sm text-slate-800 mt-1">{{ editingCase.module || '-' }}</div>
            </div>
            <div>
              <label class="text-xs text-slate-500 font-medium">优先级</label>
              <n-select v-if="caseEditing" v-model:value="editingCase.priority" :options="priorityOptions" class="mt-1" size="small" />
              <div v-else class="mt-1">
                <n-tag size="small" :type="editingCase.priority === '1' ? 'error' : editingCase.priority === '2' ? 'warning' : 'info'" round>
                  P{{ editingCase.priority || 3 }}
                </n-tag>
              </div>
            </div>
          </div>
          <div>
            <label class="text-xs text-slate-500 font-medium">测试步骤</label>
            <div v-if="caseEditing" class="mt-1 space-y-2">
              <div v-for="(step, si) in editingCase.steps" :key="si" class="flex items-center gap-2">
                <span class="text-xs text-slate-400 w-5 text-right flex-shrink-0">{{ si + 1 }}.</span>
                <n-input v-model:value="editingCase.steps[si]" size="small" class="flex-1" />
                <n-button size="tiny" quaternary type="error" @click="editingCase.steps.splice(si, 1)" :disabled="editingCase.steps.length <= 1">
                  <i class="fas fa-times"></i>
                </n-button>
              </div>
              <n-button size="tiny" dashed block @click="editingCase.steps.push('')" class="!rounded-lg">
                <template #icon><i class="fas fa-plus"></i></template>
                添加步骤
              </n-button>
            </div>
            <div v-else class="mt-1">
              <ol class="list-decimal list-inside text-sm text-slate-700 space-y-1">
                <li v-for="(step, si) in editingCase.steps" :key="si">{{ step }}</li>
              </ol>
            </div>
          </div>
          <div>
            <label class="text-xs text-slate-500 font-medium">预期结果</label>
            <n-input v-if="caseEditing" v-model:value="editingCase.expected" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" placeholder="预期结果" class="mt-1" />
            <div v-else class="text-sm text-slate-700 mt-1 whitespace-pre-wrap">{{ editingCase.expected || '-' }}</div>
          </div>
          <div>
            <label class="text-xs text-slate-500 font-medium">测试数据</label>
            <n-input v-if="caseEditing" v-model:value="editingCaseTestDataStr" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" placeholder='JSON 格式，如 {"username":"test"}' class="mt-1" :status="testDataError ? 'error' : undefined" />
            <div v-else class="text-sm text-slate-700 mt-1 font-mono bg-slate-50 rounded-lg p-2 break-all">{{ formatTestData(editingCase.test_data) }}</div>
            <div v-if="testDataError" class="text-xs text-red-500 mt-1">JSON 格式不正确</div>
          </div>
          <div class="flex items-center gap-2">
            <label class="text-xs text-slate-500 font-medium">需要浏览器</label>
            <n-switch v-if="caseEditing" v-model:value="editingCase.need_browser" size="small" />
            <n-tag v-else size="tiny" :type="editingCase.need_browser !== false ? 'success' : 'default'" round>
              {{ editingCase.need_browser !== false ? '是' : '否' }}
            </n-tag>
          </div>
        </div>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2">
          <template v-if="caseEditing">
            <n-button size="small" @click="caseEditing = false" class="!rounded-xl">取消</n-button>
            <n-button size="small" type="primary" @click="saveCaseEdit" class="!rounded-xl" :disabled="testDataError">
              <template #icon><i class="fas fa-check"></i></template>
              保存
            </n-button>
          </template>
          <template v-else>
            <n-button size="small" @click="showCaseModal = false" class="!rounded-xl">关闭</n-button>
            <n-button size="small" type="primary" ghost @click="caseEditing = true" class="!rounded-xl" :disabled="executing">
              <template #icon><i class="fas fa-pen"></i></template>
              编辑
            </n-button>
          </template>
        </div>
      </template>
    </n-modal>

    <!-- 历史记录抽屉 -->
    <n-drawer v-model:show="showHistory" :width="400" placement="right">
      <n-drawer-content title="历史记录">
        <div class="space-y-3">
          <div v-if="historyList.length === 0" class="text-center text-slate-400 py-8">
            暂无历史记录
          </div>
          <div v-for="h in historyList" :key="h.id"
            class="p-3 bg-slate-50 rounded-xl cursor-pointer hover:bg-emerald-50 transition-colors border border-transparent hover:border-emerald-200"
            @click="loadSession(h.id)">
            <div class="flex items-center justify-between">
              <span class="text-sm font-medium text-slate-700 truncate flex-1">{{ h.user_input }}</span>
              <n-tag size="tiny" :type="statusType(h.status)" round>{{ statusLabel(h.status) }}</n-tag>
            </div>
            <div class="text-xs text-slate-400 mt-1">{{ h.created_at }}</div>
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { NInput, NButton, NTag, NCheckbox, NSpin, NDrawer, NDrawerContent, NModal, NSelect, NSwitch, useMessage } from 'naive-ui'
import { oneclickAPI } from '@/api/index.js'

const message = useMessage()

const inputText = ref('')
const messages = ref([])
const loading = ref(false)
const executing = ref(false)
const loadingText = ref('AI 正在分析...')
const currentSessionId = ref(null)
const generatedCases = ref([])
const showHistory = ref(false)
const historyList = ref([])
const messageContainer = ref(null)

// 用例编辑相关
const showCaseModal = ref(false)
const caseEditing = ref(false)
const editingCaseIndex = ref(-1)
const editingCase = ref(null)
const editingCaseTestDataStr = ref('{}')
const testDataError = ref(false)

const priorityOptions = [
  { label: 'P1 - 最高', value: '1' },
  { label: 'P2 - 高', value: '2' },
  { label: 'P3 - 中', value: '3' },
  { label: 'P4 - 低', value: '4' },
]

const quickHints = [
  '帮我测试登录功能',
  '帮我测试课程作业的所有功能',
  '全面测试用户管理模块',
]

const checkedCount = computed(() => generatedCases.value.filter(c => c._checked).length)

function scrollToBottom() {
  nextTick(() => {
    if (messageContainer.value) {
      messageContainer.value.scrollTop = messageContainer.value.scrollHeight
    }
  })
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text) return

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  loading.value = true
  loadingText.value = 'AI 正在分析您的需求...'
  scrollToBottom()

  try {
    const res = await oneclickAPI.start(text)
    loading.value = false

    if (res.success) {
      currentSessionId.value = res.session_id
      const data = res.data

      // 添加 AI 消息
      if (data.messages) {
        // 跳过第一条 user 消息（已经显示了）
        const aiMsgs = data.messages.filter(m => m.role === 'assistant')
        for (const m of aiMsgs) {
          messages.value.push(m)
        }
      }

      // 处理生成的用例
      if (data.generated_cases && data.generated_cases.length > 0) {
        generatedCases.value = data.generated_cases.map(c => ({ ...c, _checked: true }))
      }
    } else {
      messages.value.push({ role: 'assistant', content: `❌ ${res.message || '启动失败'}` })
    }
  } catch (err) {
    loading.value = false
    messages.value.push({ role: 'assistant', content: `❌ 请求失败: ${err.message}` })
  }

  scrollToBottom()
}

async function confirmExecute() {
  if (!currentSessionId.value) return

  const selected = generatedCases.value.filter(c => c._checked).map(({ _checked, ...rest }) => rest)
  if (selected.length === 0) {
    message.warning('请至少选择一条用例')
    return
  }

  executing.value = true
  messages.value.push({ role: 'user', content: `确认执行 ${selected.length} 条测试用例` })
  scrollToBottom()

  try {
    const res = await oneclickAPI.confirm(currentSessionId.value, selected)
    executing.value = false

    if (res.success && res.data) {
      const aiMsgs = (res.data.messages || []).filter(m => m.role === 'assistant')
      // 只添加确认后的新消息
      const existingCount = messages.value.filter(m => m.role === 'assistant').length
      for (let i = existingCount; i < aiMsgs.length; i++) {
        messages.value.push(aiMsgs[i])
      }

      // 显示结果摘要
      const result = res.data.result
      if (result && result.summary) {
        const s = result.summary
        messages.value.push({
          role: 'assistant',
          content: `📊 测试完成！\n通过: ${s.passed}/${s.total}\n失败: ${s.failed}/${s.total}\n耗时: ${s.duration}秒`
        })
      }
    } else {
      messages.value.push({ role: 'assistant', content: `❌ ${res.message || '执行失败'}` })
    }
  } catch (err) {
    executing.value = false
    messages.value.push({ role: 'assistant', content: `❌ 执行异常: ${err.message}` })
  }

  scrollToBottom()
}

function selectAll() {
  generatedCases.value.forEach(c => c._checked = true)
}

function deselectAll() {
  generatedCases.value.forEach(c => c._checked = false)
}

function openCaseDetail(index) {
  const c = generatedCases.value[index]
  editingCaseIndex.value = index
  // 深拷贝，编辑时不影响原数据
  editingCase.value = JSON.parse(JSON.stringify({
    title: c.title || '',
    module: c.module || '',
    steps: Array.isArray(c.steps) ? [...c.steps] : (c.steps ? [c.steps] : ['']),
    expected: c.expected || '',
    priority: String(c.priority || '3'),
    test_data: c.test_data || {},
    need_browser: c.need_browser !== false,
  }))
  editingCaseTestDataStr.value = JSON.stringify(editingCase.value.test_data, null, 2)
  testDataError.value = false
  caseEditing.value = false
  showCaseModal.value = true
}

function saveCaseEdit() {
  // 校验 test_data JSON
  let parsedData = {}
  try {
    parsedData = JSON.parse(editingCaseTestDataStr.value || '{}')
    testDataError.value = false
  } catch {
    testDataError.value = true
    return
  }

  const idx = editingCaseIndex.value
  if (idx < 0 || idx >= generatedCases.value.length) return

  const original = generatedCases.value[idx]
  // 保留 _checked 状态，更新其他字段
  generatedCases.value[idx] = {
    ...original,
    title: editingCase.value.title,
    module: editingCase.value.module,
    steps: editingCase.value.steps.filter(s => s.trim() !== ''),
    expected: editingCase.value.expected,
    priority: editingCase.value.priority,
    test_data: parsedData,
    need_browser: editingCase.value.need_browser,
  }

  caseEditing.value = false
  message.success('用例已保存')
}

function formatTestData(data) {
  if (!data || Object.keys(data).length === 0) return '-'
  return JSON.stringify(data, null, 2)
}

// 监听 test_data 输入，实时校验 JSON
watch(editingCaseTestDataStr, (val) => {
  try {
    JSON.parse(val || '{}')
    testDataError.value = false
  } catch {
    testDataError.value = true
  }
})

function clearAll() {
  inputText.value = ''
  messages.value = []
  loading.value = false
  executing.value = false
  loadingText.value = 'AI 正在分析...'
  currentSessionId.value = null
  generatedCases.value = []
}

async function stopSession() {
  if (!currentSessionId.value) return
  try {
    await oneclickAPI.stop(currentSessionId.value)
    loading.value = false
    executing.value = false
    messages.value.push({ role: 'assistant', content: '⏹️ 测试已停止' })
  } catch (err) {
    message.error('停止失败')
  }
}

async function loadHistory() {
  try {
    const res = await oneclickAPI.getHistory({ page: 1, page_size: 50 })
    if (res.success) {
      historyList.value = res.data.items || []
    }
  } catch (err) {
    console.error('加载历史失败', err)
  }
}

async function loadSession(sessionId) {
  try {
    const res = await oneclickAPI.getSession(sessionId)
    if (res.success) {
      const data = res.data
      currentSessionId.value = data.id
      messages.value = data.messages || []
      if (data.generated_cases && data.generated_cases.length > 0) {
        generatedCases.value = data.generated_cases.map(c => ({ ...c, _checked: true }))
      }
      showHistory.value = false
      scrollToBottom()
    }
  } catch (err) {
    message.error('加载会话失败')
  }
}

function statusType(status) {
  const map = { completed: 'success', failed: 'error', executing: 'warning', cases_generated: 'info' }
  return map[status] || 'default'
}

function statusLabel(status) {
  const map = {
    init: '初始化', analyzing: '分析中', page_scanned: '已扫描',
    cases_generated: '已生成', confirmed: '已确认', executing: '执行中',
    completed: '已完成', failed: '失败'
  }
  return map[status] || status
}

onMounted(() => {
  loadHistory()
})
</script>
