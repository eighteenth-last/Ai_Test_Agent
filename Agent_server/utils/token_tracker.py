"""
Token 跟踪服务 - 借鉴 browser-use 的 token 统计实现

功能:
- 实时跟踪每次 LLM 调用的 token 使用
- 支持缓存 token 统计（prompt_cached_tokens, cache_creation_tokens）
- 计算每个模型的总使用量和成本
- 按模型分类统计
- 持久化到数据库

作者: Ai_Test_Agent Team
版本: 2.0 (基于 browser-use 0.11.1)
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================

class TokenUsage(BaseModel):
    """单次 LLM 调用的 token 使用情况"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    
    # 缓存相关 token（Anthropic Claude 等模型支持）
    prompt_cached_tokens: Optional[int] = None  # 从缓存读取的 token
    prompt_cache_creation_tokens: Optional[int] = None  # 创建缓存的 token
    
    @property
    def total_tokens(self) -> int:
        """总 token 数量"""
        return self.prompt_tokens + self.completion_tokens


class TokenUsageEntry(BaseModel):
    """token 使用记录条目"""
    model_name: str
    timestamp: datetime
    usage: TokenUsage
    step_number: Optional[int] = None  # 测试步骤编号
    action_type: Optional[str] = None  # 动作类型


class ModelUsageStats(BaseModel):
    """按模型统计的使用情况"""
    model_name: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0  # 总缓存 token
    cache_creation_tokens: int = 0  # 缓存创建 token
    invocations: int = 0  # 调用次数
    
    @property
    def average_tokens_per_call(self) -> float:
        """每次调用平均 token 数"""
        return self.total_tokens / self.invocations if self.invocations > 0 else 0.0
    
    @property
    def cache_hit_rate(self) -> float:
        """缓存命中率"""
        total_prompt = self.prompt_tokens + self.cache_creation_tokens
        if total_prompt == 0:
            return 0.0
        return self.cached_tokens / total_prompt


class UsageSummary(BaseModel):
    """使用情况汇总"""
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cached_tokens: int = 0
    total_cache_creation_tokens: int = 0
    total_invocations: int = 0
    
    by_model: Dict[str, ModelUsageStats] = Field(default_factory=dict)
    
    @property
    def cache_hit_rate(self) -> float:
        """缓存命中率 (0.0 - 1.0)"""
        total_prompt = self.total_prompt_tokens + self.total_cache_creation_tokens
        if total_prompt == 0:
            return 0.0
        return self.total_cached_tokens / total_prompt


# ==================== Token 跟踪器 ====================

class TokenTracker:
    """Token 使用跟踪器"""
    
    def __init__(self):
        self.usage_history: List[TokenUsageEntry] = []
        self._current_step: Optional[int] = None
    
    def set_current_step(self, step_number: int):
        """设置当前步骤编号"""
        self._current_step = step_number
    
    def add_usage(
        self,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        prompt_cached_tokens: Optional[int] = None,
        prompt_cache_creation_tokens: Optional[int] = None,
        action_type: Optional[str] = None
    ) -> TokenUsageEntry:
        """
        添加一次 token 使用记录
        
        Args:
            model_name: 模型名称
            prompt_tokens: 输入 token 数
            completion_tokens: 输出 token 数
            prompt_cached_tokens: 从缓存读取的 token 数
            prompt_cache_creation_tokens: 创建缓存的 token 数
            action_type: 动作类型
        
        Returns:
            TokenUsageEntry: 使用记录
        """
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            prompt_cached_tokens=prompt_cached_tokens,
            prompt_cache_creation_tokens=prompt_cache_creation_tokens
        )
        
        entry = TokenUsageEntry(
            model_name=model_name,
            timestamp=datetime.now(),
            usage=usage,
            step_number=self._current_step,
            action_type=action_type
        )
        
        self.usage_history.append(entry)
        
        # 日志输出
        self._log_usage(entry)
        
        return entry
    
    def _log_usage(self, entry: TokenUsageEntry):
        """记录 token 使用日志（带颜色输出）"""
        usage = entry.usage
        
        # 计算新 token（非缓存）
        new_prompt_tokens = usage.prompt_tokens - (usage.prompt_cached_tokens or 0)
        
        parts = []
        
        # 输入 token
        if usage.prompt_cached_tokens or usage.prompt_cache_creation_tokens:
            if new_prompt_tokens > 0:
                parts.append(f"🆕 {new_prompt_tokens}")
            if usage.prompt_cached_tokens:
                parts.append(f"💾 {usage.prompt_cached_tokens}")
            if usage.prompt_cache_creation_tokens:
                parts.append(f"📝 {usage.prompt_cache_creation_tokens}")
        else:
            parts.append(f"📥 {usage.prompt_tokens}")
        
        # 输出 token
        parts.append(f"📤 {usage.completion_tokens}")
        
        # 总计
        parts.append(f"Σ {usage.total_tokens}")
        
        step_info = f"[Step {entry.step_number}]" if entry.step_number else ""
        action_info = f"[{entry.action_type}]" if entry.action_type else ""
        
        logger.info(f"[TokenTracker] {step_info}{action_info} {entry.model_name}: {' | '.join(parts)}")
    
    def get_summary(self) -> UsageSummary:
        """
        获取使用情况汇总
        
        Returns:
            UsageSummary: 汇总统计
        """
        summary = UsageSummary()
        
        for entry in self.usage_history:
            usage = entry.usage
            model_name = entry.model_name
            
            # 更新总计
            summary.total_prompt_tokens += usage.prompt_tokens
            summary.total_completion_tokens += usage.completion_tokens
            summary.total_tokens += usage.total_tokens
            summary.total_cached_tokens += usage.prompt_cached_tokens or 0
            summary.total_cache_creation_tokens += usage.prompt_cache_creation_tokens or 0
            summary.total_invocations += 1
            
            # 按模型统计
            if model_name not in summary.by_model:
                summary.by_model[model_name] = ModelUsageStats(model_name=model_name)
            
            model_stats = summary.by_model[model_name]
            model_stats.prompt_tokens += usage.prompt_tokens
            model_stats.completion_tokens += usage.completion_tokens
            model_stats.total_tokens += usage.total_tokens
            model_stats.cached_tokens += usage.prompt_cached_tokens or 0
            model_stats.cache_creation_tokens += usage.prompt_cache_creation_tokens or 0
            model_stats.invocations += 1
        
        return summary
    
    def clear(self):
        """清空使用历史"""
        self.usage_history.clear()
        self._current_step = None
    
    def get_model_usage(self, model_name: str) -> Optional[ModelUsageStats]:
        """
        获取指定模型的使用统计
        
        Args:
            model_name: 模型名称
        
        Returns:
            ModelUsageStats: 模型统计，如果没有记录则返回 None
        """
        summary = self.get_summary()
        return summary.by_model.get(model_name)


# ==================== 数据库持久化服务 ====================

class TokenStatisticsService:
    """Token 统计数据库服务"""
    
    @staticmethod
    def update_active_model_token_usage(
        db: Session,
        token_usage: Dict[str, int]
    ) -> Dict[str, any]:
        """
        更新激活模型的 token 使用量
        
        Args:
            db: 数据库会话
            token_usage: token 使用字典 {'prompt_tokens': xxx, 'completion_tokens': xxx, 'total_tokens': xxx}
        
        Returns:
            更新结果
        """
        try:
            from database.connection import LLMModel
            
            # 获取激活的模型
            active_model = db.query(LLMModel).filter(
                LLMModel.is_active == True
            ).first()
            
            if not active_model:
                return {"success": False, "message": "未找到激活的模型"}
            
            total_tokens = token_usage.get('total_tokens', 0)
            
            # 更新模型的今日使用量
            active_model.tokens_used_today = (active_model.tokens_used_today or 0) + total_tokens
            active_model.updated_at = datetime.now()
            
            db.commit()
            
            logger.info(
                f"[TokenStats] 更新模型 token 使用: "
                f"model={active_model.model_name}, "
                f"prompt={token_usage.get('prompt_tokens', 0)}, "
                f"completion={token_usage.get('completion_tokens', 0)}, "
                f"total={total_tokens}, "
                f"today_total={active_model.tokens_used_today}"
            )
            
            return {
                "success": True,
                "data": {
                    "model_id": active_model.id,
                    "model_name": active_model.model_name,
                    "tokens_added": total_tokens,
                    "tokens_used_today": active_model.tokens_used_today
                }
            }
            
        except Exception as e:
            logger.error(f"[TokenStats] 更新 token 使用失败: {e}")
            db.rollback()
            return {"success": False, "message": str(e)}
    
    @staticmethod
    def reset_daily_usage(db: Session) -> Dict[str, any]:
        """
        重置所有模型的今日使用量（每日凌晨调用）
        
        Args:
            db: 数据库会话
        
        Returns:
            重置结果
        """
        try:
            from database.connection import LLMModel
            
            models = db.query(LLMModel).all()
            reset_count = 0
            
            for model in models:
                if model.tokens_used_today and model.tokens_used_today > 0:
                    model.tokens_used_today = 0
                    reset_count += 1
            
            db.commit()
            
            logger.info(f"[TokenStats] 已重置 {reset_count} 个模型的今日 token 使用量")
            
            return {
                "success": True,
                "message": f"已重置 {reset_count} 个模型的今日使用量"
            }
            
        except Exception as e:
            logger.error(f"[TokenStats] 重置今日使用量失败: {e}")
            db.rollback()
            return {"success": False, "message": str(e)}
    
    @staticmethod
    def get_today_usage(db: Session, model_id: Optional[int] = None) -> Dict[str, any]:
        """
        获取今日 token 使用量
        
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
            
            total_usage = 0
            model_usage = []
            
            for model in models:
                usage = model.tokens_used_today or 0
                total_usage += usage
                model_usage.append({
                    "model_id": model.id,
                    "model_name": model.model_name,
                    "tokens_used_today": usage
                })
            
            return {
                "success": True,
                "data": {
                    "total_tokens": total_usage,
                    "models": model_usage
                }
            }
            
        except Exception as e:
            logger.error(f"[TokenStats] 获取今日使用量失败: {e}")
            return {"success": False, "message": str(e)}
