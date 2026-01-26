from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
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


class UpdateTestCaseRequest(BaseModel):
    module: str
    title: str
    precondition: Optional[str] = None
    steps: List[str]
    expected: str
    keywords: Optional[str] = None
    priority: str
    case_type: Optional[str] = None
    stage: Optional[str] = None


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
    module: str = None,
    search: str = None,
    priority: str = None,
    db: Session = Depends(get_db)
):
    """
    Get test case list with filters
    
    Args:
        limit: Number of records per page
        offset: Offset
        module: Filter by module name
        search: Search by case title
        priority: Filter by priority level
        db: Database session
    """
    result = TestCaseService.get_test_cases(
        db=db, 
        limit=limit, 
        offset=offset,
        module=module,
        search=search,
        priority=priority
    )
    return {
        "success": True,
        "data": result['data'],
        "total": result['total']
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


@router.put("/{case_id}")
async def update_test_case(
    case_id: int,
    request: UpdateTestCaseRequest,
    db: Session = Depends(get_db)
):
    """
    更新测试用例
    """
    result = TestCaseService.update_test_case(
        db=db,
        case_id=case_id,
        module=request.module,
        title=request.title,
        precondition=request.precondition,
        steps=request.steps,
        expected=request.expected,
        keywords=request.keywords,
        priority=request.priority,
        case_type=request.case_type,
        stage=request.stage
    )
    
    if not result.get('success'):
        raise HTTPException(status_code=404 if 'not found' in result.get('message', '').lower() else 500, 
                          detail=result.get('message'))
    
    return result


@router.post("/upload-file")
async def upload_file_and_generate(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    上传文件并生成测试用例
    
    支持的文件格式：
    - .md (Markdown)
    - .txt (纯文本)
    - .pdf (PDF文档)
    - .doc (Word 2003)
    - .docx (Word 2007+)
    
    文件内容将被解析为测试需求，然后自动生成测试用例
    """
    # 验证文件类型
    allowed_extensions = ['.md', '.txt', '.pdf', '.doc', '.docx']
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"不支持的文件格式。支持的格式：{', '.join(allowed_extensions)}"
        )
    
    # 验证文件大小（限制10MB）
    max_size = 10 * 1024 * 1024  # 10MB
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail="文件大小超过10MB限制")
    
    # 调用服务处理文件
    result = await TestCaseService.process_uploaded_file(
        filename=file.filename,
        content=content,
        db=db
    )
    
    if not result.get('success'):
        raise HTTPException(status_code=500, detail=result.get('message'))
    
    return result