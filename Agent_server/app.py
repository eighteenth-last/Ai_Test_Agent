import os
import sys
import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Fix for Windows: Ensure ProactorEventLoop is used for subprocess support
# Must be set before any other asyncio usage or uvicorn execution
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

from database.connection import init_db
from Build_tests.router import router as test_cases_router
from Build_test_code.router import router as test_code_router
from Build_Report.router import router as report_router


# Create FastAPI application with custom docs
app = FastAPI(
    title="AI Test Agent API",
    description="AI-powered automated testing platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,  # 使用自定义 ReDoc 端点
    openapi_url="/openapi.json"
)

# CORS configuration
cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(',')
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(test_cases_router)
app.include_router(test_code_router)
app.include_router(report_router)



# 自定义 ReDoc 端点
@app.get("/redoc", include_in_schema=False)
async def redoc_html() -> HTMLResponse:
    """
    ReDoc API 文档页面
    使用 CDN 加载 ReDoc 最新版本
    """
    return HTMLResponse(
        content="""
        <!DOCTYPE html>
        <html>
            <head>
                <title>AI Test Agent - API 文档</title>
                <meta charset="utf-8"/>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
                <style>
                    body {
                        margin: 0;
                        padding: 0;
                    }
                </style>
            </head>
            <body>
                <redoc spec-url="/openapi.json"></redoc>
                <script src="https://cdn.jsdelivr.net/npm/redoc@latest/bundles/redoc.standalone.js"></script>
            </body>
        </html>
        """
    )


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "message": "AI Test Agent API is running",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "AI Test Agent"
    }


@app.on_event("startup")
async def startup_event():
    """启动事件处理器"""
    # Debug: Check Event Loop Type
    loop = asyncio.get_running_loop()
    print(f"\n[Debug] Current Event Loop: {type(loop)}")
    if sys.platform == 'win32' and not isinstance(loop, asyncio.ProactorEventLoop):
        print("[Warning] NOT using ProactorEventLoop on Windows! Subprocesses may fail.")

    print("\n" + "="*80)
    print("初始化数据库...")
    init_db()
    
    # 输出API文档信息
    print("\n" + "="*80)
    print("📚 API 文档访问地址：")
    print("="*80)
    print(f"  ✓ Swagger UI 文档: http://localhost:8000/docs")
    print(f"  ✓ ReDoc 文档:       http://localhost:8000/redoc")
    print(f"  ✓ OpenAPI JSON:    http://localhost:8000/openapi.json")
    print("="*80)
    print("\n💡 提示：")
    print("  - 浏览器控制台的 content.js 错误可以忽略（Chrome 扩展兼容性问题）")
    print("  - 如果 ReDoc 显示空白，请尝试刷新或清除浏览器缓存")
    print("="*80)
    
    print("\n🚀 AI 自动化测试平台 API 已成功启动！")
    print("="*80 + "\n")


if __name__ == "__main__":
    # Additional enforcement for Windows
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 8000))
    debug = os.getenv('DEBUG', 'True').lower() == 'true'
    
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=False
    )