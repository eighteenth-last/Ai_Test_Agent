/**
 * 项目管理平台 API
 */
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001'

/**
 * 获取系统支持的所有项目管理平台列表
 */
export const getSupportedPlatforms = async () => {
  const response = await axios.get(`${API_BASE}/api/project-platform/platforms/supported`)
  return response.data
}

/**
 * 获取所有项目管理平台配置列表
 */
export const listPlatforms = async () => {
  const response = await axios.get(`${API_BASE}/api/project-platform/list`)
  return response.data
}

/**
 * 获取已激活的项目管理平台列表（用于动态菜单）
 */
export const listActivePlatforms = async () => {
  const response = await axios.get(`${API_BASE}/api/project-platform/active`)
  return response.data
}

/**
 * 获取指定平台配置
 */
export const getPlatform = async (platformId) => {
  const response = await axios.get(`${API_BASE}/api/project-platform/${platformId}`)
  return response.data
}

/**
 * 创建新的平台配置
 */
export const createPlatform = async (data) => {
  const response = await axios.post(`${API_BASE}/api/project-platform`, data)
  return response.data
}

/**
 * 更新平台配置
 */
export const updatePlatform = async (configId, data) => {
  const response = await axios.put(`${API_BASE}/api/project-platform/${configId}`, data)
  return response.data
}

/**
 * 删除平台配置
 */
export const deletePlatform = async (configId) => {
  const response = await axios.delete(`${API_BASE}/api/project-platform/${configId}`)
  return response.data
}

/**
 * 激活指定平台配置
 */
export const activatePlatform = async (configId) => {
  const response = await axios.post(`${API_BASE}/api/project-platform/${configId}/activate`)
  return response.data
}

/**
 * 取消激活指定平台配置
 */
export const deactivatePlatform = async (configId) => {
  const response = await axios.post(`${API_BASE}/api/project-platform/${configId}/deactivate`)
  return response.data
}

/**
 * 启用指定平台配置
 */
export const enablePlatform = async (configId) => {
  const response = await axios.post(`${API_BASE}/api/project-platform/${configId}/enable`)
  return response.data
}

/**
 * 禁用指定平台配置
 */
export const disablePlatform = async (configId) => {
  const response = await axios.post(`${API_BASE}/api/project-platform/${configId}/disable`)
  return response.data
}

/**
 * 测试平台连接是否可达
 */
export const testConnection = async (data) => {
  const response = await axios.post(`${API_BASE}/api/project-platform/test-connection`, data)
  return response.data
}
