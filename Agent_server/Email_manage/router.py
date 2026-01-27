from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime

from database.connection import get_db, EmailRecord, EmailConfig
from Email_manage.service import EmailService

router = APIRouter(
    prefix="/api/emails",
    tags=["邮件发送管理"]
)


class SendEmailRequest(BaseModel):
    """发送邮件请求模型"""
    contact_ids: List[int]
    subject: str
    html_content: str
    email_type: str = 'custom'


class EmailConfigCreate(BaseModel):
    """创建邮件配置请求模型"""
    config_name: str
    provider: str = 'resend'  # resend/aliyun
    api_key: str
    secret_key: Optional[str] = None  # 仅阿里云需要
    sender_email: EmailStr
    test_email: Optional[EmailStr] = None
    test_mode: int = 1
    description: Optional[str] = None


class EmailConfigUpdate(BaseModel):
    """更新邮件配置请求模型"""
    provider: Optional[str] = None
    api_key: Optional[str] = None
    secret_key: Optional[str] = None
    sender_email: Optional[EmailStr] = None
    test_email: Optional[EmailStr] = None
    test_mode: Optional[int] = None
    description: Optional[str] = None


class EmailConfigResponse(BaseModel):
    """邮件配置响应模型"""
    id: int
    config_name: str
    provider: str
    api_key: str
    secret_key: Optional[str] = None
    sender_email: str
    test_email: Optional[str] = None
    test_mode: int
    is_active: int
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime = None

    class Config:
        from_attributes = True


class EmailRecordResponse(BaseModel):
    """邮件发送记录响应模型"""
    id: int
    subject: str
    recipients: list
    status: str
    success_count: int
    failed_count: int
    total_count: int
    email_type: str
    content_summary: Optional[str] = None
    email_ids: Optional[list] = None
    failed_details: Optional[list] = None
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/send")
async def send_custom_email(
    request: SendEmailRequest,
    db: Session = Depends(get_db)
):
    """
    发送自定义邮件（动态从contacts表获取收件人）
    
    Args:
        request: 发送邮件请求（包含联系人ID列表、主题、内容）
        db: Database session
    
    Returns:
        发送结果
    """
    result = EmailService.send_email(
        contact_ids=request.contact_ids,
        subject=request.subject,
        html_content=request.html_content,
        email_type=request.email_type,
        db=db
    )
    
    if result.get('success'):
        return {"code": 200, "message": result.get('message'), "data": result.get('data')}
    else:
        return {"code": 500, "message": result.get('message'), "data": None}


@router.post("/send-bug-notification")
async def send_bug_notification(
    subject: str,
    html_content: str,
    db: Session = Depends(get_db)
):
    """
    发送BUG通知给所有开启"自动接收BUG"的联系人
    
    Args:
        subject: 邮件主题
        html_content: HTML格式的邮件内容
        db: Database session
    
    Returns:
        发送结果
    """
    result = EmailService.send_to_auto_receive_bug_contacts(
        subject=subject,
        html_content=html_content,
        db=db
    )
    
    if result.get('success'):
        return {"code": 200, "message": result.get('message'), "data": result.get('data')}
    else:
        return {"code": 500, "message": result.get('message'), "data": None}


@router.get("/records", response_model=List[EmailRecordResponse])
async def get_email_records(
    limit: int = 20,
    offset: int = 0,
    status: str = None,
    email_type: str = None,
    db: Session = Depends(get_db)
):
    """
    获取邮件发送记录列表
    
    Args:
        limit: 返回记录数量
        offset: 偏移量
        status: 筛选状态 (success/partial/failed)
        email_type: 筛选邮件类型 (report/bug/custom)
        db: Database session
    
    Returns:
        邮件发送记录列表
    """
    try:
        query = db.query(EmailRecord)
        
        # 应用筛选条件
        if status:
            query = query.filter(EmailRecord.status == status)
        if email_type:
            query = query.filter(EmailRecord.email_type == email_type)
        
        # 按创建时间倒序排列
        records = query.order_by(EmailRecord.created_at.desc()).limit(limit).offset(offset).all()
        
        return records
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取邮件记录失败: {str(e)}")


@router.get("/records/{record_id}", response_model=EmailRecordResponse)
async def get_email_record_detail(
    record_id: int,
    db: Session = Depends(get_db)
):
    """
    获取单条邮件发送记录详情
    
    Args:
        record_id: 记录ID
        db: Database session
    
    Returns:
        邮件发送记录详情
    """
    record = db.query(EmailRecord).filter(EmailRecord.id == record_id).first()
    
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    
    return record


@router.get("/statistics")
async def get_email_statistics(db: Session = Depends(get_db)):
    """
    获取邮件发送统计信息
    
    Returns:
        统计信息
    """
    try:
        # 总发送次数
        total_sends = db.query(EmailRecord).count()
        
        # 成功发送次数
        success_sends = db.query(EmailRecord).filter(EmailRecord.status == 'success').count()
        
        # 部分成功次数
        partial_sends = db.query(EmailRecord).filter(EmailRecord.status == 'partial').count()
        
        # 失败次数
        failed_sends = db.query(EmailRecord).filter(EmailRecord.status == 'failed').count()
        
        # 总成功邮件数（累加所有记录的 success_count）
        from sqlalchemy import func
        total_success_emails = db.query(func.sum(EmailRecord.success_count)).scalar() or 0
        
        # 总失败邮件数
        total_failed_emails = db.query(func.sum(EmailRecord.failed_count)).scalar() or 0
        
        return {
            "success": True,
            "data": {
                "total_sends": total_sends,
                "success_sends": success_sends,
                "partial_sends": partial_sends,
                "failed_sends": failed_sends,
                "total_success_emails": int(total_success_emails),
                "total_failed_emails": int(total_failed_emails),
                "success_rate": round(success_sends / total_sends * 100, 2) if total_sends > 0 else 0
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.delete("/records/{record_id}")
async def delete_email_record(
    record_id: int,
    db: Session = Depends(get_db)
):
    """
    删除邮件发送记录
    
    Args:
        record_id: 记录ID
        db: Database session
    
    Returns:
        删除结果
    """
    record = db.query(EmailRecord).filter(EmailRecord.id == record_id).first()
    
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    
    try:
        db.delete(record)
        db.commit()
        
        return {
            "success": True,
            "message": "删除成功"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


# ==================== 邮件配置管理 ====================

@router.get("/config", response_model=List[EmailConfigResponse])
async def get_email_configs(db: Session = Depends(get_db)):
    """
    获取所有邮件配置列表
    
    Returns:
        邮件配置列表
    """
    try:
        configs = db.query(EmailConfig).order_by(EmailConfig.created_at.desc()).all()
        return configs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


@router.get("/config/active", response_model=Optional[EmailConfigResponse])
async def get_active_config(db: Session = Depends(get_db)):
    """
    获取当前激活的邮件配置
    
    Returns:
        激活的邮件配置
    """
    config = db.query(EmailConfig).filter(EmailConfig.is_active == 1).first()
    
    if not config:
        return None
    
    return config


@router.post("/config", response_model=dict)
async def create_email_config(
    config_data: EmailConfigCreate,
    db: Session = Depends(get_db)
):
    """
    创建新的邮件配置
    
    Args:
        config_data: 配置数据
        db: Database session
    
    Returns:
        创建结果
    """
    try:
        print(f"[EmailConfig] 创建配置请求: {config_data.dict()}")
        
        # 检查配置名称是否已存在
        existing = db.query(EmailConfig).filter(EmailConfig.config_name == config_data.config_name).first()
        if existing:
            raise HTTPException(status_code=400, detail="配置名称已存在")
        
        # 创建新配置
        new_config = EmailConfig(
            config_name=config_data.config_name,
            provider=config_data.provider,
            api_key=config_data.api_key,
            secret_key=config_data.secret_key,
            sender_email=config_data.sender_email,
            test_email=config_data.test_email,
            test_mode=config_data.test_mode,
            description=config_data.description,
            is_active=0  # 默认不激活
        )
        
        db.add(new_config)
        db.commit()
        db.refresh(new_config)
        
        return {
            "success": True,
            "message": "配置创建成功",
            "data": {
                "id": new_config.id,
                "config_name": new_config.config_name
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建配置失败: {str(e)}")


@router.put("/config/{config_id}")
async def update_email_config(
    config_id: int,
    config_data: EmailConfigUpdate,
    db: Session = Depends(get_db)
):
    """
    更新邮件配置
    
    Args:
        config_id: 配置ID
        config_data: 更新数据
        db: Database session
    
    Returns:
        更新结果
    """
    config = db.query(EmailConfig).filter(EmailConfig.id == config_id).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    
    try:
        # 更新字段
        if config_data.provider is not None:
            config.provider = config_data.provider
        if config_data.api_key is not None:
            config.api_key = config_data.api_key
        if config_data.secret_key is not None:
            config.secret_key = config_data.secret_key
        if config_data.sender_email is not None:
            config.sender_email = config_data.sender_email
        if config_data.test_email is not None:
            config.test_email = config_data.test_email
        if config_data.test_mode is not None:
            config.test_mode = config_data.test_mode
        if config_data.description is not None:
            config.description = config_data.description
        
        db.commit()
        
        return {
            "success": True,
            "message": "配置更新成功"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")


@router.post("/config/{config_id}/activate")
async def activate_config(
    config_id: int,
    db: Session = Depends(get_db)
):
    """
    激活指定的邮件配置
    
    Args:
        config_id: 配置ID
        db: Database session
    
    Returns:
        激活结果
    """
    config = db.query(EmailConfig).filter(EmailConfig.id == config_id).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    
    try:
        # 先将所有配置设为未激活
        db.query(EmailConfig).update({"is_active": 0})
        
        # 激活指定配置
        config.is_active = 1
        
        db.commit()
        
        return {
            "success": True,
            "message": f"配置 '{config.config_name}' 已激活"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"激活配置失败: {str(e)}")


@router.delete("/config/{config_id}")
async def delete_email_config(
    config_id: int,
    db: Session = Depends(get_db)
):
    """
    删除邮件配置
    
    Args:
        config_id: 配置ID
        db: Database session
    
    Returns:
        删除结果
    """
    config = db.query(EmailConfig).filter(EmailConfig.id == config_id).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    
    if config.is_active == 1:
        raise HTTPException(status_code=400, detail="无法删除激活中的配置，请先激活其他配置")
    
    try:
        db.delete(config)
        db.commit()
        
        return {
            "success": True,
            "message": "配置删除成功"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除配置失败: {str(e)}")

