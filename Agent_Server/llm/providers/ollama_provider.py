"""
Ollama Provider 实现

支持本地运行的 Ollama 模型，包括 Qwen、Llama、DeepSeek 等

作者: Ai_Test_Agent Team
"""
import os
import logging
from typing import Any, Dict, List

from langchain_core.language_models.base import LanguageModelInput
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage

from ..base import BaseLLMProvider, LLMConfig, LLMResponse, ProviderType
from ..config import PROVIDER_DEFAULT_ENDPOINTS, is_reasoning_model

logger = logging.getLogger(__name__)


class DeepSeekR1ChatOllama:
    """
    Ollama 上的 DeepSeek R1 专用实现
    
    处理 <think>...</think> 格式的推理输出
    """
    
    def __init__(
        self,
        model: str,
        base_url: str,
        temperature: float = 0.0,
        num_ctx: int = 32000,
        **kwargs
    ):
        from langchain_ollama import ChatOllama
        
        self.model_name = model
        self._ollama = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
            num_ctx=num_ctx,
        )
        
        # LangChain 兼容属性
        self.model = model
    
    def _parse_thinking_output(self, content: str) -> tuple:
        """解析 <think>...</think> 格式"""
        if "<think>" in content and "</think>" in content:
            parts = content.split("</think>")
            if len(parts) >= 2:
                thinking = parts[0].replace("<think>", "").strip()
                final = parts[1].strip()
                
                # 处理 **JSON Response:** 格式
                if "**JSON Response:**" in final:
                    final = final.split("**JSON Response:**")[-1].strip()
                
                return thinking, final
        return "", content
    
    async def ainvoke(
        self,
        input: LanguageModelInput,
        config: RunnableConfig = None,
        **kwargs
    ) -> AIMessage:
        """异步调用"""
        response = await self._ollama.ainvoke(input)
        content = response.content
        
        thinking, final = self._parse_thinking_output(content)
        
        return AIMessage(
            content=final,
            additional_kwargs={"reasoning_content": thinking}
        )
    
    def invoke(
        self,
        input: LanguageModelInput,
        config: RunnableConfig = None,
        **kwargs
    ) -> AIMessage:
        """同步调用"""
        response = self._ollama.invoke(input)
        content = response.content
        
        thinking, final = self._parse_thinking_output(content)
        
        return AIMessage(
            content=final,
            additional_kwargs={"reasoning_content": thinking}
        )


class OllamaProvider(BaseLLMProvider):
    """
    Ollama Provider
    
    支持本地运行的所有 Ollama 模型
    """
    
    @property
    def provider_name(self) -> str:
        return "Ollama"
    
    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.OLLAMA
    
    def __init__(self, config: LLMConfig):
        # 设置默认 base_url
        if not config.base_url:
            config.base_url = os.getenv(
                "OLLAMA_ENDPOINT",
                PROVIDER_DEFAULT_ENDPOINTS.get("ollama", "http://localhost:11434")
            )
        
        super().__init__(config)
    
    def _initialize_client(self) -> Any:
        """初始化 Ollama 客户端"""
        try:
            import ollama
            return ollama.Client(host=self.config.base_url)
        except ImportError:
            logger.warning("[Ollama] ollama 库未安装，将使用 HTTP API")
            return None
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
        **kwargs
    ) -> LLMResponse:
        """Ollama 聊天"""
        self.ensure_initialized()
        
        try:
            if self._client:
                # 使用 ollama Python 库
                response = self._client.chat(
                    model=self.config.model_name,
                    messages=messages,
                    options={
                        "temperature": temperature if temperature is not None else self.config.temperature,
                        "num_ctx": self.config.num_ctx,
                        "num_predict": max_tokens or self.config.num_predict,
                    }
                )
                
                content = response.get("message", {}).get("content", "")
                
                # 处理推理模型
                reasoning_content = ""
                if self.is_reasoning_model():
                    if "<think>" in content and "</think>" in content:
                        parts = content.split("</think>")
                        reasoning_content = parts[0].replace("<think>", "").strip()
                        content = parts[1].strip()
                
                return LLMResponse(
                    content=content,
                    reasoning_content=reasoning_content,
                    model=self.config.model_name,
                    finish_reason="stop",
                    prompt_tokens=response.get("prompt_eval_count", 0),
                    completion_tokens=response.get("eval_count", 0),
                    total_tokens=response.get("prompt_eval_count", 0) + response.get("eval_count", 0),
                    raw_response=response
                )
            else:
                # 回退到 HTTP API
                import requests
                
                response = requests.post(
                    f"{self.config.base_url}/api/chat",
                    json={
                        "model": self.config.model_name,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "temperature": temperature if temperature is not None else self.config.temperature,
                            "num_ctx": self.config.num_ctx,
                        }
                    }
                )
                response.raise_for_status()
                result = response.json()
                
                content = result.get("message", {}).get("content", "")
                
                reasoning_content = ""
                if self.is_reasoning_model():
                    if "<think>" in content and "</think>" in content:
                        parts = content.split("</think>")
                        reasoning_content = parts[0].replace("<think>", "").strip()
                        content = parts[1].strip()
                
                return LLMResponse(
                    content=content,
                    reasoning_content=reasoning_content,
                    model=self.config.model_name,
                    finish_reason="stop",
                    raw_response=result
                )
                
        except Exception as e:
            logger.error(f"[Ollama] 聊天请求失败: {e}")
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
            import httpx
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.config.base_url}/api/chat",
                    json={
                        "model": self.config.model_name,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "temperature": temperature if temperature is not None else self.config.temperature,
                            "num_ctx": self.config.num_ctx,
                        }
                    },
                    timeout=self.config.timeout
                )
                response.raise_for_status()
                result = response.json()
                
                content = result.get("message", {}).get("content", "")
                
                reasoning_content = ""
                if self.is_reasoning_model():
                    if "<think>" in content and "</think>" in content:
                        parts = content.split("</think>")
                        reasoning_content = parts[0].replace("<think>", "").strip()
                        content = parts[1].strip()
                
                return LLMResponse(
                    content=content,
                    reasoning_content=reasoning_content,
                    model=self.config.model_name,
                    finish_reason="stop",
                    raw_response=result
                )
                
        except Exception as e:
            logger.error(f"[Ollama] 异步聊天请求失败: {e}")
            raise
    
    def get_langchain_llm(self) -> Any:
        """获取 LangChain LLM 实例"""
        # DeepSeek R1 使用特殊实现
        if self.is_reasoning_model() and "deepseek-r1" in self.config.model_name.lower():
            return DeepSeekR1ChatOllama(
                model=self.config.model_name,
                base_url=self.config.base_url,
                temperature=self.config.temperature,
                num_ctx=self.config.num_ctx,
            )
        
        from langchain_ollama import ChatOllama
        
        return ChatOllama(
            model=self.config.model_name,
            base_url=self.config.base_url,
            temperature=self.config.temperature,
            num_ctx=self.config.num_ctx,
            num_predict=self.config.num_predict,
        )
    
    def get_browser_use_llm(self) -> Any:
        """获取 Browser-Use LLM 实例"""
        return self.get_langchain_llm()
    
    def supports_structured_output(self) -> bool:
        """Ollama 不支持结构化输出"""
        return False
