"""
应用启动和生命周期管理模块
"""
import sys
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from database.connection import init_db


def print_startup_banner():
    """打印启动横幅"""
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    loop = asyncio.get_running_loop()
    print(f"\n[Debug] 当前事件循环: {type(loop)}")
    
    if sys.platform == 'win32' and not isinstance(loop, asyncio.ProactorEventLoop):
        print("[Warning] Windows 未使用 ProactorEventLoop!")
    
    # 启动时执行
    print_startup_banner()
    
    yield
    
    # 关闭时执行
    print("\n服务已安全关闭\n")
