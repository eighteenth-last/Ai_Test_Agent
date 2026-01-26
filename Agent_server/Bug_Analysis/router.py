"""
Bug 管理 API 路由
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_db
from Bug_Analysis.service import BugAnalysisService

router = APIRouter(
    prefix="/api/bugs",
    tags=["Bug Management"]
)


@router.get("/list")
async def get_bugs(
    limit: int = Query(20, description="每页数量"),
    offset: int = Query(0, description="偏移量"),
    severity_level: Optional[str] = Query(None, description="严重程度筛选"),
    status: Optional[str] = Query(None, description="状态筛选"),
    db: Session = Depends(get_db)
):
    """
    获取 Bug 列表
    
    **筛选条件**：
    - severity_level: 一级/二级/三级/四级
    - status: 待处理/已确认/已修复/已关闭
    """
    result = BugAnalysisService.get_bugs(
        db=db,
        limit=limit,
        offset=offset,
        severity_level=severity_level,
        status=status
    )
    return result


@router.get("/{bug_id}")
async def get_bug_detail(
    bug_id: int,
    db: Session = Depends(get_db)
):
    """获取 Bug 详情"""
    result = BugAnalysisService.get_bug_by_id(db=db, bug_id=bug_id)
    
    if not result.get('success'):
        raise HTTPException(status_code=404, detail=result.get('message'))
    
    return result


@router.put("/{bug_id}/status")
async def update_bug_status(
    bug_id: int,
    status: str = Query(..., description="新状态：待处理/已确认/已修复/已关闭"),
    db: Session = Depends(get_db)
):
    """更新 Bug 状态"""
    result = BugAnalysisService.update_bug_status(db=db, bug_id=bug_id, status=status)
    
    if not result.get('success'):
        raise HTTPException(status_code=404, detail=result.get('message'))
    
    return result
