"""
模型配置管理器
从数据库获取当前激活的模型配置
"""
from typing import Optional, Dict
from sqlalchemy.orm import Session
from database.connection import SessionLocal, LLMModel


class ModelConfigManager:
    """LLM 模型配置管理器"""
    
    _instance = None
    _cached_config: Optional[Dict] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelConfigManager, cls).__new__(cls)
        return cls._instance
    
    def get_active_model_config(self) -> Dict:
        """
        获取当前激活的模型配置
        
        Returns:
            Dict: 包含模型配置的字典
            {
                'model_name': str,
                'api_key': str,
                'base_url': str,
                'provider': str,
                'temperature': float,
                'max_tokens': int
            }
        """
        db = SessionLocal()
        try:
            # 查询当前激活的模型（不使用缓存，确保实时获取）
            active_model = db.query(LLMModel).filter(LLMModel.is_active == 1).first()
            
            if not active_model:
                raise ValueError("未找到激活的模型，请在模型管理页面激活一个模型")
            
            # 构建配置字典
            config = {
                'model_name': active_model.model_name,
                'api_key': active_model.api_key,
                'base_url': active_model.base_url,
                'provider': active_model.provider or 'openai',
                'temperature': 0.0,  # 默认温度
                'max_tokens': 128000,  # 默认最大 token
            }
            
            # 更新缓存（但不依赖缓存）
            self._cached_config = config
            
            print(f"[ModelConfig] 从数据库加载激活模型: ID={active_model.id}, model_name={config['model_name']}, provider={config['provider']}")
            
            return config
            
        except Exception as e:
            # 如果数据库查询失败，尝试使用缓存
            if self._cached_config:
                print(f"[Warning] 数据库查询失败，使用缓存配置: {e}")
                return self._cached_config
            raise
        finally:
            db.close()
    
    def refresh_config(self):
        """刷新配置缓存"""
        self._cached_config = None
        return self.get_active_model_config()
    
    def get_model_for_langchain(self) -> Dict:
        """
        获取 LangChain 格式的模型配置
        
        Returns:
            Dict: LangChain 初始化参数
        """
        config = self.get_active_model_config()
        
        langchain_config = {
            'model': config['model_name'],
            'api_key': config['api_key'],
            'temperature': config['temperature'],
            'max_tokens': config['max_tokens'],
        }
        
        if config['base_url']:
            langchain_config['base_url'] = config['base_url']
        
        return langchain_config
    
    def get_model_for_browser_use(self) -> Dict:
        """
        获取 Browser-Use 格式的模型配置
        
        Returns:
            Dict: Browser-Use LLM 初始化参数
        """
        config = self.get_active_model_config()
        
        browser_use_config = {
            'model_name': config['model_name'],
            'api_key': config['api_key'],
            'base_url': config['base_url'],
            'temperature': config['temperature'],
        }
        
        return browser_use_config
    
    def increment_token_usage(self, tokens: int):
        """
        增加今日 Token 使用量
        
        Args:
            tokens: 使用的 token 数量
        """
        db = SessionLocal()
        try:
            active_model = db.query(LLMModel).filter(LLMModel.is_active == 1).first()
            if active_model:
                active_model.tokens_used_today = (active_model.tokens_used_today or 0) + tokens
                db.commit()
        except Exception as e:
            print(f"[Warning] 更新 Token 使用量失败: {e}")
            db.rollback()
        finally:
            db.close()


# 全局单例
model_config_manager = ModelConfigManager()


def get_active_llm_config() -> Dict:
    """
    快捷函数：获取当前激活的 LLM 配置
    
    Returns:
        Dict: 模型配置字典
    """
    return model_config_manager.get_active_model_config()


def refresh_llm_config():
    """
    快捷函数：刷新 LLM 配置缓存
    """
    return model_config_manager.refresh_config()
