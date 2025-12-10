"""
Browser-Use Core Package

包含从 web-ui 移植的核心组件:
- BrowserUseAgent: 增强的 Agent
- CustomBrowser: 自定义浏览器配置
- CustomBrowserContext: 浏览器上下文
- CustomController: 自定义动作控制器 (含 MCP 支持)
"""

from .browser_use_agent import BrowserUseAgent
from .custom_browser import CustomBrowser
from .custom_context import CustomBrowserContext
from .custom_controller import CustomController

__all__ = [
    'BrowserUseAgent',
    'CustomBrowser',
    'CustomBrowserContext',
    'CustomController',
]
