"""
项目管理平台统一配置 - 服务层
"""
import logging
from typing import Optional
from sqlalchemy.orm import Session
from database.connection import ProjectPlatformConfig

logger = logging.getLogger(__name__)


class ProjectPlatformService:
    """项目管理平台配置服务"""

    # 支持的平台列表
    SUPPORTED_PLATFORMS = [
        {"platform_id": "zentao", "platform_name": "禅道 (Zentao)", "description": "开源项目管理软件"},
        {"platform_id": "pingcode", "platform_name": "PingCode", "description": "研发团队项目管理工具"},
        {"platform_id": "worktile", "platform_name": "Worktile", "description": "企业协作与项目管理工具"},
        {"platform_id": "ones", "platform_name": "ONES", "description": "研发项目管理工具"},
        {"platform_id": "yunxiao", "platform_name": "云效", "description": "阿里云研发协同平台"},
        {"platform_id": "tapd", "platform_name": "TAPD", "description": "腾讯敏捷产品研发协作平台"},
        {"platform_id": "8manage", "platform_name": "8Manage PM", "description": "企业级项目管理系统"},
        {"platform_id": "msproject", "platform_name": "Microsoft Project", "description": "微软项目管理软件"},
        {"platform_id": "asana", "platform_name": "Asana", "description": "团队协作和项目管理工具"},
        {"platform_id": "clickup", "platform_name": "ClickUp", "description": "全能型项目管理工具"},
        {"platform_id": "jira", "platform_name": "Jira", "description": "Atlassian敏捷项目管理工具"},
    ]

    @staticmethod
    def get_supported_platforms() -> list[dict]:
        """获取系统支持的所有平台列表"""
        return ProjectPlatformService.SUPPORTED_PLATFORMS

    @staticmethod
    def list_all(db: Session) -> list[dict]:
        """获取所有平台配置列表"""
        rows = db.query(ProjectPlatformConfig).order_by(
            ProjectPlatformConfig.is_active.desc(),
            ProjectPlatformConfig.id.desc()
        ).all()
        return [ProjectPlatformService._to_dict(r) for r in rows]

    @staticmethod
    def list_active(db: Session) -> list[dict]:
        """获取已激活且启用的平台列表（用于动态菜单）"""
        rows = db.query(ProjectPlatformConfig).filter(
            ProjectPlatformConfig.is_active == 1,
            ProjectPlatformConfig.is_enabled == 1
        ).order_by(ProjectPlatformConfig.id).all()
        return [ProjectPlatformService._to_dict(r) for r in rows]

    @staticmethod
    def get_by_platform_id(db: Session, platform_id: str) -> Optional[dict]:
        """根据平台标识获取配置"""
        cfg = db.query(ProjectPlatformConfig).filter(
            ProjectPlatformConfig.platform_id == platform_id
        ).first()
        return ProjectPlatformService._to_dict(cfg) if cfg else None

    @staticmethod
    def create(db: Session, data: dict) -> dict:
        """创建新的平台配置"""
        # 检查 platform_id 是否已存在
        existing = db.query(ProjectPlatformConfig).filter(
            ProjectPlatformConfig.platform_id == data.get("platform_id")
        ).first()
        if existing:
            raise ValueError(f"平台标识 {data.get('platform_id')} 已存在")

        cfg = ProjectPlatformConfig(**{
            k: v for k, v in data.items()
            if hasattr(ProjectPlatformConfig, k)
        })
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
        return ProjectPlatformService._to_dict(cfg)

    @staticmethod
    def update(db: Session, config_id: int, data: dict) -> dict:
        """更新平台配置"""
        cfg = db.query(ProjectPlatformConfig).filter(
            ProjectPlatformConfig.id == config_id
        ).first()
        if not cfg:
            raise ValueError("配置不存在")

        logger.info(f"[ProjectPlatform] 更新前 is_enabled={cfg.is_enabled}")
        for k, v in data.items():
            if hasattr(cfg, k) and k not in ("id", "platform_id", "created_at"):
                logger.info(f"[ProjectPlatform] 设置字段 {k}={v}")
                setattr(cfg, k, v)
        logger.info(f"[ProjectPlatform] 更新后 is_enabled={cfg.is_enabled}")
        
        db.commit()
        db.refresh(cfg)
        return ProjectPlatformService._to_dict(cfg)

    @staticmethod
    def delete(db: Session, config_id: int):
        """删除平台配置"""
        cfg = db.query(ProjectPlatformConfig).filter(
            ProjectPlatformConfig.id == config_id
        ).first()
        if not cfg:
            raise ValueError("配置不存在")
        db.delete(cfg)
        db.commit()

    @staticmethod
    def activate(db: Session, config_id: int) -> dict:
        """激活指定平台配置"""
        cfg = db.query(ProjectPlatformConfig).filter(
            ProjectPlatformConfig.id == config_id
        ).first()
        if not cfg:
            raise ValueError("配置不存在")
        cfg.is_active = 1
        db.commit()
        db.refresh(cfg)
        return ProjectPlatformService._to_dict(cfg)

    @staticmethod
    def deactivate(db: Session, config_id: int) -> dict:
        """取消激活指定平台配置"""
        cfg = db.query(ProjectPlatformConfig).filter(
            ProjectPlatformConfig.id == config_id
        ).first()
        if not cfg:
            raise ValueError("配置不存在")
        cfg.is_active = 0
        db.commit()
        db.refresh(cfg)
        return ProjectPlatformService._to_dict(cfg)

    @staticmethod
    def enable(db: Session, config_id: int) -> dict:
        """启用指定平台配置"""
        cfg = db.query(ProjectPlatformConfig).filter(
            ProjectPlatformConfig.id == config_id
        ).first()
        if not cfg:
            raise ValueError("配置不存在")
        cfg.is_enabled = 1
        db.commit()
        db.refresh(cfg)
        return ProjectPlatformService._to_dict(cfg)

    @staticmethod
    def disable(db: Session, config_id: int) -> dict:
        """禁用指定平台配置"""
        cfg = db.query(ProjectPlatformConfig).filter(
            ProjectPlatformConfig.id == config_id
        ).first()
        if not cfg:
            raise ValueError("配置不存在")
        cfg.is_enabled = 0
        db.commit()
        db.refresh(cfg)
        return ProjectPlatformService._to_dict(cfg)

    @staticmethod
    def _to_dict(cfg: ProjectPlatformConfig) -> dict:
        """将模型转换为字典"""
        return {
            "id": cfg.id,
            "platform_id": cfg.platform_id,
            "platform_name": cfg.platform_name,
            "config_name": cfg.config_name,
            "base_url": cfg.base_url,
            "account": cfg.account,
            "api_token": cfg.api_token,
            "default_product_id": cfg.default_product_id,
            "api_version": cfg.api_version,
            "extra_config": cfg.extra_config,
            "is_active": cfg.is_active,
            "is_enabled": cfg.is_enabled,
            "last_sync_at": cfg.last_sync_at.isoformat() if cfg.last_sync_at else None,
            "description": cfg.description,
            "created_at": cfg.created_at.isoformat() if cfg.created_at else None,
            "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
        }
