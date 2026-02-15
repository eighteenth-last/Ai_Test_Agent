"""
Moonshot/Kimi Provider 实现

支持月之暗面 Moonshot 系列模型，兼容 OpenAI API

作者: Ai_Test_Agent Team
"""
import os
import logging
from typing import Any, Dict, List

from ..base import BaseOpenAICompatibleProvider, LLMConfig, LLMResponse, ProviderType
from ..config import PROVIDER_DEFAULT_ENDPOINTS, get_api_key_env_var

logger = logging.getLogger(__name__)


class MoonshotProvider(BaseOpenAICompatibleProvider):
    """
    Moonshot/Kimi Provider
    
    支持 Moonshot 系列模型
    """
    
    @property
    def provider_name(self) -> str:
        return "Moonshot"
    
    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.MOONSHOT
    
    def __init__(self, config: LLMConfig):
        # 设置默认 base_url
        if not config.base_url:
            config.base_url = os.getenv(
                "MOONSHOT_ENDPOINT",
                PROVIDER_DEFAULT_ENDPOINTS.get("moonshot", "https://api.moonshot.cn/v1")
            )
        
        # 从环境变量获取 API Key
        if not config.api_key:
            env_var = get_api_key_env_var("moonshot")
            config.api_key = os.getenv(env_var, "")
        
        super().__init__(config)
    
    def get_langchain_llm(self) -> Any:
        """获取 LangChain LLM 实例"""
        from langchain_openai import ChatOpenAI
        
        return ChatOpenAI(
            model=self.config.model_name,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            temperature=self.config.temperature,
        )
    
    def get_browser_use_llm(self) -> Any:
        """获取 Browser-Use LLM 实例"""
        try:
            from browser_use.llm.openai.chat import ChatOpenAI as BrowserUseChatOpenAI
            
            return BrowserUseChatOpenAI(
                model=self.config.model_name,
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                temperature=self.config.temperature,
                dont_force_structured_output=True,  # Moonshot 可能不完全支持结构化输出
            )
        except ImportError:
            logger.warning("[Moonshot] browser-use 未安装，回退到 LangChain")
            return self.get_langchain_llm()
    
    def supports_structured_output(self) -> bool:
        """Moonshot 可能不完全支持结构化输出"""
        return False
