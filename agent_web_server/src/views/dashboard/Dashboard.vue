<template>
  <div class="dashboard-container">
    <!-- 顶部统计卡片 -->
    <div class="stats-cards">
      <div class="stat-card test-cases">
        <div class="stat-icon">
          <i class="fas fa-list-check"></i>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats.testCases }}</div>
          <div class="stat-label">测试用例总数</div>
        </div>
      </div>
      
      <div class="stat-card test-reports">
        <div class="stat-icon">
          <i class="fas fa-file-lines"></i>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats.testReports }}</div>
          <div class="stat-label">测试报告数</div>
        </div>
      </div>
      
      <div class="stat-card bugs">
        <div class="stat-icon">
          <i class="fas fa-bug"></i>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats.bugReports }}</div>
          <div class="stat-label">Bug报告数</div>
        </div>
      </div>
      
      <div class="stat-card emails">
        <div class="stat-icon">
          <i class="fas fa-envelope"></i>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats.emailsSent }}</div>
          <div class="stat-label">邮件发送数</div>
        </div>
      </div>
    </div>

    <!-- 图表区域 -->
    <div class="charts-row">
      <!-- 测试结果分布 -->
      <n-card class="chart-card" title="测试结果分布">
        <div ref="testResultChartRef" class="chart-container"></div>
      </n-card>
      
      <!-- 用例优先级分布 -->
      <n-card class="chart-card" title="用例优先级分布">
        <div ref="priorityChartRef" class="chart-container"></div>
      </n-card>
    </div>

    <div class="charts-row">
      <!-- 近期测试趋势 -->
      <n-card class="chart-card wide" title="测试趋势">
        <template #header-extra>
          <n-radio-group v-model:value="trendRange" size="small" @update:value="loadTrendChart">
            <n-radio-button value="30">近一月</n-radio-button>
            <n-radio-button value="90">近一季</n-radio-button>
            <n-radio-button value="365">近一年</n-radio-button>
          </n-radio-group>
        </template>
        <div ref="trendChartRef" class="chart-container"></div>
      </n-card>
    </div>

    <div class="charts-row">
      <!-- 用例类型分布 -->
      <n-card class="chart-card" title="测试用例类型分布">
        <div ref="moduleChartRef" class="chart-container"></div>
      </n-card>
      
      <!-- 邮件发送统计 -->
      <n-card class="chart-card" title="邮件发送统计">
        <div ref="emailChartRef" class="chart-container"></div>
      </n-card>
    </div>

    <!-- 最近活动 -->
    <n-card class="recent-activity" title="最近测试活动">
      <n-timeline>
        <n-timeline-item
          v-for="(activity, index) in recentActivities"
          :key="index"
          :type="activity.type"
          :title="activity.title"
          :content="activity.content"
          :time="activity.time"
        />
      </n-timeline>
      <n-empty v-if="recentActivities.length === 0" description="暂无测试活动" />
    </n-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { NCard, NTimeline, NTimelineItem, NEmpty, NRadioGroup, NRadioButton, useMessage } from 'naive-ui'
import * as echarts from 'echarts'
import { dashboardAPI } from '@/api'

const message = useMessage()

// 时间范围
const trendRange = ref('30')

// 统计数据
const stats = ref({
  testCases: 0,
  testReports: 0,
  bugReports: 0,
  emailsSent: 0
})

// 图表引用
const testResultChartRef = ref(null)
const priorityChartRef = ref(null)
const trendChartRef = ref(null)
const moduleChartRef = ref(null)
const emailChartRef = ref(null)

// 图表实例
let testResultChart = null
let priorityChart = null
let trendChart = null
let moduleChart = null
let emailChart = null

// 最近活动
const recentActivities = ref([])

// 加载统计数据
const loadStats = async () => {
  try {
    const result = await dashboardAPI.getStats()
    if (result.success) {
      stats.value = result.data
    }
  } catch (error) {
    console.error('加载统计数据失败:', error)
  }
}

// 加载测试结果分布
const loadTestResultChart = async () => {
  try {
    const result = await dashboardAPI.getTestResultStats()
    console.log('[Dashboard] 测试结果数据:', result)
    
    if (result.success && testResultChartRef.value) {
      // 确保容器有高度
      if (!testResultChart) {
        testResultChart = echarts.init(testResultChartRef.value)
      }
      
      const data = result.data || { passed: 0, failed: 0, pending: 0 }
      
      testResultChart.setOption({
        tooltip: {
          trigger: 'item',
          formatter: '{b}: {c} ({d}%)'
        },
        legend: {
          bottom: '5%',
          left: 'center'
        },
        series: [{
          name: '测试结果',
          type: 'pie',
          radius: ['40%', '70%'],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 10,
            borderColor: '#fff',
            borderWidth: 2
          },
          label: {
            show: false,
            position: 'center'
          },
          emphasis: {
            label: {
              show: true,
              fontSize: 20,
              fontWeight: 'bold'
            }
          },
          labelLine: {
            show: false
          },
          data: [
            { value: data.passed, name: '通过', itemStyle: { color: '#18a058' } },
            { value: data.failed, name: '失败', itemStyle: { color: '#d03050' } },
            { value: data.pending, name: '待执行', itemStyle: { color: '#f0a020' } }
          ]
        }]
      })
      
      // 手动触发resize
      setTimeout(() => testResultChart?.resize(), 100)
    }
  } catch (error) {
    console.error('加载测试结果分布失败:', error)
  }
}

// 加载优先级分布
const loadPriorityChart = async () => {
  try {
    const result = await dashboardAPI.getPriorityStats()
    console.log('[Dashboard] 优先级数据:', result)
    
    if (result.success && priorityChartRef.value) {
      if (!priorityChart) {
        priorityChart = echarts.init(priorityChartRef.value)
      }
      
      const data = result.data || { '1': 0, '2': 0, '3': 0, '4': 0 }
      
      priorityChart.setOption({
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'shadow' }
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: ['1级', '2级', '3级', '4级']
        },
        yAxis: {
          type: 'value'
        },
        series: [{
          name: '用例数',
          type: 'bar',
          barWidth: '60%',
          data: [
            { value: data['1'], itemStyle: { color: '#d03050' } },
            { value: data['2'], itemStyle: { color: '#f0a020' } },
            { value: data['3'], itemStyle: { color: '#2080f0' } },
            { value: data['4'], itemStyle: { color: '#18a058' } }
          ]
        }]
      })
      
      setTimeout(() => priorityChart?.resize(), 100)
    }
  } catch (error) {
    console.error('加载优先级分布失败:', error)
  }
}

// 加载测试趋势
const loadTrendChart = async () => {
  try {
    const days = parseInt(trendRange.value)
    const result = await dashboardAPI.getTestTrend(days)
    console.log('[Dashboard] 趋势数据:', result)
    
    if (result.success && trendChartRef.value) {
      if (!trendChart) {
        trendChart = echarts.init(trendChartRef.value)
      }
      
      const data = result.data || { dates: [], tests: [], bugs: [], cases: [] }
      
      // 根据天数调整X轴标签间隔
      let axisLabelInterval = 0
      if (days === 365) {
        axisLabelInterval = 6  // 一年显示约52个点
      } else if (days === 90) {
        axisLabelInterval = 2  // 季度显示约30个点
      } else {
        axisLabelInterval = 2  // 月度显示约15个点
      }
      
      trendChart.setOption({
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'cross'
          }
        },
        legend: {
          data: ['测试执行', 'Bug发现', '用例新增'],
          top: 10
        },
        grid: {
          left: '50px',
          right: '20px',
          bottom: '60px',
          top: '50px'
        },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: data.dates,
          axisLabel: {
            rotate: 45,
            interval: axisLabelInterval,
            fontSize: 11
          }
        },
        yAxis: {
          type: 'value'
        },
        series: [
          {
            name: '测试执行',
            type: 'line',
            smooth: true,
            data: data.tests,
            itemStyle: { color: '#2080f0' },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(32, 128, 240, 0.3)' },
                { offset: 1, color: 'rgba(32, 128, 240, 0.1)' }
              ])
            }
          },
          {
            name: 'Bug发现',
            type: 'line',
            smooth: true,
            data: data.bugs,
            itemStyle: { color: '#d03050' }
          },
          {
            name: '用例新增',
            type: 'line',
            smooth: true,
            data: data.cases,
            itemStyle: { color: '#18a058' }
          }
        ]
      })
      
      setTimeout(() => trendChart?.resize(), 100)
    }
  } catch (error) {
    console.error('加载测试趋势失败:', error)
  }
}

// 加载模块分布
const loadModuleChart = async () => {
  try {
    const result = await dashboardAPI.getCaseTypeStats()
    console.log('[Dashboard] 用例类型数据:', result)
    
    if (result.success && moduleChartRef.value) {
      if (!moduleChart) {
        moduleChart = echarts.init(moduleChartRef.value)
      }
      
      const data = result.data || []
      
      moduleChart.setOption({
        tooltip: {
          trigger: 'item',
          formatter: '{b}: {c} ({d}%)'
        },
        legend: {
          type: 'scroll',
          orient: 'vertical',
          right: 10,
          top: 20,
          bottom: 20
        },
        series: [{
          name: '用例类型分布',
          type: 'pie',
          radius: '65%',
          center: ['40%', '50%'],
          data: data.map((item, index) => ({
            value: item.count,
            name: item.case_type || '未分类',
            itemStyle: {
              color: ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4'][index % 8]
            }
          })),
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)'
            }
          }
        }]
      })
      
      setTimeout(() => moduleChart?.resize(), 100)
    }
  } catch (error) {
    console.error('加载模块分布失败:', error)
  }
}

// 加载邮件统计
const loadEmailChart = async () => {
  try {
    const result = await dashboardAPI.getEmailStats()
    console.log('[Dashboard] 邮件数据:', result)
    
    if (result.success && emailChartRef.value) {
      if (!emailChart) {
        emailChart = echarts.init(emailChartRef.value)
      }
      
      const data = result.data || { success: 0, failed: 0, partial: 0 }
      
      emailChart.setOption({
        tooltip: {
          trigger: 'item'
        },
        legend: {
          bottom: '5%'
        },
        series: [{
          name: '邮件统计',
          type: 'pie',
          radius: ['30%', '60%'],
          roseType: 'area',
          data: [
            { value: data.success, name: '发送成功', itemStyle: { color: '#18a058' } },
            { value: data.failed, name: '发送失败', itemStyle: { color: '#d03050' } },
            { value: data.partial, name: '部分成功', itemStyle: { color: '#f0a020' } }
          ]
        }]
      })
      
      setTimeout(() => emailChart?.resize(), 100)
    }
  } catch (error) {
    console.error('加载邮件统计失败:', error)
  }
}

// 加载最近活动
const loadRecentActivities = async () => {
  try {
    const result = await dashboardAPI.getRecentActivities()
    if (result.success) {
      recentActivities.value = result.data.map(item => ({
        type: item.type === 'success' ? 'success' : item.type === 'error' ? 'error' : 'info',
        title: item.title,
        content: item.content,
        time: item.time
      }))
    }
  } catch (error) {
    console.error('加载最近活动失败:', error)
  }
}

// 窗口大小改变时重绘图表
const handleResize = () => {
  testResultChart?.resize()
  priorityChart?.resize()
  trendChart?.resize()
  moduleChart?.resize()
  emailChart?.resize()
}

onMounted(async () => {
  console.log('[Dashboard] 开始加载数据...')
  
  await loadStats()
  
  // 等待DOM渲染完成
  await new Promise(resolve => setTimeout(resolve, 200))
  
  await Promise.all([
    loadTestResultChart(),
    loadPriorityChart(),
    loadTrendChart(),
    loadModuleChart(),
    loadEmailChart(),
    loadRecentActivities()
  ])
  
  console.log('[Dashboard] 数据加载完成')
  
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  testResultChart?.dispose()
  priorityChart?.dispose()
  trendChart?.dispose()
  moduleChart?.dispose()
  emailChart?.dispose()
})
</script>

<style scoped>
.dashboard-container {
  padding: 20px;
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 20px;
  border-radius: 12px;
  background: white;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  transition: transform 0.3s, box-shadow 0.3s;
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
}

.stat-icon {
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  font-size: 24px;
  margin-right: 16px;
}

.stat-card.test-cases .stat-icon {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.stat-card.test-reports .stat-icon {
  background: linear-gradient(135deg, #2080f0 0%, #18a058 100%);
  color: white;
}

.stat-card.bugs .stat-icon {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  color: white;
}

.stat-card.emails .stat-icon {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: white;
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #333;
}

.stat-label {
  font-size: 14px;
  color: #666;
  margin-top: 4px;
}

.charts-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  margin-bottom: 20px;
}

.chart-card {
  border-radius: 12px;
}

.chart-card.wide {
  grid-column: span 2;
}

.chart-container {
  height: 300px;
  min-height: 300px;
  width: 100%;
}

.recent-activity {
  border-radius: 12px;
}

@media (max-width: 1200px) {
  .stats-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .stats-cards {
    grid-template-columns: 1fr;
  }
  
  .charts-row {
    grid-template-columns: 1fr;
  }
  
  .chart-card.wide {
    grid-column: span 1;
  }
}
</style>
