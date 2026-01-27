from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List
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


class ExecuteBatchBrowserUseRequest(BaseModel):
    """Browser-Use 批量执行请求参数"""
    test_case_ids: List[int]
    headless: bool = True
    max_steps: int = 50
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


@router.post("/execute-batch-browser-use")
async def execute_batch_with_browser_use(
    request: ExecuteBatchBrowserUseRequest,
    db: Session = Depends(get_db)
):
    """
    批量执行多条测试用例（智能合并步骤）🤖
    
    这是AI驱动的批量测试执行方式：
    - LLM 分析多条用例，找出共同步骤
    - 智能合并避免重复操作（如多次登录）
    - 按优化后的流程连续执行
    
    **适用场景**：
    - 多条用例有共同前置步骤（如都需要先登录）
    - 批量验证同一模块的多个功能
    - 回归测试套件执行
    
    **参数说明**：
    - test_case_ids: 测试用例 ID 列表
    - headless: 是否无头模式
    - max_steps: 最大执行步数（建议设置较大值）
    - use_vision: 是否启用视觉能力
    
    **返回**：
    - 合并后的执行步骤
    - 每条用例的执行结果
    - 完整的交互历史
    """
    result = await BrowserUseService.execute_batch_test_cases(
        test_case_ids=request.test_case_ids,
        db=db,
        headless=request.headless,
        max_steps=request.max_steps,
        use_vision=request.use_vision
    )
    
    if not result.get('success'):
        raise HTTPException(status_code=500, detail=result.get('message'))
    
    return result


@router.post("/pause-task/{task_id}")
async def pause_task(task_id: int):
    """
    暂停正在执行的测试任务
    
    **参数**：
    - task_id: 任务ID（通常是测试用例ID）
    
    **返回**：
    - 暂停操作的结果
    """
    from Build_test_code.task_manager import get_task_manager
    
    task_manager = get_task_manager()
    success = task_manager.pause_task(task_id)
    
    if success:
        return {
            "success": True,
            "message": f"任务 {task_id} 已暂停"
        }
    else:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")


@router.post("/resume-task/{task_id}")
async def resume_task(task_id: int):
    """
    恢复已暂停的测试任务
    
    **参数**：
    - task_id: 任务ID（通常是测试用例ID）
    
    **返回**：
    - 恢复操作的结果
    """
    from Build_test_code.task_manager import get_task_manager
    
    task_manager = get_task_manager()
    success = task_manager.resume_task(task_id)
    
    if success:
        return {
            "success": True,
            "message": f"任务 {task_id} 已恢复"
        }
    else:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")


@router.post("/stop-task/{task_id}")
async def stop_task(task_id: int):
    """
    停止正在执行的测试任务
    
    **参数**：
    - task_id: 任务ID（通常是测试用例ID）
    
    **返回**：
    - 停止操作的结果
    """
    from Build_test_code.task_manager import get_task_manager
    
    task_manager = get_task_manager()
    success = task_manager.stop_task(task_id)
    
    if success:
        return {
            "success": True,
            "message": f"任务 {task_id} 已停止"
        }
    else:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")


@router.get("/task-status/{task_id}")
async def get_task_status(task_id: int):
    """
    获取任务状态
    
    **参数**：
    - task_id: 任务ID
    
    **返回**：
    - 任务的当前状态信息
    """
    from Build_test_code.task_manager import get_task_manager
    
    task_manager = get_task_manager()
    status = task_manager.get_task_status(task_id)
    
    if status:
        return {
            "success": True,
            "data": status
        }
    else:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")