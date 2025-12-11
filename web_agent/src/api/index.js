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

// Test case API
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

// Test code API - Browser-Use execution only
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

// Test report API
export const testReportAPI = {
  generate(test_result_ids, format_type = 'markdown') {
    return api.post('/reports/generate', { test_result_ids, format_type })
  },
  getList(params) {
    return api.get('/reports/list', { params })
  },
  getById(report_id) {
    return api.get(`/reports/${report_id}`)
  },
  download(report_id) {
    // 使用原生方式下载文件
    const url = `/api/reports/${report_id}/download`
    const link = document.createElement('a')
    link.href = url
    link.download = `test_report_${report_id}.html`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }
}

export default api