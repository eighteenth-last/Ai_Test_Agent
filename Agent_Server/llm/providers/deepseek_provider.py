"""
DeepSeek Provider 实现

支持 DeepSeek Chat 和 DeepSeek Reasoner（R1）模型
特别处理 R1 模型的 reasoning_content 输出

作者: Ai_Test_Agent Team
"""
import os
import logging
from typing import Any, Dict, List

from langchain_core.language_models.base import LanguageModelInput
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

from ..base import BaseOpenAICompatibleProvider, LLMConfig, LLMResponse, ProviderType
from ..config import PROVIDER_DEFAULT_ENDPOINTS, get_api_key_env_var, is_reasoning_model

logger = logging.getLogger(__name__)


class DeepSeekR1ChatOpenAI:
    """
    DeepSeek R1 专用的 LangChain 兼容实现
    
    处理 DeepSeek Reasoner 的 reasoning_content 输出
    """
    
    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        temperature: float = 0.0,
        **kwargs
    ):
        from openai import OpenAI
        
        self.model_name = model
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key
        )
        self.temperature = temperature
        
        # LangChain 兼容属性
        self.model = model
    
    def _convert_messages(self, input_messages) -> List[Dict]:
        """转换 LangChain 消息格式为 OpenAI 格式"""
        message_history = []
        for msg in input_messages:
            if isinstance(msg, SystemMessage):
                message_history.append({"role": "system", "content": msg.content})
            elif isinstance(msg, AIMessage):
                message_history.append({"role": "assistant", "content": msg.content})
            else:
                message_history.append({"role": "user", "content": msg.content})
        return message_history
    
    async def ainvoke(
        self,
        input: LanguageModelInput,
        config: RunnableConfig = None,
        **kwargs
    ) -> AIMessage:
        """异步调用"""
        message_history = self._convert_messages(input)
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=message_history,
            temperature=self.temperature
        )
        
        # 提取 reasoning_content 和 content
        message = response.choices[0].message
        reasoning_content = getattr(message, 'reasoning_content', '') or ''
        content = message.content or ''
        
        return AIMessage(
            content=content,
            additional_kwargs={"reasoning_content": reasoning_content}
        )
    
    def invoke(
        self,
        input: LanguageModelInput,
        config: RunnableConfig = None,
        **kwargs
    ) -> AIMessage:
        """同步调用"""
        message_history = self._convert_messages(input)
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=message_history,
            temperature=self.temperature
        )
        
        message = response.choices[0].message
        reasoning_content = getattr(message, 'reasoning_content', '') or ''
        content = message.content or ''
        
        return AIMessage(
            content=content,
            additional_kwargs={"reasoning_content": reasoning_content}
        )


class DeepSeekProvider(BaseOpenAICompatibleProvider):
    """
    DeepSeek Provider
    
    支持:
    - deepseek-chat: 通用对话模型
    - deepseek-coder: 代码专用模型
    - deepseek-reasoner: R1 推理模型（特殊处理）
    """
    
    @property
    def provider_name(self) -> str:
        return "DeepSeek"
    
    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.DEEPSEEK
    
    def __init__(self, config: LLMConfig):
        # 设置默认 base_url
        if not config.base_url:
            config.base_url = os.getenv(
                "DEEPSEEK_ENDPOINT",
                PROVIDER_DEFAULT_ENDPOINTS.get("deepseek", "https://api.deepseek.com/v1")
            )
        
        # 从环境变量获取 API Key
        if not config.api_key:
            env_var = get_api_key_env_var("deepseek")
            config.api_key = os.getenv(env_var, "")
        
        super().__init__(config)
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
        **kwargs
    ) -> LLMResponse:
        """DeepSeek 聊天，特殊处理 R1 模型"""
        self.ensure_initialized()
        
        request_params = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.config.max_tokens,
        }
        
        # DeepSeek 不支持结构化输出，移除 response_format
        kwargs.pop('response_format', None)
        request_params.update(kwargs)
        
        try:
            response = self._client.chat.completions.create(**request_params)
            
            message = response.choices[0].message
            content = message.content or ""
            
            # R1 模型特殊处理：提取 reasoning_content
            reasoning_content = ""
            if hasattr(message, 'reasoning_content') and message.reasoning_content:
                reasoning_content = message.reasoning_content
            elif self.is_reasoning_model():
                # 尝试从内容中解析
                reasoning_content, content = self._parse_response_content(content)
            
            usage = response.usage
            
            return LLMResponse(
                content=content,
                reasoning_content=reasoning_content,
                model=response.model,
                finish_reason=response.choices[0].finish_reason,
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
                raw_response=response
            )
            
        except Exception as e:
            logger.error(f"[DeepSeek] 聊天请求失败: {e}")
            raise
    
    def get_langchain_llm(self) -> Any:
        """获取 LangChain LLM 实例"""
        # R1 模型使用特殊实现
        if self.is_reasoning_model():
            return DeepSeekR1ChatOpenAI(
                model=self.config.model_name,
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                temperature=self.config.temperature,
            )
        
        # 普通模型使用标准 ChatOpenAI
        from langchain_openai import ChatOpenAI
        
        return ChatOpenAI(
            model=self.config.model_name,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
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
                dont_force_structured_output=True,  # DeepSeek 不支持结构化输出
            )
        except ImportError:
            logger.warning("[DeepSeek] browser-use 未安装，回退到 LangChain")
            return self.get_langchain_llm()
    
    def supports_structured_output(self) -> bool:
        """DeepSeek 不支持结构化输出"""
        return False
