"""
Token 统计服务 - 用于跟踪和记录 LLM Token 使用量

功能:
- 每次测试的 Token 使用量统计
- 每日 Token 使用量统计
- 与数据库集成，持久化存储

作者: Ai_Test_Agent Team
版本: 1.0
"""

import logging
from datetime import datetime, date
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)


class TokenStatisticsService:
    """Token 统计服务"""
    
    @staticmethod
    def record_token_usage(
        db: Session,
        model_id: int,
        prompt_tokens: int,
        completion_tokens: int,
        cached_tokens: int = 0,
        test_result_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        记录一次 Token 使用
        
        Args:
            db: 数据库会话
            model_id: 模型 ID
            prompt_tokens: 输入 Token 数
            completion_tokens: 输出 Token 数
            cached_tokens: 缓存 Token 数
            test_result_id: 关联的测试结果 ID
            
        Returns:
            记录结果
        """
        try:
            from database.connection import LLMModel
            
            # 获取模型
            model = db.query(LLMModel).filter(LLMModel.id == model_id).first()
            if not model:
                return {"success": False, "message": f"模型 ID {model_id} 不存在"}
            
            total_tokens = prompt_tokens + completion_tokens
            
            # 更新模型的 tokens_used_today 字段
            model.tokens_used_today = (model.tokens_used_today or 0) + total_tokens
            model.updated_at = datetime.now()
            
            db.commit()
            
            logger.info(f"[TokenStats] 记录 Token 使用: model={model.model_name}, tokens={total_tokens}")
            
            return {
                "success": True,
                "data": {
                    "model_id": model_id,
                    "model_name": model.model_name,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "cached_tokens": cached_tokens,
                    "total_tokens": total_tokens,
                    "tokens_used_today": model.tokens_used_today
                }
            }
            
        except Exception as e:
            logger.error(f"[TokenStats] 记录 Token 使用失败: {e}")
            db.rollback()
            return {"success": False, "message": str(e)}
    
    @staticmethod
    def get_today_usage(db: Session, model_id: Optional[int] = None) -> Dict[str, Any]:
        """
        获取今日 Token 使用量
        
        Args:
            db: 数据库会话
            model_id: 可选，指定模型 ID
            
        Returns:
            今日使用量统计
        """
        try:
            from database.connection import LLMModel
            
            query = db.query(LLMModel)
            if model_id:
                query = query.filter(LLMModel.id == model_id)
            
            models = query.all()
            
            total_tokens = sum(m.tokens_used_today or 0 for m in models)
            
            model_stats = [
                {
                    "model_id": m.id,
                    "model_name": m.name,
                    "tokens_used_today": m.tokens_used_today or 0
                }
                for m in models
            ]
            
            return {
                "success": True,
                "data": {
                    "date": date.today().isoformat(),
                    "total_tokens": total_tokens,
                    "models": model_stats
                }
            }
            
        except Exception as e:
            logger.error(f"[TokenStats] 获取今日使用量失败: {e}")
            return {"success": False, "message": str(e)}
    
    @staticmethod
    def reset_daily_usage(db: Session) -> Dict[str, Any]:
        """
        重置所有模型的每日 Token 使用量（用于每日定时任务）
        
        Args:
            db: 数据库会话
            
        Returns:
            重置结果
        """
        try:
            from database.connection import LLMModel
            
            # 重置所有模型的 tokens_used_today
            db.query(LLMModel).update({LLMModel.tokens_used_today: 0})
            db.commit()
            
            logger.info("[TokenStats] 已重置所有模型的每日 Token 使用量")
            
            return {"success": True, "message": "每日使用量已重置"}
            
        except Exception as e:
            logger.error(f"[TokenStats] 重置每日使用量失败: {e}")
            db.rollback()
            return {"success": False, "message": str(e)}
    
    @staticmethod
    def update_model_token_usage(
        db: Session,
        model_name: str,
        token_usage: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        根据模型名称更新 Token 使用量
        
        Args:
            db: 数据库会话
            model_name: 模型名称（model_name 字段）
            token_usage: Token 使用量统计
                - prompt_tokens: 输入 Token 数
                - completion_tokens: 输出 Token 数
                - total_tokens: 总 Token 数
                
        Returns:
            更新结果
        """
        try:
            from database.connection import LLMModel
            
            # 通过模型名称查找（精确匹配 model_name 字段）
            model = db.query(LLMModel).filter(LLMModel.model_name == model_name).first()
            
            if not model:
                # 尝试模糊匹配
                model = db.query(LLMModel).filter(
                    LLMModel.model_name.like(f"%{model_name}%")
                ).first()
            
            if not model:
                logger.warning(f"[TokenStats] 未找到模型: {model_name}")
                return {"success": False, "message": f"模型 {model_name} 不存在"}
            
            total_tokens = token_usage.get('total_tokens', 0)
            if total_tokens == 0:
                total_tokens = token_usage.get('prompt_tokens', 0) + token_usage.get('completion_tokens', 0)
            
            # 更新 tokens_used_today
            model.tokens_used_today = (model.tokens_used_today or 0) + total_tokens
            model.updated_at = datetime.now()
            
            db.commit()
            
            logger.info(f"[TokenStats] 更新 Token 使用: model={model.model_name}, +{total_tokens}, total_today={model.tokens_used_today}")
            
            return {
                "success": True,
                "data": {
                    "model_id": model.id,
                    "model_name": model.model_name,
                    "added_tokens": total_tokens,
                    "tokens_used_today": model.tokens_used_today
                }
            }
            
        except Exception as e:
            logger.error(f"[TokenStats] 更新 Token 使用失败: {e}")
            db.rollback()
            return {"success": False, "message": str(e)}
    
    @staticmethod
    def update_active_model_token_usage(
        db: Session,
        token_usage: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        更新当前激活模型的 Token 使用量
        
        Args:
            db: 数据库会话
            token_usage: Token 使用量统计
                
        Returns:
            更新结果
        """
        try:
            from database.connection import LLMModel
            
            # 直接查找激活的模型
            model = db.query(LLMModel).filter(LLMModel.is_active == 1).first()
            
            if not model:
                logger.warning("[TokenStats] 未找到激活的模型")
                return {"success": False, "message": "未找到激活的模型"}
            
            total_tokens = token_usage.get('total_tokens', 0)
            if total_tokens == 0:
                total_tokens = token_usage.get('prompt_tokens', 0) + token_usage.get('completion_tokens', 0)
            
            # 更新 tokens_used_today
            model.tokens_used_today = (model.tokens_used_today or 0) + total_tokens
            model.updated_at = datetime.now()
            
            db.commit()
            
            logger.info(f"[TokenStats] 更新激活模型 Token: model={model.model_name}, +{total_tokens}, total_today={model.tokens_used_today}")
            
            return {
                "success": True,
                "data": {
                    "model_id": model.id,
                    "model_name": model.model_name,
                    "added_tokens": total_tokens,
                    "tokens_used_today": model.tokens_used_today
                }
            }
            
        except Exception as e:
            logger.error(f"[TokenStats] 更新激活模型 Token 使用失败: {e}")
            db.rollback()
            return {"success": False, "message": str(e)}
