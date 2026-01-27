from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_db
from Build_Report.service import TestReportService

router = APIRouter(
    prefix="/api/reports",
    tags=["Test Reports"]
)


class GenerateReportRequest(BaseModel):
    test_result_ids: List[int]
    format_type: str = "markdown"  # txt/markdown/html


class GenerateMixedReportRequest(BaseModel):
    """综合报告生成请求"""
    report_ids: List[int]  # 运行测试报告 ID 列表
    bug_report_ids: List[int] = []  # Bug 报告 ID 列表


class SendReportRequest(BaseModel):
    """发送报告请求"""
    report_content: dict  # 报告内容
    contact_ids: List[int]  # 联系人 ID 列表


@router.post("/generate")
async def generate_report(
    request: GenerateReportRequest,
    db: Session = Depends(get_db)
):
    """
    Generate test report based on test results
    """
    result = await TestReportService.generate_report(
        test_result_ids=request.test_result_ids,
        db=db,
        format_type=request.format_type
    )
    
    if not result.get('success'):
        raise HTTPException(status_code=500, detail=result.get('message'))
    
    return result


@router.post("/generate-mixed")
async def generate_mixed_report(
    request: GenerateMixedReportRequest,
    db: Session = Depends(get_db)
):
    """
    生成综合评估报告（基于 LLM 分析）
    """
    result = await TestReportService.generate_mixed_report(
        report_ids=request.report_ids,
        bug_report_ids=request.bug_report_ids,
        db=db
    )
    
    if not result.get('success'):
        raise HTTPException(status_code=500, detail=result.get('message'))
    
    return result


@router.post("/send-report")
async def send_report_to_contacts(
    request: SendReportRequest,
    db: Session = Depends(get_db)
):
    """
    发送综合评估报告给指定联系人
    """
    result = await TestReportService.send_report_to_contacts(
        report_content=request.report_content,
        contact_ids=request.contact_ids,
        db=db
    )
    
    if not result.get('success'):
        return {"code": 500, "message": result.get('message'), "data": None}
    
    return {"code": 200, "message": result.get('message'), "data": result.get('data', {})}


@router.get("/list")
async def get_reports(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get test report list with pagination
    """
    result = TestReportService.get_reports(db=db, limit=limit, offset=offset)
    return {
        "success": True,
        "data": result['data'],
        "total": result['total'],
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < result['total']
    }


@router.get("/{report_id}")
async def get_report_by_id(
    report_id: int,
    db: Session = Depends(get_db)
):
    """
    Get full test report details by ID
    """
    result = TestReportService.get_report_by_id(report_id=report_id, db=db)
    
    if not result.get('success'):
        raise HTTPException(status_code=404, detail=result.get('message'))
    
    return result


@router.get("/{report_id}/download")
async def download_report(
    report_id: int,
    db: Session = Depends(get_db)
):
    """
    下载测试报告文件
    
    支持下载 HTML、Markdown、TXT 格式的报告文件
    """
    result = TestReportService.get_report_by_id(report_id=report_id, db=db)
    
    if not result.get('success'):
        raise HTTPException(status_code=404, detail=result.get('message'))
    
    report_data = result.get('data')
    file_path = report_data.get('file_path')
    
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="报告文件不存在")
    
    # 获取文件扩展名
    format_type = report_data.get('format_type', 'html')
    filename = f"test_report_{report_id}.{format_type}"
    
    # 设置正确的 MIME 类型
    media_type_map = {
        'html': 'text/html',
        'markdown': 'text/markdown',
        'txt': 'text/plain'
    }
    media_type = media_type_map.get(format_type, 'application/octet-stream')
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
        }
    )