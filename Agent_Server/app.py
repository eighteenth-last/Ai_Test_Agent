"""
AI 自动化测试平台 - 后端服务入口

支持用户自定义大模型执行项目测试

作者: Ai_Test_Agent Team
"""
import os
import sys
import asyncio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Windows 事件循环修复
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# 加载环境变量
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# 导入数据库初始化
from database.connection import init_db

# 导入路由
from Build_Use_case.router import router as test_cases_router
from Execute_test.router import router as execute_router
from Build_Report.router import router as report_router
from Bug_Analysis.router import router as bug_router
from Model_manage.router import router as model_router
from Email_manage.router import router as email_router
from Contact_manage.router import router as contact_router
from Dashboard.router import router as dashboard_router
from Api_Spec.router import router as spec_router
from Api_Test.router import router as api_test_router
from OneClick_Test.router import router as oneclick_router
from Security_Test.router import router as security_router
from Page_Knowledge.router import router as knowledge_router
from Zentao_manage.router import router as zentao_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    loop = asyncio.get_running_loop()
    print(f"\n[Debug] 当前事件循环: {type(loop)}")
    
    if sys.platform == 'win32' and not isinstance(loop, asyncio.ProactorEventLoop):
        print("[Warning] Windows 未使用 ProactorEventLoop!")
    
    print("\n" + "=" * 80)
    print("🗄️  初始化数据库...")
    init_db()
    
    print("\n" + "=" * 80)
    print("🤖 LLM 模型配置检查")
    print("=" * 80)

    try:
        from llm import get_active_llm_config
        config = get_active_llm_config()
        print(f"  ✓ 使用数据库模型配置")
        print(f"  ✓ 当前激活模型: {config['model_name']}")
        print(f"  ✓ 供应商: {config.get('provider', 'N/A')}")
        print(f"  ✓ Base URL: {config.get('base_url', 'N/A')}")
    except Exception as e:
        print(f"  ⚠️ 无法获取数据库模型配置: {e}")
        print(f"  ⚠️ 请在模型管理页面添加并激活模型")
    
    print("\n" + "=" * 80)
    print("📚 API 文档访问地址：")
    print("=" * 80)
    print(f"  ✓ Swagger UI 文档: http://localhost:8001/docs")
    print(f"  ✓ ReDoc 文档:       http://localhost:8001/redoc")
    print(f"  ✓ OpenAPI JSON:    http://localhost:8001/openapi.json")
    print("=" * 80)
    
    print("\n💡 提示：")
    print("  - 系统支持多种大模型（OpenAI、DeepSeek、Claude 等）")
    print("  - 通过模型管理页面配置和切换模型")
    print("  - 使用 browser-use 执行自动化测试")
    print("=" * 80)
    
    print("\n🚀 AI 自动化测试平台 API 已成功启动！")
    print("=" * 80 + "\n")
    
    yield

    print("\n服务已安全关闭\n")

# 创建 FastAPI 应用
app = FastAPI(
    title="AI Test Agent API",
    description="""
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
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# CORS 配置
cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:5175').split(',')
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(test_cases_router)
app.include_router(execute_router)
app.include_router(report_router)
app.include_router(bug_router)
app.include_router(model_router)
app.include_router(email_router)
app.include_router(contact_router)
app.include_router(dashboard_router)
app.include_router(spec_router)
app.include_router(api_test_router)
app.include_router(oneclick_router)
app.include_router(security_router)
app.include_router(knowledge_router)
app.include_router(zentao_router)


# 自定义 ReDoc 端点
@app.get("/redoc", include_in_schema=False)
async def redoc_html() -> HTMLResponse:
    """ReDoc API 文档页面"""
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
    """API 根端点"""
    return {
        "message": "AI Test Agent API is running",
        "version": "2.0.0",
        "docs": "/docs",
        "features": [
            "Multi-LLM support (OpenAI, DeepSeek, Claude, etc.)",
            "Intelligent test case generation",
            "Browser-Use automated testing",
            "AI-powered bug analysis"
        ]
    }


@app.get("/health")
async def health_check():
    """健康检查端点"""
    try:
        from llm import get_active_llm_config
        config = get_active_llm_config()
        llm_status = "active"
        llm_model = config.get('model_name', 'unknown')
    except Exception:
        llm_status = "not_configured"
        llm_model = None
    
    return {
        "status": "healthy",
        "service": "AI Test Agent",
        "version": "2.0.0",
        "llm": {
            "status": llm_status,
            "model": llm_model
        }
    }


if __name__ == "__main__":
    # Windows 额外处理
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 8001))
    debug = os.getenv('DEBUG', 'True').lower() == 'true'
    
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=False
    )
