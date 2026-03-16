<template>
  <div class="p-6">
    <n-card title="ONES用例导入" class="shadow-sm">
      <n-alert type="warning" class="mb-4">
        <template #icon>
          <i class="fas fa-exclamation-triangle"></i>
        </template>
        请先在"ONES配置"中完成系统连接配置
      </n-alert>
      
      <n-empty
        description="用例导入功能开发中..."
        class="py-12"
      >
        <template #icon>
          <i class="fas fa-file-import text-4xl text-gray-400"></i>
        </template>
        <template #extra>
          <n-button type="primary" disabled>
            <template #icon>
              <i class="fas fa-download"></i>
            </template>
            导入用例
          </n-button>
        </template>
      </n-empty>
    </n-card>
  </div>
</template>

<script setup>
import { NCard, NAlert, NEmpty, NButton } from 'naive-ui'
</script>
