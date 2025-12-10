from fastapi import APIRouter, Depends, HTTPException
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


@router.get("/list")
async def get_reports(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get test report list
    """
    reports = TestReportService.get_reports(db=db, limit=limit, offset=offset)
    return {
        "success": True,
        "data": reports,
        "total": len(reports)
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