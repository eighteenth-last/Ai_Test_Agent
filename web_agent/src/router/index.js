import { createRouter, createWebHistory } from 'vue-router'
import TestCaseView from '../views/TestCaseView.vue'
import TestReportView from '../views/TestReportView.vue'
import ExecuteCaseView from '../views/ExecuteCaseView.vue'
import BugReportView from '../views/BugReportView.vue'

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
  },
  {
    path: '/bug-report',
    name: 'BugReport',
    component: BugReportView
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router