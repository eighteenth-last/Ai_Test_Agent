import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  // 首页仪表盘
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/dashboard/Dashboard.vue'),
    meta: { title: '数据看板', menu: 'dashboard' }
  },
  // 测试模块
  {
    path: '/test/func',
    name: 'TestFunc',
    component: () => import('@/views/test/FuncTest.vue'),
    meta: { title: '功能测试', menu: 'test' }
  },
  {
    path: '/test/press',
    name: 'TestPress',
    component: () => import('@/views/test/PressTest.vue'),
    meta: { title: '性能测试', menu: 'test' }
  },
  {
    path: '/test/security',
    name: 'TestSecurity',
    component: () => import('@/views/test/SecurityTest.vue'),
    meta: { title: '安全测试', menu: 'test' }
  },
  {
    path: '/test/api',
    name: 'TestApi',
    component: () => import('@/views/test/ApiTest.vue'),
    meta: { title: '接口测试', menu: 'test' }
  },
  {
    path: '/test/oneclick',
    name: 'TestOneClick',
    component: () => import('@/views/test/OneClickTest.vue'),
    meta: { title: '一键测试', menu: 'test' }
  },
  // 邮件通知模块
  {
    path: '/mail/contacts',
    name: 'MailContacts',
    component: () => import('@/views/mail/Contacts.vue'),
    meta: { title: '联系人管理', menu: 'mail' }
  },
  {
    path: '/mail/send',
    name: 'MailSend',
    component: () => import('@/views/mail/SendMail.vue'),
    meta: { title: '邮件发送', menu: 'mail' }
  },
  {
    path: '/mail/config',
    name: 'MailConfig',
    component: () => import('@/views/mail/EmailConfig.vue'),
    meta: { title: '邮件配置', menu: 'mail' }
  },
  // 模型管理模块
  {
    path: '/model/manage',
    name: 'ModelManage',
    component: () => import('@/views/model/ModelManage.vue'),
    meta: { title: '模型信息与切换', menu: 'model' }
  },
  {
    path: '/model/providers',
    name: 'ProviderManage',
    component: () => import('@/views/model/ProviderManage.vue'),
    meta: { title: '供应商管理', menu: 'model' }
  },
  // 测试用例生成模块
  {
    path: '/case/generate',
    name: 'CaseGenerate',
    component: () => import('@/views/case/CaseGenerate.vue'),
    meta: { title: '用例生成模块', menu: 'case' }
  },
  {
    path: '/case/manage',
    name: 'CaseManage',
    component: () => import('@/views/case/CaseManage.vue'),
    meta: { title: '用例管理', menu: 'case' }
  },
  {
    path: '/case/api-spec',
    name: 'ApiSpecManage',
    component: () => import('@/views/case/ApiSpecManage.vue'),
    meta: { title: '接口文件管理', menu: 'case' }
  },
  // 提示词模块
  {
    path: '/prompt/list',
    name: 'PromptList',
    component: () => import('@/views/prompt/PromptList.vue'),
    meta: { title: 'Skills仓库', menu: 'prompt' }
  },
  {
    path: '/skills/manage',
    name: 'SkillManage',
    component: () => import('@/views/skills/SkillManage.vue'),
    meta: { title: 'Skills管理', menu: 'prompt' }
  },
  // 测试报告模块
  {
    path: '/report/bug',
    name: 'ReportBug',
    component: () => import('@/views/report/BugReport.vue'),
    meta: { title: 'Bug测试报告', menu: 'report' }
  },
  {
    path: '/report/run',
    name: 'ReportRun',
    component: () => import('@/views/report/RunReport.vue'),
    meta: { title: '运行测试报告', menu: 'report' }
  },
  {
    path: '/report/mixed',
    name: 'ReportMixed',
    component: () => import('@/views/report/MixedReport.vue'),
    meta: { title: '综合测试报告', menu: 'report' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
