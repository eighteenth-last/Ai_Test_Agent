"""
Anthropic Provider 实现

支持 Claude 系列模型

作者: Ai_Test_Agent Team
"""
import os
import logging
from typing import Any, Dict, List

from ..base import BaseLLMProvider, LLMConfig, LLMResponse, ProviderType
from ..config import PROVIDER_DEFAULT_ENDPOINTS, get_api_key_env_var

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic Provider
    
    支持 Claude 3 系列模型
    """
    
    @property
    def provider_name(self) -> str:
        return "Anthropic"
    
    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.ANTHROPIC
    
    def __init__(self, config: LLMConfig):
        # 设置默认 base_url
        if not config.base_url:
            config.base_url = os.getenv(
                "ANTHROPIC_ENDPOINT",
                PROVIDER_DEFAULT_ENDPOINTS.get("anthropic", "https://api.anthropic.com")
            )
        
        # 从环境变量获取 API Key
        if not config.api_key:
            env_var = get_api_key_env_var("anthropic")
            config.api_key = os.getenv(env_var, "")
        
        super().__init__(config)
    
    def _initialize_client(self) -> Any:
        """初始化 Anthropic 客户端"""
        try:
            from anthropic import Anthropic
            return Anthropic(
                api_key=self.config.api_key,
                base_url=self.config.base_url
            )
        except ImportError:
            logger.error("[Anthropic] anthropic 库未安装，请运行: pip install anthropic")
            raise
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
        **kwargs
    ) -> LLMResponse:
        """Anthropic 聊天"""
        self.ensure_initialized()
        
        # 分离系统消息和其他消息
        system_message = ""
        chat_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                chat_messages.append(msg)
        
        try:
            response = self._client.messages.create(
                model=self.config.model_name,
                max_tokens=max_tokens or self.config.max_tokens,
                system=system_message if system_message else None,
                messages=chat_messages,
                temperature=temperature if temperature is not None else self.config.temperature,
            )
            
            # 提取内容
            content = ""
            if response.content:
                content = response.content[0].text
            
            return LLMResponse(
                content=content,
                model=response.model,
                finish_reason=response.stop_reason or "",
                prompt_tokens=response.usage.input_tokens if response.usage else 0,
                completion_tokens=response.usage.output_tokens if response.usage else 0,
                total_tokens=(response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0,
                raw_response=response
            )
            
        except Exception as e:
            logger.error(f"[Anthropic] 聊天请求失败: {e}")
            raise
    
    async def achat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
        **kwargs
    ) -> LLMResponse:
        """异步聊天"""
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            logger.error("[Anthropic] anthropic 库未安装")
            raise
        
        async_client = AsyncAnthropic(
            api_key=self.config.api_key,
            base_url=self.config.base_url
        )
        
        system_message = ""
        chat_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                chat_messages.append(msg)
        
        try:
            response = await async_client.messages.create(
                model=self.config.model_name,
                max_tokens=max_tokens or self.config.max_tokens,
                system=system_message if system_message else None,
                messages=chat_messages,
                temperature=temperature if temperature is not None else self.config.temperature,
            )
            
            content = ""
            if response.content:
                content = response.content[0].text
            
            return LLMResponse(
                content=content,
                model=response.model,
                finish_reason=response.stop_reason or "",
                prompt_tokens=response.usage.input_tokens if response.usage else 0,
                completion_tokens=response.usage.output_tokens if response.usage else 0,
                total_tokens=(response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0,
                raw_response=response
            )
            
        except Exception as e:
            logger.error(f"[Anthropic] 异步聊天请求失败: {e}")
            raise
    
    def get_langchain_llm(self) -> Any:
        """获取 LangChain LLM 实例"""
        from langchain_anthropic import ChatAnthropic
        
        return ChatAnthropic(
            model=self.config.model_name,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            temperature=self.config.temperature,
        )
    
    def get_browser_use_llm(self) -> Any:
        """获取 Browser-Use LLM 实例"""
        # Browser-Use 使用 LangChain 的 Anthropic
        return self.get_langchain_llm()
