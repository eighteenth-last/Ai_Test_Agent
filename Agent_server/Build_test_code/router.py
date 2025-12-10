from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_db
from Build_test_code.browser_use_service import BrowserUseService

router = APIRouter(
    prefix="/api/test-code",
    tags=["Test Code"]
)


class ExecuteBrowserUseRequest(BaseModel):
    """Browser-Use 执行请求参数"""
    test_case_id: int
    headless: bool = True
    max_steps: int = 20
    use_vision: bool = False


@router.post("/execute-browser-use")
async def execute_with_browser_use(
    request: ExecuteBrowserUseRequest,
    db: Session = Depends(get_db)
):
    """
    使用 Browser-Use 执行测试（AI 智能操作）🤖
    
    这是AI驱动的测试执行方式，无需生成代码：
    
    **特点**：
    - LLM 实时观察页面状态
    - 动态决策每一步操作
    - 智能处理错误和意外情况
    - 自动适应页面变化
    
    **适用场景**：
    - 动态网页（React/Vue/Angular）
    - 页面结构经常变化
    - 需要处理弹窗等意外情况
    - 需要视觉验证（启用 use_vision）
    
    **参数说明**：
    - test_case_id: 测试用例 ID
    - headless: 是否无头模式（默认 True，生产环境推荐）
    - max_steps: 最大执行步数（默认 20，防止无限循环）
    - use_vision: 是否启用视觉能力（需要支持视觉的 LLM）
    
    **返回**：
    - 执行结果和详细的交互历史
    - 每一步的 LLM 思考过程
    - 完整的页面URL变化轨迹
    """
    result = await BrowserUseService.execute_test_with_browser_use(
        test_case_id=request.test_case_id,
        db=db,
        headless=request.headless,
        max_steps=request.max_steps,
        use_vision=request.use_vision
    )
    
    if not result.get('success'):
        raise HTTPException(status_code=500, detail=result.get('message'))
    
    return result