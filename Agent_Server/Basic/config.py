"""
应用配置模块
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))


class Config:
    """应用配置类"""
    
    # 服务器配置
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 8001))
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    
    # CORS 配置
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:5175').split(',')
    
    # 应用信息
    APP_TITLE = "AI Test Agent API"
    APP_VERSION = "2.0.0"
    APP_DESCRIPTION = """
    AI 自动化测试平台 API
    
    ## 功能特性
    
    - 🤖 **智能测试用例生成** - 基于需求自动生成测试用例
    - 🌐 **Browser-Use 自动化执行** - 使用 AI Agent 执行浏览器测试
    - 📊 **测试报告生成** - 自动生成详细的测试报告
    - 🐛 **Bug 智能分析** - 自动分析测试失败原因
    - 🔧 **多模型支持** - 支持 OpenAI、DeepSeek、Claude 等多种大模型
    
    ## 使用流程
    
    1. 在模型管理中配置并激活 LLM 模型
    2. 创建或导入测试用例
    3. 执行测试（单条或批量）
    4. 查看测试报告和 Bug 分析
    """


config = Config()
