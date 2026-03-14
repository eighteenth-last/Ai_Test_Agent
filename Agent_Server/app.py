"""
AI 自动化测试平台 - 后端服务入口

支持用户自定义大模型执行项目测试

作者: 程序员Eighteen
"""
import os
import sys
import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Windows 事件循环修复
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# 导入配置和模块
from Agent_Server.Basic.config import config
from Agent_Server.Basic.startup import lifespan
from Agent_Server.Basic.routes import register_routes
from Agent_Server.Basic.endpoints import register_basic_endpoints


# 创建 FastAPI 应用
app = FastAPI(
    title=config.APP_TITLE,
    description=config.APP_DESCRIPTION,
    version=config.APP_VERSION,
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由和端点
register_routes(app)
register_basic_endpoints(app)


if __name__ == "__main__":
    # Windows 额外处理
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    uvicorn.run(
        "app:app",
        host=config.HOST,
        port=config.PORT,
        reload=False
    )
