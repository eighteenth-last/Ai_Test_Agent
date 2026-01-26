from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from datetime import datetime

from database.connection import get_db, LLMModel

router = APIRouter(
    prefix="/api/models",
    tags=["模型管理"]
)


# Pydantic 模型定义
class ModelCreate(BaseModel):
    """创建模型的请求模型"""
    model_name: str
    api_key: str
    base_url: str = None
    provider: str = None
    priority: int = 1
    utilization: int = 100


class ModelUpdate(BaseModel):
    """更新模型的请求模型"""
    model_name: str = None
    api_key: str = None
    base_url: str = None
    provider: str = None
    priority: int = None
    utilization: int = None
    is_active: int = None
    status: str = None


class ModelResponse(BaseModel):
    """模型响应模型"""
    id: int
    model_name: str
    api_key: str
    base_url: str = None
    provider: str = None
    is_active: int
    priority: int
    utilization: int
    tokens_used_today: int
    status: str
    created_at: datetime
    updated_at: datetime = None

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ModelResponse])
async def get_models(db: Session = Depends(get_db)):
    """获取所有模型列表"""
    try:
        models = db.query(LLMModel).order_by(LLMModel.priority).all()
        return models
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")


@router.get("/{model_id}", response_model=ModelResponse)
async def get_model(model_id: int, db: Session = Depends(get_db)):
    """获取单个模型详情"""
    model = db.query(LLMModel).filter(LLMModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    return model


@router.post("/", response_model=dict)
async def create_model(model_data: ModelCreate, db: Session = Depends(get_db)):
    """创建新模型"""
    try:
        # 检查是否已存在同名模型
        existing = db.query(LLMModel).filter(LLMModel.model_name == model_data.model_name).first()
        if existing:
            raise HTTPException(status_code=400, detail="模型名称已存在")
        
        # 创建新模型
        new_model = LLMModel(
            model_name=model_data.model_name,
            api_key=model_data.api_key,
            base_url=model_data.base_url,
            provider=model_data.provider,
            priority=model_data.priority,
            utilization=model_data.utilization,
            is_active=0,
            tokens_used_today=0,
            status='待命'
        )
        
        db.add(new_model)
        db.commit()
        db.refresh(new_model)
        
        return {
            "success": True,
            "message": "模型创建成功",
            "data": {
                "id": new_model.id,
                "model_name": new_model.model_name
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建模型失败: {str(e)}")


@router.put("/{model_id}", response_model=dict)
async def update_model(model_id: int, model_data: ModelUpdate, db: Session = Depends(get_db)):
    """更新模型信息"""
    try:
        model = db.query(LLMModel).filter(LLMModel.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")
        
        # 更新字段
        update_data = model_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(model, field, value)
        
        model.updated_at = datetime.now()
        db.commit()
        db.refresh(model)
        
        return {
            "success": True,
            "message": "模型更新成功",
            "data": {
                "id": model.id,
                "model_name": model.model_name
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新模型失败: {str(e)}")


@router.delete("/{model_id}", response_model=dict)
async def delete_model(model_id: int, db: Session = Depends(get_db)):
    """删除模型"""
    try:
        model = db.query(LLMModel).filter(LLMModel.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")
        
        # 不允许删除正在激活的模型
        if model.is_active == 1:
            raise HTTPException(status_code=400, detail="无法删除激活中的模型，请先切换到其他模型")
        
        db.delete(model)
        db.commit()
        
        return {
            "success": True,
            "message": "模型删除成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除模型失败: {str(e)}")


@router.post("/{model_id}/activate", response_model=dict)
async def activate_model(model_id: int, db: Session = Depends(get_db)):
    """激活模型（将当前模型设置为活跃状态，其他模型设为待命）"""
    try:
        # 查找目标模型
        model = db.query(LLMModel).filter(LLMModel.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")
        
        # 将所有模型设为非激活
        db.query(LLMModel).update({LLMModel.is_active: 0})
        
        # 激活目标模型
        model.is_active = 1
        model.status = 'DeepSeek V3'  # 或者根据模型名称动态设置
        model.updated_at = datetime.now()
        
        db.commit()
        
        # 刷新模型配置缓存
        from Model_manage.config_manager import refresh_llm_config
        refresh_llm_config()
        
        return {
            "success": True,
            "message": f"模型 {model.model_name} 已激活，配置已刷新"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"激活模型失败: {str(e)}")


@router.get("/active/current", response_model=dict)
async def get_active_model(db: Session = Depends(get_db)):
    """获取当前激活的模型"""
    try:
        active_model = db.query(LLMModel).filter(LLMModel.is_active == 1).first()
        if not active_model:
            return {
                "success": True,
                "data": None,
                "message": "当前没有激活的模型"
            }
        
        return {
            "success": True,
            "data": {
                "id": active_model.id,
                "model_name": active_model.model_name,
                "provider": active_model.provider,
                "status": active_model.status,
                "tokens_used_today": active_model.tokens_used_today
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取激活模型失败: {str(e)}")
