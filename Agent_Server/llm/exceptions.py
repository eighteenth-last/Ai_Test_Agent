"""
LLM 模块自定义异常

作者: Ai_Test_Agent Team
版本: 1.0
"""


class LLMError(Exception):
    """LLM 基础异常"""
    pass


class ProviderNotFoundError(LLMError):
    """Provider 未找到异常"""
    def __init__(self, provider: str):
        self.provider = provider
        super().__init__(f"不支持的模型供应商: {provider}")


class ModelNotFoundError(LLMError):
    """模型未找到异常"""
    def __init__(self, model_name: str, provider: str = None):
        self.model_name = model_name
        self.provider = provider
        msg = f"模型 '{model_name}' 未找到"
        if provider:
            msg += f" (供应商: {provider})"
        super().__init__(msg)


class APIKeyMissingError(LLMError):
    """API Key 缺失异常"""
    def __init__(self, provider: str, env_var: str = None):
        self.provider = provider
        self.env_var = env_var
        msg = f"💥 {provider} API Key 未找到!"
        if env_var:
            msg += f" 🔑 请设置环境变量 `{env_var}` 或在 UI 中提供。"
        super().__init__(msg)


class ConfigurationError(LLMError):
    """配置错误异常"""
    def __init__(self, message: str, details: dict = None):
        self.details = details or {}
        super().__init__(message)


class ModelInitializationError(LLMError):
    """模型初始化错误"""
    def __init__(self, provider: str, model_name: str, reason: str = None):
        self.provider = provider
        self.model_name = model_name
        self.reason = reason
        msg = f"初始化模型失败: {provider}/{model_name}"
        if reason:
            msg += f" - {reason}"
        super().__init__(msg)


class OutputParsingError(LLMError):
    """输出解析错误"""
    def __init__(self, message: str, raw_output: str = None):
        self.raw_output = raw_output
        super().__init__(message)


class TokenLimitExceededError(LLMError):
    """Token 限制超出异常"""
    def __init__(self, used_tokens: int, max_tokens: int):
        self.used_tokens = used_tokens
        self.max_tokens = max_tokens
        super().__init__(f"Token 使用量超出限制: {used_tokens}/{max_tokens}")


class RateLimitError(LLMError):
    """速率限制异常"""
    def __init__(self, provider: str, retry_after: int = None):
        self.provider = provider
        self.retry_after = retry_after
        msg = f"{provider} API 速率限制"
        if retry_after:
            msg += f"，请在 {retry_after} 秒后重试"
        super().__init__(msg)


class NoActiveModelError(LLMError):
    """无激活模型异常"""
    def __init__(self):
        super().__init__("未找到激活的模型，请在模型管理页面激活一个模型")
