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
  }
}

export default api