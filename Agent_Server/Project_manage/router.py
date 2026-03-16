"""
项目管理平台统一配置 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
import logging

from database.connection import get_db
from Project_manage.service import ProjectPlatformService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/project-platform",
    tags=["项目管理平台"]
)


# =====================================================================
# Pydantic 请求模型
# =====================================================================

class PlatformConfigCreate(BaseModel):
    platform_id: str
    platform_name: str
    config_name: str
    base_url: str
    account: str
    password: str
    api_token: Optional[str] = None
    default_product_id: Optional[int] = None
    api_version: Optional[str] = "v2"
    extra_config: Optional[str] = None
    description: Optional[str] = None


class PlatformConfigUpdate(BaseModel):
    config_name: Optional[str] = None
    platform_name: Optional[str] = None
    base_url: Optional[str] = None
    account: Optional[str] = None
    password: Optional[str] = None
    api_token: Optional[str] = None
    default_product_id: Optional[int] = None
    api_version: Optional[str] = None
    extra_config: Optional[str] = None
    is_enabled: Optional[int] = None
    description: Optional[str] = None


# =====================================================================
# 配置管理接口
# =====================================================================

@router.get("/platforms/supported")
def get_supported_platforms():
    """获取系统支持的所有项目管理平台列表"""
    return {"success": True, "data": ProjectPlatformService.get_supported_platforms()}


@router.get("/list")
def list_platforms(db: Session = Depends(get_db)):
    """获取所有项目管理平台配置列表"""
    return {"success": True, "data": ProjectPlatformService.list_all(db)}


@router.get("/active")
def list_active_platforms(db: Session = Depends(get_db)):
    """获取已激活的项目管理平台列表（用于动态菜单）"""
    return {"success": True, "data": ProjectPlatformService.list_active(db)}


@router.get("/{platform_id}")
def get_platform(platform_id: str, db: Session = Depends(get_db)):
    """获取指定平台配置"""
    cfg = ProjectPlatformService.get_by_platform_id(db, platform_id)
    if not cfg:
        return {"success": True, "data": None, "message": "该平台尚未配置"}
    return {"success": True, "data": cfg}


@router.post("")
def create_platform(body: PlatformConfigCreate, db: Session = Depends(get_db)):
    """新增项目管理平台配置"""
    try:
        cfg = ProjectPlatformService.create(db, body.model_dump())
        return {"success": True, "data": cfg, "message": "平台配置创建成功"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{config_id}")
def update_platform(config_id: int, body: PlatformConfigUpdate, db: Session = Depends(get_db)):
    """更新项目管理平台配置"""
    try:
        data = body.model_dump(exclude_none=True)
        logger.info(f"[ProjectPlatform] 更新配置 ID={config_id}, 数据: {data}")
        cfg = ProjectPlatformService.update(db, config_id, data)
        return {"success": True, "data": cfg, "message": "平台配置更新成功"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{config_id}")
def delete_platform(config_id: int, db: Session = Depends(get_db)):
    """删除项目管理平台配置"""
    try:
        ProjectPlatformService.delete(db, config_id)
        return {"success": True, "message": "平台配置已删除"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{config_id}/activate")
def activate_platform(config_id: int, db: Session = Depends(get_db)):
    """激活指定平台配置"""
    try:
        cfg = ProjectPlatformService.activate(db, config_id)
        return {"success": True, "data": cfg, "message": "平台已激活"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{config_id}/deactivate")
def deactivate_platform(config_id: int, db: Session = Depends(get_db)):
    """取消激活指定平台配置"""
    try:
        cfg = ProjectPlatformService.deactivate(db, config_id)
        return {"success": True, "data": cfg, "message": "平台已取消激活"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{config_id}/enable")
def enable_platform(config_id: int, db: Session = Depends(get_db)):
    """启用指定平台配置"""
    try:
        cfg = ProjectPlatformService.enable(db, config_id)
        return {"success": True, "data": cfg, "message": "平台已启用"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{config_id}/disable")
def disable_platform(config_id: int, db: Session = Depends(get_db)):
    """禁用指定平台配置"""
    try:
        cfg = ProjectPlatformService.disable(db, config_id)
        return {"success": True, "data": cfg, "message": "平台已禁用"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
