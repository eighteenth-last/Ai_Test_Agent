"""
一键测试 + Skills 管理 - API 路由
"""
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, Body, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database.connection import get_db, get_default_project
from OneClick_Test.service import OneClickService
from OneClick_Test.skill_manager import SkillManager
from OneClick_Test.session import SessionManager

router = APIRouter(prefix="/api", tags=["一键测试 & Skills"])


# ============ 请求模型 ============

class StartSessionRequest(BaseModel):
    user_input: str
    skill_ids: Optional[List[int]] = None

class ConfirmRequest(BaseModel):
    session_id: int
    confirmed_cases: Optional[List[dict]] = None

class ConfirmTreeRequest(BaseModel):
    """任务树确认请求 - 支持节点级勾选"""
    session_id: int
    # { node_id: True/False }  L2/L3 节点均支持
    # 传 null 或 {} 表示全选
    selections: Optional[Dict[str, bool]] = None

class InstallSkillRequest(BaseModel):
    slug: str

class ToggleSkillRequest(BaseModel):
    is_active: bool

class TestEnvRequest(BaseModel):
    name: str
    base_url: str
    login_url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    extra_credentials: Optional[dict] = None
    description: Optional[str] = None
    is_default: Optional[int] = 0


# ============ 一键测试 API ============

@router.post("/oneclick/start")
async def start_oneclick(req: StartSessionRequest, db: Session = Depends(get_db)):
    """启动一键测试会话"""
    # 获取默认项目
    project = get_default_project(db)
    if not project:
        return {"success": False, "message": "没有可用的项目，请先创建并启用一个项目"}
    
    result = await OneClickService.start_session(db, req.user_input, req.skill_ids, project.id)
    return result


@router.get("/oneclick/session/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db)):
    """获取会话详情"""
    from database.connection import OneclickSession, get_active_project_by_id
    
    detail = OneClickService.get_session_detail(db, session_id)
    if not detail:
        return {"success": False, "message": "会话不存在"}
    
    # 验证会话所属项目是否启用
    session = db.query(OneclickSession).filter(OneclickSession.id == session_id).first()
    if session and session.project_id:
        project = get_active_project_by_id(db, session.project_id)
        if not project:
            return {"success": False, "message": "会话所属项目未启用"}
    
    return {"success": True, "data": detail}


@router.post("/oneclick/confirm")
async def confirm_execute(req: ConfirmRequest, db: Session = Depends(get_db)):
    """确认并执行测试（传统扁平模式）"""
    from database.connection import OneclickSession, get_active_project_by_id
    
    # 验证会话所属项目是否启用
    session = db.query(OneclickSession).filter(OneclickSession.id == req.session_id).first()
    if not session:
        return {"success": False, "message": "会话不存在"}
    
    if session.project_id:
        project = get_active_project_by_id(db, session.project_id)
        if not project:
            return {"success": False, "message": "会话所属项目未启用"}
    
    result = await OneClickService.confirm_and_execute(
        db, req.session_id, req.confirmed_cases
    )
    return result


@router.post("/oneclick/confirm-tree")
async def confirm_tree_execute(req: ConfirmTreeRequest, db: Session = Depends(get_db)):
    """
    任务树确认并执行

    支持 L2 模块级勾选和 L3 用例级勾选。
    selections 为空时全部确认执行。
    """
    from database.connection import OneclickSession, get_active_project_by_id
    
    # 验证会话所属项目是否启用
    session = db.query(OneclickSession).filter(OneclickSession.id == req.session_id).first()
    if not session:
        return {"success": False, "message": "会话不存在"}
    
    if session.project_id:
        project = get_active_project_by_id(db, session.project_id)
        if not project:
            return {"success": False, "message": "会话所属项目未启用"}
    
    result = await OneClickService.confirm_task_tree(
        db, req.session_id, req.selections or {}
    )
    return result


@router.post("/oneclick/stop")
async def stop_session(session_id: int = Body(..., embed=True), db: Session = Depends(get_db)):
    """停止会话"""
    from database.connection import OneclickSession, get_active_project_by_id
    
    # 验证会话所属项目是否启用
    session = db.query(OneclickSession).filter(OneclickSession.id == session_id).first()
    if not session:
        return {"success": False, "message": "会话不存在"}
    
    if session.project_id:
        project = get_active_project_by_id(db, session.project_id)
        if not project:
            return {"success": False, "message": "会话所属项目未启用"}
    
    return await OneClickService.stop_session(db, session_id)


@router.get("/oneclick/history")
def get_history(page: int = 1, page_size: int = 20, project_id: int = None, db: Session = Depends(get_db)):
    """获取历史会话列表"""
    from database.connection import get_active_project_by_id
    
    # 如果未指定项目，使用默认项目
    if project_id is None:
        project = get_default_project(db)
        if not project:
            # 没有启用的项目，返回空列表
            return {"success": True, "data": {"items": [], "total": 0, "page": page, "page_size": page_size}}
        project_id = project.id
    else:
        # 验证指定的项目是否启用（不报错，只是过滤）
        project = get_active_project_by_id(db, project_id)
        if not project:
            # 项目未启用，返回空列表
            return {"success": True, "data": {"items": [], "total": 0, "page": page, "page_size": page_size}}
    
    data = SessionManager.list_sessions(db, page, page_size, project_id)
    return {"success": True, "data": data}


# ============ Skills 管理 API ============

@router.get("/skills/list")
def list_skills(category: str = None, db: Session = Depends(get_db)):
    """获取已安装的 Skills"""
    skills = SkillManager.list_skills(db, category)
    return {"success": True, "data": skills}


@router.post("/skills/install")
async def install_skill(req: InstallSkillRequest, db: Session = Depends(get_db)):
    """从 GitHub 安装 Skill（需要网络）"""
    result = await SkillManager.install_skill(db, req.slug)
    return result


@router.post("/skills/upload")
async def upload_skill(
    file: UploadFile = File(...),
    skill_name: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db)
):
    """手动上传 .md 文件安装 Skill（无需网络）"""
    if not file.filename.endswith(".md"):
        return {"success": False, "message": "仅支持 .md 文件"}
    content = await file.read()
    return SkillManager.install_skill_from_file(db, file.filename, content, skill_name, description)


@router.delete("/skills/{skill_id}")
def uninstall_skill(skill_id: int, db: Session = Depends(get_db)):
    """卸载 Skill"""
    return SkillManager.uninstall_skill(db, skill_id)


@router.get("/skills/{skill_id}/detail")
def get_skill_detail(skill_id: int, db: Session = Depends(get_db)):
    """获取 Skill 详情"""
    detail = SkillManager.get_skill_detail(db, skill_id)
    if not detail:
        return {"success": False, "message": "Skill 不存在"}
    return {"success": True, "data": detail}


@router.put("/skills/{skill_id}/toggle")
def toggle_skill(skill_id: int, req: ToggleSkillRequest, db: Session = Depends(get_db)):
    """启用/禁用 Skill"""
    return SkillManager.toggle_skill(db, skill_id, req.is_active)


@router.get("/skills/search")
async def search_skills(q: str = ""):
    """搜索 skills.sh 上的 Skills"""
    if not q:
        return {"success": False, "message": "请输入搜索关键词"}
    return await SkillManager.search_skills(q)


# ============ 测试环境管理 API ============

@router.get("/test-env/list")
def list_test_envs(db: Session = Depends(get_db)):
    """获取所有测试环境配置"""
    from database.connection import TestEnvironment
    envs = db.query(TestEnvironment).order_by(
        TestEnvironment.is_default.desc(),
        TestEnvironment.created_at.desc()
    ).all()
    return {
        "success": True,
        "data": [
            {
                "id": e.id,
                "name": e.name,
                "base_url": e.base_url,
                "login_url": e.login_url,
                "username": e.username,
                "password": e.password,
                "extra_credentials": e.extra_credentials,
                "description": e.description,
                "is_default": e.is_default,
                "is_active": e.is_active,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in envs
        ]
    }


@router.post("/test-env/create")
def create_test_env(req: TestEnvRequest, db: Session = Depends(get_db)):
    """创建测试环境"""
    from database.connection import TestEnvironment

    # 如果设为默认，先取消其他默认
    if req.is_default:
        db.query(TestEnvironment).filter(
            TestEnvironment.is_default == 1
        ).update({"is_default": 0})

    env = TestEnvironment(
        name=req.name,
        base_url=req.base_url,
        login_url=req.login_url,
        username=req.username,
        password=req.password,
        extra_credentials=req.extra_credentials,
        description=req.description,
        is_default=req.is_default or 0,
    )
    db.add(env)
    db.commit()
    db.refresh(env)
    return {"success": True, "data": {"id": env.id}, "message": "创建成功"}


@router.put("/test-env/{env_id}")
def update_test_env(env_id: int, req: TestEnvRequest, db: Session = Depends(get_db)):
    """更新测试环境"""
    from database.connection import TestEnvironment

    env = db.query(TestEnvironment).filter(TestEnvironment.id == env_id).first()
    if not env:
        return {"success": False, "message": "环境不存在"}

    # 如果设为默认，先取消其他默认
    if req.is_default and not env.is_default:
        db.query(TestEnvironment).filter(
            TestEnvironment.is_default == 1
        ).update({"is_default": 0})

    env.name = req.name
    env.base_url = req.base_url
    env.login_url = req.login_url
    env.username = req.username
    env.password = req.password
    env.extra_credentials = req.extra_credentials
    env.description = req.description
    env.is_default = req.is_default or 0
    db.commit()
    return {"success": True, "message": "更新成功"}


@router.delete("/test-env/{env_id}")
def delete_test_env(env_id: int, db: Session = Depends(get_db)):
    """删除测试环境"""
    from database.connection import TestEnvironment

    env = db.query(TestEnvironment).filter(TestEnvironment.id == env_id).first()
    if not env:
        return {"success": False, "message": "环境不存在"}
    db.delete(env)
    db.commit()
    return {"success": True, "message": "删除成功"}


@router.put("/test-env/{env_id}/set-default")
def set_default_env(env_id: int, db: Session = Depends(get_db)):
    """设置默认测试环境"""
    from database.connection import TestEnvironment

    env = db.query(TestEnvironment).filter(TestEnvironment.id == env_id).first()
    if not env:
        return {"success": False, "message": "环境不存在"}

    # 取消所有默认
    db.query(TestEnvironment).filter(
        TestEnvironment.is_default == 1
    ).update({"is_default": 0})

    env.is_default = 1
    db.commit()
    return {"success": True, "message": "已设为默认"}
