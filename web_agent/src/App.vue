<template>
  <div id="app">
    <el-container style="min-height: 100vh">
      <el-header style="background: #545c64; color: #fff; line-height: 60px">
        <h2 style="margin: 0">AI 自动化测试平台</h2>
      </el-header>
      
      <el-container>
        <el-aside width="200px" style="background: #545c64">
          <el-menu
            :default-active="$route.path"
            router
            background-color="#545c64"
            text-color="#fff"
            active-text-color="#ffd04b"
          >
            <el-menu-item index="/">
              <el-icon><Document /></el-icon>
              <span>生成用例</span>
            </el-menu-item>
            <el-menu-item index="/execute-case">
              <el-icon><VideoPlay /></el-icon>
              <span>执行用例</span>
            </el-menu-item>
            <el-menu-item index="/test-report">
              <el-icon><DataAnalysis /></el-icon>
              <span>测试报告</span>
            </el-menu-item>
            <el-menu-item index="/bug-report">
              <el-icon><Warning /></el-icon>
              <span>错误集合</span>
            </el-menu-item>
          </el-menu>
        </el-aside>
        
        <el-main style="background: #f0f2f5">
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { Document, Edit, DataAnalysis, VideoPlay, Warning } from '@element-plus/icons-vue'
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: Arial, sans-serif;
}
</style>
