"""
项目管理 API 路由

提供项目的 CRUD 操作和默认项目设置

作者: 程序员Eighteen
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from database.connection import get_db, Project, get_default_project

router = APIRouter(
    prefix="/api/projects",
    tags=["项目管理"]
)


class ProjectCreate(BaseModel):
    """创建项目请求"""
    name: str
    code: str
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    """更新项目请求"""
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[int] = None


class ProjectResponse(BaseModel):
    """项目响应"""
    id: int
    name: str
    code: str
    description: Optional[str]
    is_default: int
    is_active: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get("/list")
def list_projects(
    is_active: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """获取项目列表"""
    query = db.query(Project)
    
    if is_active is not None:
        query = query.filter(Project.is_active == is_active)
    
    projects = query.order_by(Project.is_default.desc(), Project.id.asc()).all()
    
    return {
        "success": True,
        "data": [
            {
                "id": p.id,
                "name": p.name,
                "code": p.code,
                "description": p.description,
                "is_default": p.is_default,
                "is_active": p.is_active,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None
            }
            for p in projects
        ]
    }


@router.get("/default")
def get_default(db: Session = Depends(get_db)):
    """获取默认项目"""
    project = get_default_project(db)
    
    return {
        "success": True,
        "data": {
            "id": project.id,
            "name": project.name,
            "code": project.code,
            "description": project.description,
            "is_default": project.is_default,
            "is_active": project.is_active
        }
    }


@router.get("/{project_id}")
def get_project(
    project_id: int,
    db: Session = Depends(get_db)
):
    """获取项目详情"""
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    return {
        "success": True,
        "data": {
            "id": project.id,
            "name": project.name,
            "code": project.code,
            "description": project.description,
            "is_default": project.is_default,
            "is_active": project.is_active,
            "created_at": project.created_at.isoformat() if project.created_at else None,
            "updated_at": project.updated_at.isoformat() if project.updated_at else None
        }
    }


@router.post("/create")
def create_project(
    request: ProjectCreate,
    db: Session = Depends(get_db)
):
    """创建项目"""
    # 检查项目名称是否已存在
    existing_name = db.query(Project).filter(Project.name == request.name).first()
    if existing_name:
        raise HTTPException(status_code=400, detail="项目名称已存在")
    
    # 检查项目代码是否已存在
    existing_code = db.query(Project).filter(Project.code == request.code).first()
    if existing_code:
        raise HTTPException(status_code=400, detail="项目代码已存在")
    
    # 创建项目
    project = Project(
        name=request.name,
        code=request.code,
        description=request.description,
        is_default=0,
        is_active=1
    )
    
    db.add(project)
    db.commit()
    db.refresh(project)
    
    return {
        "success": True,
        "message": "项目创建成功",
        "data": {
            "id": project.id,
            "name": project.name,
            "code": project.code
        }
    }


@router.put("/{project_id}")
def update_project(
    project_id: int,
    request: ProjectUpdate,
    db: Session = Depends(get_db)
):
    """更新项目"""
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 更新字段
    if request.name is not None:
        # 检查名称是否与其他项目重复
        existing = db.query(Project).filter(
            Project.name == request.name,
            Project.id != project_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="项目名称已存在")
        project.name = request.name
    
    if request.code is not None:
        # 检查代码是否与其他项目重复
        existing = db.query(Project).filter(
            Project.code == request.code,
            Project.id != project_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="项目代码已存在")
        project.code = request.code
    
    if request.description is not None:
        project.description = request.description
    
    if request.is_active is not None:
        project.is_active = request.is_active
    
    project.updated_at = datetime.now()
    
    db.commit()
    db.refresh(project)
    
    return {
        "success": True,
        "message": "项目更新成功",
        "data": {
            "id": project.id,
            "name": project.name,
            "code": project.code
        }
    }


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db)
):
    """删除项目"""
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 不允许删除默认项目
    if project.is_default == 1:
        raise HTTPException(status_code=400, detail="不能删除默认项目，请先设置其他项目为默认")
    
    # 检查是否有关联数据
    from database.connection import ExecutionCase, ApiSpec, OneclickSession
    
    has_cases = db.query(ExecutionCase).filter(ExecutionCase.project_id == project_id).count() > 0
    has_specs = db.query(ApiSpec).filter(ApiSpec.project_id == project_id).count() > 0
    has_sessions = db.query(OneclickSession).filter(OneclickSession.project_id == project_id).count() > 0
    
    if has_cases or has_specs or has_sessions:
        raise HTTPException(
            status_code=400,
            detail="该项目下有关联数据，无法删除。请先清理或转移数据。"
        )
    
    db.delete(project)
    db.commit()
    
    return {
        "success": True,
        "message": "项目删除成功"
    }


@router.post("/{project_id}/set-default")
def set_default_project(
    project_id: int,
    db: Session = Depends(get_db)
):
    """设置默认项目"""
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    if project.is_active == 0:
        raise HTTPException(status_code=400, detail="不能将未启用的项目设为默认")
    
    # 取消其他项目的默认状态
    db.query(Project).update({Project.is_default: 0})
    
    # 设置当前项目为默认
    project.is_default = 1
    project.updated_at = datetime.now()
    
    db.commit()
    
    return {
        "success": True,
        "message": f"已将 '{project.name}' 设为默认项目"
    }


@router.get("/{project_id}/stats")
def get_project_stats(
    project_id: int,
    db: Session = Depends(get_db)
):
    """获取项目统计信息"""
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    from database.connection import (
        ExecutionCase, ApiSpec, ApiSpecVersion, OneclickSession,
        TestRecord, TestReport, BugReport, TestEnvironment
    )
    
    # 统计各类数据
    stats = {
        "test_cases": db.query(ExecutionCase).filter(ExecutionCase.project_id == project_id).count(),
        "api_specs": db.query(ApiSpec).filter(ApiSpec.project_id == project_id).count(),
        "api_versions": db.query(ApiSpecVersion).filter(ApiSpecVersion.project_id == project_id).count(),
        "oneclick_sessions": db.query(OneclickSession).filter(OneclickSession.project_id == project_id).count(),
        "test_records": db.query(TestRecord).filter(TestRecord.project_id == project_id).count(),
        "test_reports": db.query(TestReport).filter(TestReport.project_id == project_id).count(),
        "bug_reports": db.query(BugReport).filter(BugReport.project_id == project_id).count(),
        "test_environments": db.query(TestEnvironment).filter(TestEnvironment.project_id == project_id).count(),
    }
    
    return {
        "success": True,
        "data": {
            "project": {
                "id": project.id,
                "name": project.name,
                "code": project.code
            },
            "stats": stats
        }
    }
