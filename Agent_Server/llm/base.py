"""
LLM Provider 基类

定义统一的接口和抽象基类，所有 Provider 实现都需要继承此基类

作者: Ai_Test_Agent Team
版本: 1.0
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union, Type
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Provider 类型枚举"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    GOOGLE = "google"
    ALIBABA = "alibaba"
    MOONSHOT = "moonshot"
    OLLAMA = "ollama"
    AZURE_OPENAI = "azure_openai"
    MISTRAL = "mistral"
    GROK = "grok"
    SILICONFLOW = "siliconflow"
    MODELSCOPE = "modelscope"
    ZHIPU = "zhipu"
    BAICHUAN = "baichuan"
    MINIMAX = "minimax"
    IBM = "ibm"
    CUSTOM = "custom"


@dataclass
class LLMConfig:
    """LLM 配置数据类"""
    provider: str
    model_name: str
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout: int = 60
    
    # 可选配置
    api_version: str = ""  # Azure OpenAI 需要
    project_id: str = ""   # IBM Watson 需要
    num_ctx: int = 32000   # Ollama 上下文长度
    num_predict: int = 1024  # Ollama 预测长度
    
    # 特性开关
    enable_thinking: bool = True  # 是否启用思考过程
    use_vision: bool = False  # 是否启用视觉
    
    # 额外参数
    extra_params: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "provider": self.provider,
            "model_name": self.model_name,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "api_version": self.api_version,
            "project_id": self.project_id,
            "num_ctx": self.num_ctx,
            "num_predict": self.num_predict,
            "enable_thinking": self.enable_thinking,
            "use_vision": self.use_vision,
            **self.extra_params
        }


@dataclass
class LLMResponse:
    """LLM 响应数据类"""
    content: str
    reasoning_content: str = ""  # 推理模型的思考过程
    model: str = ""
    finish_reason: str = ""
    
    # Token 使用量
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    # 元数据
    raw_response: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def full_content(self) -> str:
        """获取完整内容（包含推理过程）"""
        if self.reasoning_content:
            return f"<think>\n{self.reasoning_content}\n</think>\n{self.content}"
        return self.content


class BaseLLMProvider(ABC):
    """
    LLM Provider 抽象基类
    
    所有具体的 Provider 实现都需要继承此类并实现抽象方法
    """
    
    def __init__(self, config: LLMConfig):
        """
        初始化 Provider
        
        Args:
            config: LLM 配置
        """
        self.config = config
        self._client = None
        self._initialized = False
        
        logger.info(f"[{self.provider_name}] 初始化 Provider: model={config.model_name}")
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider 名称"""
        pass
    
    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Provider 类型"""
        pass
    
    @abstractmethod
    def _initialize_client(self) -> Any:
        """
        初始化底层客户端
        
        Returns:
            初始化后的客户端实例
        """
        pass
    
    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """
        同步聊天接口
        
        Args:
            messages: 消息列表
            **kwargs: 额外参数
            
        Returns:
            LLM 响应
        """
        pass
    
    @abstractmethod
    async def achat(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """
        异步聊天接口
        
        Args:
            messages: 消息列表
            **kwargs: 额外参数
            
        Returns:
            LLM 响应
        """
        pass
    
    def ensure_initialized(self):
        """确保客户端已初始化（延迟初始化）"""
        if not self._initialized:
            self._client = self._initialize_client()
            self._initialized = True
            logger.debug(f"[{self.provider_name}] 客户端初始化完成")
    
    def get_langchain_llm(self) -> Any:
        """
        获取 LangChain 格式的 LLM 实例
        
        Returns:
            LangChain LLM 实例
        """
        raise NotImplementedError(f"{self.provider_name} 未实现 LangChain 支持")
    
    def get_browser_use_llm(self) -> Any:
        """
        获取 Browser-Use 格式的 LLM 实例
        
        Returns:
            Browser-Use LLM 实例
        """
        raise NotImplementedError(f"{self.provider_name} 未实现 Browser-Use 支持")
    
    def supports_structured_output(self) -> bool:
        """是否支持结构化输出"""
        from .config import supports_structured_output
        return supports_structured_output(self.config.provider)
    
    def is_reasoning_model(self) -> bool:
        """是否为推理模型"""
        from .config import is_reasoning_model
        return is_reasoning_model(self.config.provider, self.config.model_name)
    
    def _parse_response_content(self, content: str) -> tuple:
        """
        解析响应内容，提取思考过程和最终回答
        
        Args:
            content: 原始响应内容
            
        Returns:
            (thinking_content, final_content) 元组
        """
        if not content:
            return "", ""
        
        # 处理 <think>...</think> 格式（常见于 DeepSeek R1 等）
        if "<think>" in content and "</think>" in content:
            parts = content.split("</think>")
            if len(parts) >= 2:
                thinking = parts[0].replace("<think>", "").strip()
                final = parts[1].strip()
                return thinking, final
        
        # 处理 **JSON Response:** 格式
        if "**JSON Response:**" in content:
            parts = content.split("**JSON Response:**")
            if len(parts) >= 2:
                thinking = parts[0].strip()
                final = parts[-1].strip()
                return thinking, final
        
        return "", content
    
    def _extract_json(self, content: str) -> str:
        """
        从响应中提取 JSON（可能在 markdown 代码块中）
        
        Args:
            content: 响应内容
            
        Returns:
            提取的 JSON 字符串
        """
        if not content:
            return content
        
        content = content.strip()
        
        # 处理 ```json ... ``` 格式
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        return content
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(provider={self.provider_name}, model={self.config.model_name})"


class BaseOpenAICompatibleProvider(BaseLLMProvider):
    """
    OpenAI 兼容 API 的基类
    
    许多 Provider（如 DeepSeek、阿里云、Moonshot 等）都兼容 OpenAI API，
    这个基类提供通用的实现
    """
    
    def _initialize_client(self) -> Any:
        """初始化 OpenAI 客户端"""
        from openai import OpenAI
        
        return OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout
        )
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
        response_format: Dict[str, str] = None,
        **kwargs
    ) -> LLMResponse:
        """同步聊天"""
        self.ensure_initialized()
        
        # 构建请求参数
        request_params = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.config.max_tokens,
        }
        
        if response_format:
            request_params["response_format"] = response_format
        
        # 合并额外参数
        request_params.update(kwargs)
        
        try:
            response = self._client.chat.completions.create(**request_params)
            
            # 解析响应
            message = response.choices[0].message
            content = message.content or ""
            
            # 处理推理模型的特殊输出
            reasoning_content = ""
            if hasattr(message, 'reasoning_content') and message.reasoning_content:
                reasoning_content = message.reasoning_content
            elif self.is_reasoning_model():
                reasoning_content, content = self._parse_response_content(content)
            
            # 获取 token 使用量
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
            logger.error(f"[{self.provider_name}] 聊天请求失败: {e}")
            raise
    
    async def achat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
        response_format: Dict[str, str] = None,
        **kwargs
    ) -> LLMResponse:
        """异步聊天"""
        from openai import AsyncOpenAI
        
        # 创建异步客户端
        async_client = AsyncOpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout
        )
        
        # 构建请求参数
        request_params = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.config.max_tokens,
        }
        
        if response_format:
            request_params["response_format"] = response_format
        
        request_params.update(kwargs)
        
        try:
            response = await async_client.chat.completions.create(**request_params)
            
            message = response.choices[0].message
            content = message.content or ""
            
            reasoning_content = ""
            if hasattr(message, 'reasoning_content') and message.reasoning_content:
                reasoning_content = message.reasoning_content
            elif self.is_reasoning_model():
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
            logger.error(f"[{self.provider_name}] 异步聊天请求失败: {e}")
            raise
    
    def get_langchain_llm(self) -> Any:
        """获取 LangChain LLM 实例"""
        from langchain_openai import ChatOpenAI
        
        return ChatOpenAI(
            model=self.config.model_name,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
