<template>
  <div class="p-6">
    <n-card title="8Manage PM配置" class="shadow-sm">
      <n-alert type="info" class="mb-4">
        <template #icon>
          <i class="fas fa-info-circle"></i>
        </template>
        8Manage PM 是一款企业级项目管理系统，提供项目计划、资源管理、成本控制等功能。
      </n-alert>
      
      <n-empty
        description="8Manage PM 集成功能开发中..."
        class="py-12"
      >
        <template #icon>
          <i class="fas fa-tools text-4xl text-gray-400"></i>
        </template>
        <template #extra>
          <n-space>
            <n-button type="primary" disabled>
              <template #icon>
                <i class="fas fa-plug"></i>
              </template>
              配置连接
            </n-button>
            <n-button disabled>
              <template #icon>
                <i class="fas fa-book"></i>
              </template>
              查看文档
            </n-button>
          </n-space>
        </template>
      </n-empty>
    </n-card>
  </div>
</template>

<script setup>
import { NCard, NAlert, NEmpty, NSpace, NButton } from 'naive-ui'
</script>
