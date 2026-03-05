"""
禅道集成 API 路由

提供配置管理、连接测试、Bug 推送/同步、用例导入等接口。
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from database.connection import get_db
from Zentao_manage.service import ZentaoConfigService, ZentaoBugService, ZentaoCaseService
from Zentao_manage.client import ZentaoClient

router = APIRouter(
    prefix="/api/zentao",
    tags=["禅道集成"]
)


# =====================================================================
# Pydantic 请求模型
# =====================================================================

class ZentaoConfigCreate(BaseModel):
    config_name: str
    base_url: str
    account: str
    password: str
    default_product_id: Optional[int] = None
    api_version: str = "v2"
    description: Optional[str] = None


class ZentaoConfigUpdate(BaseModel):
    config_name: Optional[str] = None
    base_url: Optional[str] = None
    account: Optional[str] = None
    password: Optional[str] = None
    default_product_id: Optional[int] = None
    api_version: Optional[str] = None
    description: Optional[str] = None


class BugPushRequest(BaseModel):
    bug_ids: list[int]
    product_id: Optional[int] = None
    severity: int = 3
    pri: int = 3


class CaseImportRequest(BaseModel):
    product_id: Optional[int] = None
    suite_id: Optional[int] = None
    case_ids: Optional[list[int]] = None
    limit: Optional[int] = None        # 最多导入数量，None / 0 表示不限
    concurrency: Optional[int] = 5    # 并发拉取数，默认 5


# =====================================================================
# 配置管理接口
# =====================================================================

@router.get("/config/list")
def list_configs(db: Session = Depends(get_db)):
    """获取禅道配置列表"""
    return {"success": True, "data": ZentaoConfigService.list_configs(db)}


@router.get("/config/active")
def get_active_config(db: Session = Depends(get_db)):
    """获取当前激活的禅道配置"""
    cfg = ZentaoConfigService.get_active(db)
    return {"success": True, "data": cfg}


@router.post("/config")
def create_config(body: ZentaoConfigCreate, db: Session = Depends(get_db)):
    """新增禅道配置"""
    cfg = ZentaoConfigService.create(db, body.model_dump())
    return {"success": True, "data": cfg, "message": "配置创建成功"}


@router.put("/config/{config_id}")
def update_config(config_id: int, body: ZentaoConfigUpdate,
                  db: Session = Depends(get_db)):
    """更新禅道配置"""
    try:
        cfg = ZentaoConfigService.update(db, config_id, body.model_dump(exclude_none=True))
        return {"success": True, "data": cfg, "message": "配置更新成功"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/config/{config_id}")
def delete_config(config_id: int, db: Session = Depends(get_db)):
    """删除禅道配置"""
    try:
        ZentaoConfigService.delete(db, config_id)
        return {"success": True, "message": "配置已删除"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/config/{config_id}/activate")
def activate_config(config_id: int, db: Session = Depends(get_db)):
    """激活指定配置"""
    try:
        cfg = ZentaoConfigService.activate(db, config_id)
        return {"success": True, "data": cfg, "message": "配置已激活"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/config/test-connection")
async def test_connection(db: Session = Depends(get_db)):
    """测试当前激活配置的连接"""
    from database.connection import ZentaoConfig as ZentaoConfigModel
    row = db.query(ZentaoConfigModel).filter(ZentaoConfigModel.is_active == 1).first()
    if not row:
        raise HTTPException(status_code=400, detail="请先配置并激活禅道连接")
    client = ZentaoClient(base_url=row.base_url, account=row.account, password=row.password)
    result = await client.test_connection()
    return {"success": result["success"], "data": result}


# =====================================================================
# Bug 推送 / 同步接口
# =====================================================================

@router.post("/bugs/push")
async def push_bugs(body: BugPushRequest, db: Session = Depends(get_db)):
    """将 Bug 推送到禅道"""
    try:
        if len(body.bug_ids) == 1:
            result = await ZentaoBugService.push_bug(
                db, body.bug_ids[0], body.product_id, body.severity, body.pri
            )
        else:
            result = await ZentaoBugService.batch_push_bugs(
                db, body.bug_ids, body.product_id
            )
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bugs/sync")
async def sync_bug_status(bug_id: Optional[int] = None,
                          db: Session = Depends(get_db)):
    """从禅道同步 Bug 状态"""
    try:
        result = await ZentaoBugService.sync_bug_status(db, bug_id)
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =====================================================================
# 测试用例导入接口
# =====================================================================

@router.post("/cases/import")
async def import_cases(body: CaseImportRequest, db: Session = Depends(get_db)):
    """从禅道导入测试用例"""
    try:
        result = await ZentaoCaseService.import_cases(
            db, body.product_id, body.suite_id, body.case_ids,
            limit=body.limit, concurrency=body.concurrency or 5
        )
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/products")
async def list_products(db: Session = Depends(get_db)):
    """获取禅道产品列表"""
    try:
        products = await ZentaoCaseService.list_products(db)
        return {"success": True, "data": products}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
