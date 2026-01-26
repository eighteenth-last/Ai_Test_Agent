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
from Bug_Analysis.router import router as bug_router
from Model_manage.router import router as model_router
from Contact_manage.router import router as contact_router
from Email_manage.router import router as email_router
from Dashboard.router import router as dashboard_router


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
cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:5175').split(',')
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
app.include_router(bug_router)
app.include_router(model_router)
app.include_router(contact_router)
app.include_router(email_router)
app.include_router(dashboard_router)



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
    
    # 检查并显示当前使用的模型配置
    print("\n" + "="*80)
    print("🤖 LLM 模型配置检查")
    print("="*80)
    try:
        from Model_manage.config_manager import get_active_llm_config
        config = get_active_llm_config()
        print(f"  ✓ 使用数据库模型配置")
        print(f"  ✓ 当前激活模型: {config['model_name']}")
        print(f"  ✓ 供应商: {config.get('provider', 'N/A')}")
        print(f"  ✓ Base URL: {config.get('base_url', 'N/A')}")
    except Exception as e:
        print(f"  ⚠️ 无法获取数据库模型配置: {e}")
        print(f"  ⚠️ 将回退到环境变量配置")
        print(f"  ⚠️ 请在模型管理页面添加并激活模型")
    
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