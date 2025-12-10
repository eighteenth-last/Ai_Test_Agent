from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_db
from Build_tests.service import TestCaseService

router = APIRouter(
    prefix="/api/test-cases",
    tags=["Test Cases"]
)


class GenerateTestCaseRequest(BaseModel):
    requirement: str


class TestCaseResponse(BaseModel):
    id: int
    module: str
    title: str
    precondition: Optional[str]
    steps: List[str]
    expected: str
    keywords: Optional[str]
    priority: str
    case_type: Optional[str]
    stage: Optional[str]
    test_data: Optional[dict]
    created_at: Optional[str]


@router.post("/generate")
async def generate_test_cases(
    request: GenerateTestCaseRequest,
    db: Session = Depends(get_db)
):
    """
    Generate test cases based on requirements
    """
    result = await TestCaseService.generate_test_cases(
        requirement=request.requirement,
        db=db
    )
    
    if not result.get('success'):
        raise HTTPException(status_code=500, detail=result.get('message'))
    
    return result


@router.get("/list")
async def get_test_cases(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get test case list
    """
    cases = TestCaseService.get_test_cases(db=db, limit=limit, offset=offset)
    return {
        "success": True,
        "data": cases,
        "total": len(cases)
    }


@router.get("/{case_id}")
async def get_test_case(
    case_id: int,
    db: Session = Depends(get_db)
):
    """
    Get test case by ID
    """
    case = TestCaseService.get_test_case_by_id(db=db, case_id=case_id)
    
    if not case:
        raise HTTPException(status_code=404, detail="Test case not found")
    
    return {
        "success": True,
        "data": case
    }