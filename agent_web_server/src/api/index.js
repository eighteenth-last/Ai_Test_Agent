import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 3000000
})

// Request interceptor
api.interceptors.request.use(
  config => {
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

// Test case API - 测试用例相关
export const testCaseAPI = {
  generate(requirement) {
    return api.post('/test-cases/generate', { requirement })
  },
  getList(params) {
    return api.get('/test-cases/list', { params })
  },
  getById(id) {
    return api.get(`/test-cases/${id}`)
  },
  create(data) {
    return api.post('/test-cases', data)
  },
  update(id, data) {
    return api.put(`/test-cases/${id}`, data)
  },
  delete(id) {
    return api.delete(`/test-cases/${id}`)
  },
  uploadFile(file) {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/test-cases/upload-file', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  }
}

// Test code API - Browser-Use 执行相关
export const testCodeAPI = {
  executeBrowserUse(test_case_id, headless = true, max_steps = 20, use_vision = false) {
    return api.post('/test-code/execute-browser-use', {
      test_case_id,
      headless,
      max_steps,
      use_vision
    })
  },
  pauseTask(task_id) {
    return api.post(`/test-code/pause-task/${task_id}`)
  },
  resumeTask(task_id) {
    return api.post(`/test-code/resume-task/${task_id}`)
  },
  stopTask(task_id) {
    return api.post(`/test-code/stop-task/${task_id}`)
  },
  getTaskStatus(task_id) {
    return api.get(`/test-code/task-status/${task_id}`)
  }
}

// Test report API - 测试报告相关
export const testReportAPI = {
  generate(test_result_ids, format_type = 'markdown') {
    return api.post('/reports/generate', { test_result_ids, format_type })
  },
  generateMixed(report_ids, bug_report_ids = []) {
    return api.post('/reports/generate-mixed', { report_ids, bug_report_ids })
  },
  sendReport(report_content, contact_ids) {
    return api.post('/reports/send-report', { report_content, contact_ids })
  },
  getList(params) {
    return api.get('/reports/list', { params })
  },
  getById(report_id) {
    return api.get(`/reports/${report_id}`)
  },
  download(report_id) {
    const url = `/api/reports/${report_id}/download`
    const link = document.createElement('a')
    link.href = url
    link.download = `test_report_${report_id}.html`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }
}

// Bug report API - Bug报告相关
export const bugReportAPI = {
  getList(params) {
    return api.get('/bugs/list', { params })
  },
  getById(bug_id) {
    return api.get(`/bugs/${bug_id}`)
  },
  updateStatus(bug_id, status) {
    return api.put(`/bugs/${bug_id}/status`, null, {
      params: { status }
    })
  }
}

// Model API - 模型管理相关
export const modelAPI = {
  getList() {
    return api.get('/models/')
  },
  add(data) {
    return api.post('/models/', data)
  },
  update(id, data) {
    return api.put(`/models/${id}`, data)
  },
  delete(id) {
    return api.delete(`/models/${id}`)
  },
  activate(id) {
    return api.post(`/models/${id}/activate`)
  },
  getActive() {
    return api.get('/models/active/current')
  }
}

// Contact API - 联系人相关
export const contactAPI = {
  getList() {
    return api.get('/contacts')
  },
  add(data) {
    return api.post('/contacts', data)
  },
  update(id, data) {
    return api.put(`/contacts/${id}`, data)
  },
  delete(id) {
    return api.delete(`/contacts/${id}`)
  }
}

// Email API - 邮件发送记录相关
export const emailAPI = {
  // 发送自定义邮件（动态从联系人表获取收件人）
  sendEmail(contact_ids, subject, html_content, email_type = 'custom') {
    return api.post('/emails/send', {
      contact_ids,
      subject,
      html_content,
      email_type
    })
  },
  // 发送BUG通知给所有开启自动接收的联系人
  sendBugNotification(subject, html_content) {
    return api.post('/emails/send-bug-notification', null, {
      params: { subject, html_content }
    })
  },
  // 获取邮件发送记录列表
  getRecords(params) {
    return api.get('/emails/records', { params })
  },
  // 获取记录详情
  getRecordDetail(id) {
    return api.get(`/emails/records/${id}`)
  },
  // 获取统计信息
  getStatistics() {
    return api.get('/emails/statistics')
  },
  // 删除记录
  deleteRecord(id) {
    return api.delete(`/emails/records/${id}`)
  },
  
  // 邮件配置管理
  getConfigs() {
    return api.get('/emails/config')
  },
  getActiveConfig() {
    return api.get('/emails/config/active')
  },
  createConfig(data) {
    return api.post('/emails/config', data)
  },
  updateConfig(id, data) {
    return api.put(`/emails/config/${id}`, data)
  },
  activateConfig(id) {
    return api.post(`/emails/config/${id}/activate`)
  },
  deleteConfig(id) {
    return api.delete(`/emails/config/${id}`)
  }
}

// Dashboard API - 仪表盘数据
export const dashboardAPI = {
  getStats() {
    return api.get('/dashboard/stats')
  },
  getTestResultStats() {
    return api.get('/dashboard/test-result-stats')
  },
  getPriorityStats() {
    return api.get('/dashboard/priority-stats')
  },
  getTestTrend(days = 30) {
    return api.get('/dashboard/test-trend', { params: { days } })
  },
  getModuleStats() {
    return api.get('/dashboard/module-stats')
  },
  getEmailStats() {
    return api.get('/dashboard/email-stats')
  },
  getRecentActivities() {
    return api.get('/dashboard/recent-activities')
  }
}

export default api
