"""
阿里云/通义千问 Provider 实现

支持 Qwen 系列模型，兼容 OpenAI API

已知问题（Qwen3.5 等大参数模型）：
- browser-use 的结构化输出 schema 不被可靠支持
- 模型可能返回 {"thinking": "..."} 而非 {"action": [...]} 格式
- 需要 dont_force_structured_output=True + add_schema_to_system_prompt=True

作者: Ai_Test_Agent Team
"""
import json
import os
import re
import logging
from typing import Any, Dict, List

from ..base import BaseOpenAICompatibleProvider, LLMConfig, LLMResponse, ProviderType
from ..config import PROVIDER_DEFAULT_ENDPOINTS, get_api_key_env_var

logger = logging.getLogger(__name__)


class AlibabaProvider(BaseOpenAICompatibleProvider):
    """
    阿里云/通义千问 Provider
    
    支持 Qwen 系列模型，通过 OpenAI 兼容 API
    """
    
    @property
    def provider_name(self) -> str:
        return "Alibaba"
    
    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.ALIBABA
    
    def __init__(self, config: LLMConfig):
        # 设置默认 base_url
        if not config.base_url:
            config.base_url = os.getenv(
                "ALIBABA_ENDPOINT",
                PROVIDER_DEFAULT_ENDPOINTS.get("alibaba", "https://dashscope.aliyuncs.com/compatible-mode/v1")
            )
        
        # 从环境变量获取 API Key
        if not config.api_key:
            env_var = get_api_key_env_var("alibaba")
            config.api_key = os.getenv(env_var, "")
        
        super().__init__(config)
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
        **kwargs
    ) -> LLMResponse:
        """
        Alibaba/Qwen 聊天

        Qwen 模型通过 DashScope 兼容 API 支持 response_format=json_object，
        但大参数模型（如 Qwen3.5-397B）在复杂 schema 下不稳定，
        这里保留 response_format 传递（用于简单 JSON 请求），
        browser-use 场景通过 dont_force_structured_output 单独处理。
        """
        return super().chat(messages, temperature, max_tokens, **kwargs)
    
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
    
    def get_browser_use_llm(self) -> Any:
        """
        获取 Browser-Use LLM 实例

        关键配置：
        - dont_force_structured_output=True: Qwen 模型不可靠支持 browser-use 的
          结构化输出 schema，强制使用会导致 {"thinking": "..."} 等无效输出
        - add_schema_to_system_prompt=True: 将 JSON schema 注入 system prompt，
          引导模型按正确格式输出
        """
        try:
            from browser_use.llm.openai.chat import ChatOpenAI as BrowserUseChatOpenAI
            
            return BrowserUseChatOpenAI(
                model=self.config.model_name,
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                temperature=self.config.temperature,
                dont_force_structured_output=True,
                add_schema_to_system_prompt=True,
            )
        except ImportError:
            logger.warning("[Alibaba] browser-use 未安装，回退到 LangChain")
            return self.get_langchain_llm()
    
    def supports_structured_output(self) -> bool:
        """Qwen 模型对 browser-use 的复杂 schema 支持不稳定"""
        return False

    def parse_json_response(self, content: str) -> dict:
        """
        Alibaba/Qwen JSON 解析

        Qwen 模型的常见问题：
        - Qwen3.5 等大参数模型可能返回 {"thinking": "...", "action": [...]}
          其中 thinking 字段不属于目标 schema
        - 可能在 JSON 前后添加中文解释文字
        - 偶尔有 markdown 代码块包裹
        - 可能返回 ```json\n{...}\n``` 格式
        """
        if not content:
            raise ValueError("LLM 响应为空")

        text = content.strip()

        # 1. 剥离 markdown 代码块
        text = self._extract_json(text)

        # 2. 直接尝试解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 3. 移除尾部逗号
        fixed = re.sub(r',\s*([}\]])', r'\1', text)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

        # 4. 提取第一个 JSON 对象（Qwen 可能在 JSON 前后加中文解释）
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                candidate = re.sub(r',\s*([}\]])', r'\1', match.group(0))
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        # 5. 回退到基类通用解析（含截断修复等）
        return super().parse_json_response(content)
