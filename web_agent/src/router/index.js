import { createRouter, createWebHistory } from 'vue-router'
import TestCaseView from '../views/TestCaseView.vue'
import TestReportView from '../views/TestReportView.vue'
import ExecuteCaseView from '../views/ExecuteCaseView.vue'

const routes = [
  {
    path: '/',
    name: 'TestCase',
    component: TestCaseView
  },
  {
    path: '/execute-case',
    name: 'ExecuteCase',
    component: ExecuteCaseView
  },
  {
    path: '/test-report',
    name: 'TestReport',
    component: TestReportView
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router