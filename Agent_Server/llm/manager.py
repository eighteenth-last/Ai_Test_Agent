"""
LLM 配置管理器模块

从数据库获取当前激活的模型配置，提供统一的配置管理接口

作者: Ai_Test_Agent Team
版本: 1.0
"""
import logging
from typing import Any, Dict, Optional

from .base import LLMConfig, BaseLLMProvider
from .factory import create_llm_provider, get_llm_model, get_browser_use_llm
from .exceptions import NoActiveModelError, ConfigurationError

logger = logging.getLogger(__name__)


class ModelConfigManager:
    """
    LLM 模型配置管理器
    
    提供从数据库获取激活模型配置的功能
    """
    
    _instance = None
    _cached_config: Optional[Dict] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelConfigManager, cls).__new__(cls)
        return cls._instance
    
    def _get_db_session(self):
        """获取数据库会话"""
        try:
            # 尝试导入项目的数据库连接
            import sys
            import os
            
            # 添加项目路径
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            
            from database.connection import SessionLocal
            return SessionLocal()
        except ImportError as e:
            logger.error(f"[ModelConfigManager] 无法导入数据库连接: {e}")
            raise
    
    def _get_model_from_db(self, db=None) -> Dict:
        """从数据库获取激活的模型配置"""
        close_db = False
        if db is None:
            db = self._get_db_session()
            close_db = True
        
        try:
            from database.connection import LLMModel
            
            # 查询当前激活的模型
            active_model = db.query(LLMModel).filter(LLMModel.is_active == 1).first()
            
            if not active_model:
                raise NoActiveModelError()
            
            config = {
                'id': active_model.id,
                'model_name': active_model.model_name,
                'api_key': active_model.api_key,
                'base_url': active_model.base_url or '',
                'provider': active_model.provider or 'openai',
                'temperature': 0.0,
                'max_tokens': 128000,
            }
            
            logger.info(f"[ModelConfigManager] 从数据库加载激活模型: ID={active_model.id}, "
                       f"model_name={config['model_name']}, provider={config['provider']}")
            
            return config
            
        except NoActiveModelError:
            raise
        except Exception as e:
            logger.error(f"[ModelConfigManager] 查询数据库失败: {e}")
            raise ConfigurationError(f"数据库查询失败: {e}")
        finally:
            if close_db:
                db.close()
    
    def get_active_model_config(self, db=None, use_cache: bool = False) -> Dict:
        """
        获取当前激活的模型配置
        
        Args:
            db: 数据库会话（可选）
            use_cache: 是否使用缓存
        
        Returns:
            模型配置字典
        """
        if use_cache and self._cached_config:
            return self._cached_config
        
        config = self._get_model_from_db(db)
        self._cached_config = config
        return config
    
    def refresh_config(self, db=None) -> Dict:
        """刷新配置缓存"""
        self._cached_config = None
        return self.get_active_model_config(db)
    
    def get_llm_provider(self, db=None) -> BaseLLMProvider:
        """
        获取激活模型的 LLM Provider
        
        Returns:
            BaseLLMProvider 实例
        """
        config = self.get_active_model_config(db)
        
        return create_llm_provider(
            provider=config['provider'],
            model_name=config['model_name'],
            api_key=config['api_key'],
            base_url=config['base_url'],
            temperature=config.get('temperature', 0.0),
            max_tokens=config.get('max_tokens', 128000),
        )
    
    def get_langchain_llm(self, db=None) -> Any:
        """
        获取 LangChain 格式的 LLM
        
        Returns:
            LangChain LLM 实例
        """
        config = self.get_active_model_config(db)
        
        return get_llm_model(
            provider=config['provider'],
            model_name=config['model_name'],
            api_key=config['api_key'],
            base_url=config['base_url'],
            temperature=config.get('temperature', 0.0),
        )
    
    def get_browser_use_llm(self, db=None) -> Any:
        """
        获取 Browser-Use 格式的 LLM
        
        Returns:
            Browser-Use LLM 实例
        """
        config = self.get_active_model_config(db)
        
        return get_browser_use_llm(
            provider=config['provider'],
            model_name=config['model_name'],
            api_key=config['api_key'],
            base_url=config['base_url'],
            temperature=config.get('temperature', 0.0),
        )
    
    def get_model_for_langchain(self, db=None) -> Dict:
        """
        获取 LangChain 格式的模型配置（兼容旧接口）
        
        Returns:
            LangChain 初始化参数
        """
        config = self.get_active_model_config(db)
        
        langchain_config = {
            'model': config['model_name'],
            'api_key': config['api_key'],
            'temperature': config.get('temperature', 0.0),
            'max_tokens': config.get('max_tokens', 128000),
        }
        
        if config.get('base_url'):
            langchain_config['base_url'] = config['base_url']
        
        return langchain_config
    
    def get_model_for_browser_use(self, db=None) -> Dict:
        """
        获取 Browser-Use 格式的模型配置（兼容旧接口）
        
        Returns:
            Browser-Use LLM 初始化参数
        """
        config = self.get_active_model_config(db)
        
        browser_use_config = {
            'model_name': config['model_name'],
            'api_key': config['api_key'],
            'base_url': config['base_url'],
            'temperature': config.get('temperature', 0.0),
            'provider': config['provider'],
        }
        
        return browser_use_config
    
    def increment_token_usage(self, tokens: int, db=None):
        """
        增加今日 Token 使用量和总 Token 使用量
        
        Args:
            tokens: 使用的 token 数量
            db: 数据库会话
        """
        close_db = False
        if db is None:
            db = self._get_db_session()
            close_db = True
        
        try:
            from database.connection import LLMModel
            
            active_model = db.query(LLMModel).filter(LLMModel.is_active == 1).first()
            if active_model:
                active_model.tokens_used_today = (active_model.tokens_used_today or 0) + tokens
                active_model.tokens_used_total = (active_model.tokens_used_total or 0) + tokens
                db.commit()
                logger.debug(f"[ModelConfigManager] Token 使用量更新: +{tokens}")
        except Exception as e:
            logger.warning(f"[ModelConfigManager] 更新 Token 使用量失败: {e}")
            db.rollback()
        finally:
            if close_db:
                db.close()


# 全局单例
model_config_manager = ModelConfigManager()


# 便捷函数
def get_active_llm_config(db=None) -> Dict:
    """获取当前激活的 LLM 配置"""
    return model_config_manager.get_active_model_config(db)


def get_active_llm_provider(db=None) -> BaseLLMProvider:
    """获取当前激活的 LLM Provider"""
    return model_config_manager.get_llm_provider(db)


def get_active_langchain_llm(db=None) -> Any:
    """获取当前激活的 LangChain LLM"""
    return model_config_manager.get_langchain_llm(db)


def get_active_browser_use_llm(db=None) -> Any:
    """获取当前激活的 Browser-Use LLM"""
    return model_config_manager.get_browser_use_llm(db)


def refresh_llm_config(db=None) -> Dict:
    """刷新 LLM 配置缓存"""
    return model_config_manager.refresh_config(db)
